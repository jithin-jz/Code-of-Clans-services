from django.conf import settings
from django.contrib.auth.models import User
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
    - **Profile**: `bio`, `github_username`, `leetcode_username`
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
        if "github_username" in data:
            profile.github_username = data["github_username"]
        if "leetcode_username" in data:
            profile.leetcode_username = data["leetcode_username"]

        # 3. Handle File Uploads (to Supabase Storage)
        # 3. Handle File Uploads (Native Django Storage)
        if "avatar" in request.FILES:
            profile.avatar = request.FILES["avatar"]

        if "banner" in request.FILES:
            profile.banner = request.FILES["banner"]

        profile.save()

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
        try:
            user = User.objects.get(username=username)
        except User.DoesNotExist:
            return Response(
                {"error": "User not found"}, status=status.HTTP_404_NOT_FOUND
            )

        data = UserSerializer(user, context={"request": request}).data

        # Add stats
        data["followers_count"] = user.followers.count()
        data["following_count"] = user.following.count()

        # Check if requesting user is following
        if request.user.is_authenticated:
            data["is_following"] = user.followers.filter(follower=request.user).exists()
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
