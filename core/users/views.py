from django.conf import settings
from django.contrib.auth.models import User
from django.core.cache import cache
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework import serializers
from drf_spectacular.utils import extend_schema, OpenApiTypes

from .models import UserProfile, UserFollow
from .serializers import (
    UserSerializer,
    UserSummarySerializer,
    FollowToggleResponseSerializer,
    RedeemReferralSerializer,
)


from xpoint.services import XPService
from .dynamo import dynamo_activity_client


from django.utils.decorators import method_decorator
from django.views.decorators.cache import never_cache


@method_decorator(never_cache, name="dispatch")
class CurrentUserView(APIView):
    """Get the currently authenticated user."""

    permission_classes = [IsAuthenticated]
    serializer_class = UserSerializer

    def get(self, request):
        return Response(
            UserSerializer(request.user, context={"request": request}).data,
            status=status.HTTP_200_OK,
        )


class ProfileUpdateView(APIView):
    """
    Updates the authenticated user's profile information.

    This view handles patches to both the core `User` model and the `UserProfile` model.

    **Supported Updates:**
    - **Identity**: `username`, `first_name`, `last_name`
    - **Profile**: `bio`
    - **Media**: `avatar`, `banner` (File uploads)

    Returns the updated user object.
    """

    permission_classes = [IsAuthenticated]
    serializer_class = UserSerializer

    def patch(self, request):
        user = request.user
        data = request.data

        # 1. Update Core User Model Fields
        if "username" in data:
            user.username = data["username"]
        if "first_name" in data:
            user.first_name = data["first_name"]
        if "last_name" in data:
            user.last_name = data["last_name"]
        user.save()

        # 2. Update Extended UserProfile Fields
        profile = user.profile
        if "bio" in data:
            profile.bio = data["bio"]

        # 3. Handle File Uploads (to Supabase Storage)
        # 3. Handle File Uploads (Native Django Storage)
        if "avatar" in request.FILES:
            profile.avatar = request.FILES["avatar"]

        if "banner" in request.FILES:
            profile.banner = request.FILES["banner"]

        profile.save()

        # Invalidate profile cache
        cache.delete(f'profile:{user.username}')

        # Generate new tokens to reflect updated claims (username/avatar)
        from auth.utils import generate_tokens

        tokens = generate_tokens(user)

        data = UserSerializer(user, context={"request": request}).data
        data["access_token"] = tokens["access_token"]
        data["refresh_token"] = tokens["refresh_token"]

        return Response(
            data,
            status=status.HTTP_200_OK,
        )


class ProfileDetailView(APIView):
    """View to get public profile details."""

    permission_classes = [AllowAny]
    serializer_class = UserSerializer

    def get(self, request, username):
        # Try to get from cache first
        cache_key = f'profile:{username}'
        data = cache.get(cache_key)
        
        if not data:
            try:
                user = User.objects.get(username=username)
            except User.DoesNotExist:
                return Response(
                    {"error": "User not found"}, status=status.HTTP_404_NOT_FOUND
                )

            data = UserSerializer(user, context={"request": request}).data

            # Add stats (redundant if serializer has them, but ensuring consistency)
            data["followers_count"] = user.followers.count()
            data["following_count"] = user.following.count()
            
            # Cache the public data for 5 minutes
            cache.set(cache_key, data, 300)

        # Inject request-specific data (NEVER CACHE THIS)
        if request.user.is_authenticated:
            # Check if relationship exists. 
            # We use the relationship model directly to avoid fetching the user object if data came from cache
            data["is_following"] = UserFollow.objects.filter(
                follower=request.user, following__username=username
            ).exists()
        else:
            data["is_following"] = False
        
        return Response(data, status=status.HTTP_200_OK)


class FollowToggleView(APIView):
    """View to toggle follow status."""

    permission_classes = [IsAuthenticated]
    serializer_class = FollowToggleResponseSerializer

    def post(self, request, username):
        try:
            target_user = User.objects.get(username=username)
        except User.DoesNotExist:
            return Response(
                {"error": "User not found"}, status=status.HTTP_404_NOT_FOUND
            )

        if target_user == request.user:
            return Response(
                {"error": "Cannot follow yourself"}, status=status.HTTP_400_BAD_REQUEST
            )

        follow, created = UserFollow.objects.get_or_create(
            follower=request.user, following=target_user
        )

        if not created:
            # If relationship exists, unfollow
            follow.delete()
            is_following = False
        else:
            is_following = True
            
        # Invalidate profile cache because followers_count changed
        cache.delete(f'profile:{username}')

        return_status = status.HTTP_201_CREATED if created else status.HTTP_200_OK
        return Response(
            {
                "is_following": is_following,
                "follower_count": target_user.followers.count(),
                "following_count": target_user.following.count(),
            },
            status=return_status,
        )


class UserFollowersView(APIView):
    """View to get list of followers for a user."""

    permission_classes = [AllowAny]
    serializer_class = UserSummarySerializer

    def get(self, request, username):
        try:
            target_user = User.objects.get(username=username)
        except User.DoesNotExist:
            return Response(
                {"error": "User not found"}, status=status.HTTP_404_NOT_FOUND
            )

        followers = target_user.followers.all()
        # We want to show: username, avatar, and if the *requesting user* is following them

        data = []
        auth_user = request.user

        for rel in followers:
            follower_user = rel.follower
            is_following = False
            if auth_user.is_authenticated:
                is_following = auth_user.following.filter(
                    following=follower_user
                ).exists()

            profile = getattr(follower_user, "profile", None)

            data.append(
                {
                    "username": follower_user.username,
                    "first_name": follower_user.first_name,
                    "avatar_url": (
                        (
                            f"{settings.BACKEND_URL}{profile.avatar.url}"
                            if profile.avatar
                            else None
                        )
                        if profile
                        else None
                    ),
                    "is_following": is_following,
                }
            )

        return Response(data, status=status.HTTP_200_OK)


class UserFollowingView(APIView):
    """View to get list of users a user is following."""

    permission_classes = [AllowAny]
    serializer_class = UserSummarySerializer

    def get(self, request, username):
        try:
            target_user = User.objects.get(username=username)
        except User.DoesNotExist:
            return Response(
                {"error": "User not found"}, status=status.HTTP_404_NOT_FOUND
            )

        following = target_user.following.all()

        data = []
        auth_user = request.user

        for rel in following:
            following_user = rel.following
            is_following = False
            if auth_user.is_authenticated:
                # Check if auth user is following this person (who target_user is also following)
                is_following = auth_user.following.filter(
                    following=following_user
                ).exists()

            profile = getattr(following_user, "profile", None)

            data.append(
                {
                    "username": following_user.username,
                    "first_name": following_user.first_name,
                    "avatar_url": (
                        (
                            f"{settings.BACKEND_URL}{profile.avatar.url}"
                            if profile.avatar
                            else None
                        )
                        if profile
                        else None
                    ),
                    "is_following": is_following,
                }
            )

        return Response(data, status=status.HTTP_200_OK)


class RedeemReferralView(APIView):
    """View to redeem a referral code."""

    permission_classes = [IsAuthenticated]
    serializer_class = RedeemReferralSerializer

    def post(self, request):
        code = request.data.get("code")

        if not code:
            return Response(
                {"error": "Referral code is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            profile = request.user.profile
        except UserProfile.DoesNotExist:
            return Response(
                {"error": "User profile not found"}, status=status.HTTP_404_NOT_FOUND
            )

        if profile.referred_by:
            return Response(
                {"error": "You have already redeemed a referral code"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if profile.referral_code == code:
            return Response(
                {"error": "Cannot redeem your own referral code"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            referrer_profile = UserProfile.objects.get(referral_code=code)
        except UserProfile.DoesNotExist:
            return Response(
                {"error": "Invalid referral code"}, status=status.HTTP_404_NOT_FOUND
            )

        # Update user profile
        profile.referred_by = referrer_profile.user
        XPService.add_xp(request.user, 100, source=XPService.SOURCE_REFERRAL)
        profile.refresh_from_db()  # Refresh to get the updated XP
        profile.save()  # save the referred_by change

        return Response(
            {
                "message": "Referral code redeemed successfully",
                "xp_awarded": 100,
                "new_total_xp": profile.xp,
            },
            status=status.HTTP_200_OK,
        )


class SuggestedUsersView(APIView):
    """View to get suggested users to follow."""

    permission_classes = [IsAuthenticated]
    serializer_class = UserSummarySerializer

    def get(self, request):
        # Get users the current user is NOT following (excluding self)
        following_ids = request.user.following.values_list('following_id', flat=True)
        
        suggested = User.objects.exclude(
            id__in=list(following_ids) + [request.user.id]
        ).exclude(
            is_superuser=True
        ).exclude(
            is_staff=True
        ).select_related('profile').order_by('?')[:5]

        data = []
        for user in suggested:
            profile = getattr(user, "profile", None)
            data.append({
                "username": user.username,
                "first_name": user.first_name,
                "avatar_url": (
                    request.build_absolute_uri(profile.avatar.url)
                    if profile and profile.avatar
                    else None
                ),
            })

        return Response(data, status=status.HTTP_200_OK)

class ContributionHistoryView(APIView):
    """View to get contribution history for the contribution graph."""

    permission_classes = [AllowAny]

    def get(self, request, username):
        try:
            user = User.objects.get(username=username)
        except User.DoesNotExist:
            return Response(
                {"error": "User not found"}, status=status.HTTP_404_NOT_FOUND
            )

        items = dynamo_activity_client.get_contribution_history(user.id)
        
        # Format for frontend (usually expects a map or list of {date, count})
        formatted_data = [
            {"date": item["date"], "count": int(item["contribution_count"])}
            for item in items
        ]

        return Response(formatted_data, status=status.HTTP_200_OK)
