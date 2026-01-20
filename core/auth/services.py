import logging
from django.contrib.auth.models import User
from django.db import transaction
from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile
import requests
from datetime import datetime, timedelta, timezone
from users.models import UserProfile
from .models import EmailOTP
from .utils import (
    generate_tokens,
    generate_otp_code,
    get_github_access_token,
    get_github_user,
    get_github_user_email,
    get_google_access_token,
    get_google_user,
    get_discord_access_token,
    get_discord_access_token,
    get_discord_user,
)
from .emails import send_welcome_email, send_otp_email

logger = logging.getLogger(__name__)

class AuthService:
    """
    Service layer for handling Authentication logic.
    Decouples business logic from Views.
    """

    @staticmethod
    def handle_oauth_login(provider, code):
        """
        Orchestrates the complete OAuth login lifecycle.
        
        Args:
            provider (str): The OAuth provider name ('github', 'google', 'discord').
            code (str): The authorization code received from the frontend callback.
            
        Returns:
            tuple: (User object, tokens_dict) on success, or (None, error_dict) on failure.
            
        Flow:
            1.  **Token Exchange**: Swaps the auth `code` for an `access_token` from the provider.
            2.  **User Info Fetch**: Uses the `access_token` to fetch user profile (email, name, avatar).
            3.  **Atomic User Creation/Matching**: enters a database transaction to safe-guard data integrity:
                *   Checks if a user with this `provider_id` already exists.
                *   If not, checks if a user with the same `email` exists (Account Linking).
                *   If neither, creates a new `User` and `UserProfile`.
            4.  **JWT Generation**: Issues internal access/refresh tokens for the session.
        """
        # 1. Exchange code -> access_token
        token_data = AuthService._exchange_code_for_token(provider, code)
        if 'error' in token_data:
            return None, token_data

        access_token = token_data.get('access_token')
        refresh_token = token_data.get('refresh_token', '')

        # 2. Get User Info
        user_info = AuthService._get_provider_user_info(provider, access_token)
        if 'error' in user_info:
            return None, user_info

        # 3. Match or Create User (Atomic Transaction)
        # Using atomic ensures we don't create half-records if something fails
        with transaction.atomic():
            user = AuthService._match_or_create_user(
                provider=provider,
                user_info=user_info,
                tokens={'access': access_token, 'refresh': refresh_token}
            )

        if not user.is_active:
             return None, {'error': 'User account is disabled.'}

        # 4. Generate JWTs
        jwt_tokens = generate_tokens(user)
        
        return user, jwt_tokens

    @staticmethod
    def _exchange_code_for_token(provider, code):
        if provider == 'github':
            return get_github_access_token(code)
        elif provider == 'google':
            return get_google_access_token(code)
        elif provider == 'discord':
            return get_discord_access_token(code)
        return {'error': 'Invalid provider'}

    @staticmethod
    def _get_provider_user_info(provider, access_token):
        if provider == 'github':
            user = get_github_user(access_token)
            if 'id' not in user: return {'error': 'Failed to fetch GitHub user'}
            
            # Normalize data
            email = user.get('email') or get_github_user_email(access_token)
            return {
                'id': str(user['id']),
                'email': email,
                'username': user.get('login'),
                'name': user.get('name', ''),
                'avatar_url': user.get('avatar_url', ''),
            }

        elif provider == 'google':
            user = get_google_user(access_token)
            if 'id' not in user: return {'error': 'Failed to fetch Google user'}
            
            return {
                'id': str(user['id']),
                'email': user.get('email', ''),
                'username': user.get('email', '').split('@')[0], # Fallback
                'name': user.get('name', ''),
                'avatar_url': user.get('picture', ''),
            }

        elif provider == 'discord':
            user = get_discord_user(access_token)
            if 'id' not in user: return {'error': 'Failed to fetch Discord user'}

            discord_id = str(user['id'])
            avatar_hash = user.get('avatar')
            if avatar_hash:
                avatar_url = f"https://cdn.discordapp.com/avatars/{discord_id}/{avatar_hash}.png"
            else:
                discriminator = user.get('discriminator', '0')
                avatar_url = f"https://cdn.discordapp.com/embed/avatars/{int(discriminator) % 5}.png"

            return {
                'id': discord_id,
                'email': user.get('email', ''),
                'username': user.get('username', f"discord_{discord_id}"),
                'name': user.get('global_name', user.get('username')),
                'avatar_url': avatar_url,
            }
            
        return {'error': 'Invalid provider'}

    @staticmethod
    def _match_or_create_user(provider, user_info, tokens):
        """
        Determines the correct User to log in based on provider data.
        
        Algorithm:
        1.  **Primary Match (Provider ID)**: 
            Do we already have a `UserProfile` for this specific provider ID?
            If yes -> Return that user immediately (and update tokens).
            
        2.  **Secondary Match (Email Linking)**:
            If no profile exists, do we have a `User` with the same email address?
            If yes -> **Link** the new provider to this existing user. 
            This handles "Sign in with Google" for a user who previously used GitHub with the same email.
            
        3.  **New User Creation**:
            If no match found, create a brand new `User` and `UserProfile`.
            Ensures username uniqueness by appending integers if needed.
        """
        provider_id = user_info['id']
        email = user_info['email']
        
        # --- Step 1: Try Primary Match (Provider ID) ---
        try:
            profile = UserProfile.objects.select_related('user').get(
                provider=provider, 
                provider_id=provider_id
            )
            # User Found! Update their latest tokens
            profile.access_token = tokens['access']
            profile.refresh_token = tokens['refresh']
            profile.save()
            return profile.user
            
        except UserProfile.DoesNotExist:
            pass # Continue to secondary match

        # --- Step 2: Try Secondary Match (Email Linking) ---
        user = None
        if email:
            user = User.objects.filter(email=email).first()

        if user:
            # User exists but this specific provider profile is missing.
            # ACTION: Link this new provider to the existing account.
            logger.info(f"Linking existing user {user.username} (Email: {email}) to new {provider} profile")
            AuthService._create_profile(user, provider, user_info, tokens)
            return user

        # --- Step 3: Create New User ---
        # Generate a unique username based on the provider's username or email
        username = AuthService._generate_unique_username(user_info['username'])
        
        # Parse full name into first/last
        name_parts = user_info['name'].split(' ', 1) if user_info['name'] else ['', '']
        first_name = name_parts[0]
        last_name = name_parts[1] if len(name_parts) > 1 else ''

        # Create Django User
        user = User.objects.create_user(
            username=username,
            email=email or '', # Save email to enable future linking
            first_name=first_name,
            last_name=last_name
        )
        
        # Create associated UserProfile
        AuthService._create_profile(user, provider, user_info, tokens)
        
        # Send Welcome Email (Non-blocking ideally, but here sync for now)
        send_welcome_email(user)
        
        return user

    @staticmethod
    def _create_profile(user, provider, user_info, tokens):
        """
        Creates or updates the UserProfile model.
        """
        profile = getattr(user, 'profile', None)
        
        if profile:
            # Update legacy profile with new provider's info
            profile.provider = provider
            profile.provider_id = user_info['id']
            profile.access_token = tokens['access']
            profile.refresh_token = tokens['refresh']
            profile.save()
            
            # Update avatar if missing
            if not profile.avatar and user_info.get('avatar_url'):
                 AuthService._download_and_save_avatar(profile, user_info['avatar_url'])
                 
        else:
            # Create fresh profile
            profile = UserProfile.objects.create(
                user=user,
                provider=provider,
                provider_id=user_info['id'],
                # avatar IS NOT SET HERE, we verify/download it below
                access_token=tokens['access'],
                refresh_token=tokens['refresh'],
                github_username=user_info['username'] if provider == 'github' else None,
            )
            
            if user_info.get('avatar_url'):
                AuthService._download_and_save_avatar(profile, user_info['avatar_url'])

    @staticmethod
    def _download_and_save_avatar(profile, url):
        """Helper to download image from URL and save to ImageField."""
        try:
            response = requests.get(url, timeout=10)
            if response.status_code == 200:
                file_name = url.split("/")[-1].split("?")[0]
                if not file_name:
                    file_name = f"avatar_{profile.user.id}.png"
                
                # Ensure extension
                if "." not in file_name:
                    file_name += ".png"

                profile.avatar.save(file_name, ContentFile(response.content), save=True)
        except Exception as e:
            logger.error(f"Failed to download avatar from {url}: {e}")

    @staticmethod
    def _generate_unique_username(base_username):
        """Ensure username uniqueness."""
        username = base_username
        counter = 1
        while User.objects.filter(username=username).exists():
            username = f"{base_username}_{counter}"
            counter += 1
        return username


    @staticmethod
    def request_otp(email):
        """
        Generates and sends an OTP to the given email.
        """
        email = email.lower().strip()
        otp_code = generate_otp_code()
        
        # Save OTP to DB (update existing or create new)
        # We can just create a new record, or update latest. 
        # For simplicity, create new and optionally cleanup old ones later or use expiration.
        EmailOTP.objects.create(email=email, otp=otp_code)
        
        # Send Email
        send_otp_email(email, otp_code)
        
        return True

    @staticmethod
    def verify_otp(email, otp):
        """
        Verifies the OTP and logs the user in (or creates them).
        """
        logger.info(f"Verifying OTP for {email} with code {otp}")
        
        email = email.lower().strip()
        otp = otp.strip()
        
        # Find the OTP
        # Check for OTPs created in the last 10 minutes
        expiry_time = datetime.now(timezone.utc) - timedelta(minutes=10)
        
        try:
            # Debug log
            logger.info(f"Looking for OTP: email={email}, otp={otp}, created_at__gte={expiry_time}")
            
            otp_record = EmailOTP.objects.filter(
                email__iexact=email, 
                otp=otp, 
                created_at__gte=expiry_time
            ).latest('created_at')
            
            logger.info(f"OTP Record found: {otp_record}")
            
        except EmailOTP.DoesNotExist:
            logger.warning(f"OTP not found or expired for {email}")
            # Debug: check if any OTP exists for this email
            recent_otps = EmailOTP.objects.filter(email__iexact=email).values('otp', 'created_at')
            logger.warning(f"Recent OTPs for this email: {list(recent_otps)}")
            
            return None, {'error': 'Invalid or expired OTP.'}
            
        # Valid OTP. Now get or create user.
        try:
            with transaction.atomic():
                user = User.objects.filter(email__iexact=email).first()
                
                if not user:
                    logger.info(f"Creating new user for {email}")
                    # Create New User
                    username = email.split('@')[0]
                    username = AuthService._generate_unique_username(username)
                    
                    user = User.objects.create_user(
                        username=username,
                        email=email
                    )
                    
                    # NOTE: A post_save signal in users/models.py might have already created a profile 
                    # with provider='local'. We should check and update it, or create if missing.
                    if hasattr(user, 'profile'):
                        profile = user.profile
                        profile.provider = 'email'
                        profile.provider_id = email
                        profile.save()
                    else:
                        UserProfile.objects.create(
                            user=user,
                            provider='email', 
                            provider_id=email, 
                            access_token='',
                            refresh_token=''
                        )
                        
                    # Send welcome email for new user?
                    send_welcome_email(user)
                
                else:
                    logger.info(f"Found existing user {user.username} for {email}")
                    # User exists. Check/Update profile?
                    if not hasattr(user, 'profile'):
                         UserProfile.objects.create(
                            user=user,
                            provider='email',
                            provider_id=email,
                            access_token='',
                            refresh_token=''
                        )
                
                # Helper: Delete used OTP to prevent replay?
                otp_record.delete()
                
                # Generate Tokens
                tokens = generate_tokens(user)
                
            if not user.is_active:
                 return None, {'error': 'User account is disabled.'}
                 
            return user, tokens
            
        except Exception as e:
            logger.exception(f"Error during user creation/login in verify_otp: {e}")
            return None, {'error': 'Internal server error during login.'}
