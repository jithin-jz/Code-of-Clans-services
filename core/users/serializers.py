from rest_framework import serializers
from django.contrib.auth.models import User
from drf_spectacular.utils import extend_schema_field
from .models import UserProfile, UserFollow


class UserProfileSerializer(serializers.ModelSerializer):

    # Computed field to indicate whether this user was referred by someone
    is_referred = serializers.SerializerMethodField()

    # Map ImageFields to URLs for frontend compatibility
    avatar_url = serializers.ImageField(source="avatar", read_only=True)
    banner_url = serializers.ImageField(source="banner", read_only=True)

    class Meta:
        model = UserProfile

        # Only expose non-sensitive, UI-relevant profile fields
        # Tokens, provider_id, referred_by are intentionally excluded
        fields = [
            "provider",
            "avatar_url",
            "banner_url",
            "bio",
            "xp",
            "referral_code",
            "is_referred",
            "created_at",
            "github_username",
            "leetcode_username",
            "streak_freezes",
            "active_theme",
            "active_font",
            "active_effect",
            "active_victory",
        ]

    @extend_schema_field(bool)
    def get_is_referred(self, obj):
        # Boolean derived from presence of a referrer
        return obj.referred_by is not None


class UserSerializer(serializers.ModelSerializer):

    # Profile is injected manually to avoid nested serializer overhead
    profile = serializers.SerializerMethodField()

    # Social graph metrics (computed, not stored)
    followers_count = serializers.SerializerMethodField()
    following_count = serializers.SerializerMethodField()

    class Meta:
        model = User

        # Includes permission flags for admin-aware frontends
        fields = [
            "id",
            "username",
            "email",
            "first_name",
            "last_name",
            "profile",  # Nested profile data (avatar, bio, etc.)
            "followers_count",  # Social proof metric
            "following_count",  # Social proof metric
            "is_staff",  # For Access Control (e.g. show Admin Link)
            "is_superuser",  # For Access Control
            "is_active",  # Status check
        ]

    @extend_schema_field(UserProfileSerializer)
    def get_profile(self, obj):
        # Defensive access in case profile was not created (edge cases)
        try:
            return UserProfileSerializer(obj.profile, context=self.context).data
        except:
            return None

    @extend_schema_field(int)
    def get_followers_count(self, obj):
        # Count of users following this user
        return obj.followers.count()

    @extend_schema_field(int)
    def get_following_count(self, obj):
        # Count of users this user follows
        return obj.following.count()


class UserSummarySerializer(serializers.Serializer):
    username = serializers.CharField()
    first_name = serializers.CharField()
    avatar_url = serializers.URLField(allow_null=True)
    is_following = serializers.BooleanField()


class FollowToggleResponseSerializer(serializers.Serializer):
    is_following = serializers.BooleanField()
    follower_count = serializers.IntegerField()
    following_count = serializers.IntegerField()


class RedeemReferralSerializer(serializers.Serializer):
    code = serializers.CharField(
        required=True, help_text="The referral code to redeem."
    )
