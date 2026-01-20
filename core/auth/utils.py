import jwt

import hashlib
import hmac
import time
import requests
import random
import string
from datetime import datetime, timedelta, timezone
from django.conf import settings


def generate_otp_code(length=4):
    """Generate a numeric OTP code."""
    return ''.join(random.choices(string.digits, k=length))



def generate_access_token(user):
    """
    Generate a short-lived JWT access token.
    Contains user identity (id, username, email) but no sensitive data.
    """
    payload = {
        'user_id': user.id,
        'username': user.username,
        'email': user.email,
        'avatar_url': (f"{settings.BACKEND_URL}{user.profile.avatar.url}" if user.profile.avatar else None) if hasattr(user, 'profile') else None,
        'exp': datetime.now(timezone.utc) + timedelta(seconds=settings.JWT_ACCESS_TOKEN_LIFETIME),
        'iat': datetime.now(timezone.utc),
        'type': 'access'
    }
    return jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def generate_refresh_token(user):
    """
    Generate a long-lived JWT refresh token.
    Used to obtain new access tokens without re-login.
    """
    payload = {
        'user_id': user.id,
        'exp': datetime.now(timezone.utc) + timedelta(seconds=settings.JWT_REFRESH_TOKEN_LIFETIME),
        'iat': datetime.now(timezone.utc),
        'type': 'refresh'
    }
    return jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def decode_token(token):
    """
    Decode and validate a JWT token.
    Returns the payload dict if valid, or None if expired/invalid.
    """
    try:
        payload = jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None


def generate_tokens(user):
    """
    Helper to generate both access and refresh tokens for a user.
    Usage: On Login, Registration, or Token Refresh.
    """
    return {
        'access_token': generate_access_token(user),
        'refresh_token': generate_refresh_token(user),
    }


# GitHub OAuth helpers
def get_github_access_token(code):
    """Exchange authorization code for GitHub access token."""

    response = requests.post(
        'https://github.com/login/oauth/access_token',
        data={
            'client_id': settings.GITHUB_CLIENT_ID,
            'client_secret': settings.GITHUB_CLIENT_SECRET,
            'code': code,
            'redirect_uri': settings.GITHUB_REDIRECT_URI,
        },
        headers={'Accept': 'application/json'}
    )

    return response.json()


def get_github_user(access_token):
    """Get GitHub user data using access token."""
    response = requests.get(
        'https://api.github.com/user',
        headers={
            'Authorization': f'Bearer {access_token}',
            'Accept': 'application/json'
        }
    )
    return response.json()


def get_github_user_email(access_token):
    """Get GitHub user's primary email."""
    response = requests.get(
        'https://api.github.com/user/emails',
        headers={
            'Authorization': f'Bearer {access_token}',
            'Accept': 'application/json'
        }
    )
    emails = response.json()
    for email in emails:
        if email.get('primary'):
            return email.get('email')
    return emails[0].get('email') if emails else None


# Google OAuth helpers
def get_google_access_token(code):
    """Exchange authorization code for Google access token."""

    response = requests.post(
        'https://oauth2.googleapis.com/token',
        data={
            'client_id': settings.GOOGLE_CLIENT_ID,
            'client_secret': settings.GOOGLE_CLIENT_SECRET,
            'code': code,
            'redirect_uri': settings.GOOGLE_REDIRECT_URI,
            'grant_type': 'authorization_code',
        }
    )

    return response.json()


def get_google_user(access_token):
    """Get Google user data using access token."""
    response = requests.get(
        'https://www.googleapis.com/oauth2/v2/userinfo',
        headers={'Authorization': f'Bearer {access_token}'}
    )
    return response.json()


# Discord OAuth helpers
def get_discord_access_token(code):
    """Exchange authorization code for Discord access token."""

    response = requests.post(
        'https://discord.com/api/oauth2/token',
        data={
            'client_id': settings.DISCORD_CLIENT_ID,
            'client_secret': settings.DISCORD_CLIENT_SECRET, 
            'code': code,
            'redirect_uri': settings.DISCORD_REDIRECT_URI,
            'grant_type': 'authorization_code',
        },
        headers={'Content-Type': 'application/x-www-form-urlencoded'}
    )

    return response.json()


def get_discord_user(access_token):
    """Get Discord user data using access token."""
    response = requests.get(
        'https://discord.com/api/users/@me',
        headers={'Authorization': f'Bearer {access_token}'}
    )
    return response.json()
