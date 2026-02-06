from django.contrib.auth.models import User
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from drf_spectacular.utils import extend_schema, OpenApiTypes, inline_serializer
from rest_framework import serializers
from django.utils import timezone
from datetime import timedelta
from django.db.models import Sum

from users.models import UserProfile
from users.serializers import UserSerializer


class AdminStatsView(APIView):
    """View to get admin dashboard statistics."""

    permission_classes = [IsAuthenticated]

    @extend_schema(
        responses={
            200: inline_serializer(
                name="AdminStatsResponse",
                fields={
                    "total_users": serializers.IntegerField(),
                    "active_sessions": serializers.IntegerField(),
                    "oauth_logins": serializers.IntegerField(),
                    "total_gems": serializers.IntegerField(),
                },
            ),
            403: OpenApiTypes.OBJECT,
        },
        description="Get administration statistics.",
    )
    def get(self, request):
        if not (request.user.is_staff or request.user.is_superuser):
            return Response({"error": "Unauthorized"}, status=status.HTTP_403_FORBIDDEN)

        total_users = User.objects.count()

        # Active sessions in last 24 hours
        yesterday = timezone.now() - timedelta(days=1)
        active_sessions = User.objects.filter(last_login__gte=yesterday).count()

        # OAuth logins (Providers other than email/local)
        oauth_logins = UserProfile.objects.exclude(
            provider__in=["email", "local"]
        ).count()

        # Total Gems (XP)
        total_xp = UserProfile.objects.aggregate(total_xp=Sum("xp"))["total_xp"] or 0

        return Response(
            {
                "total_users": total_users,
                "active_sessions": active_sessions,
                "oauth_logins": oauth_logins,
                "total_gems": total_xp,
            },
            status=status.HTTP_200_OK,
        )


class UserListView(APIView):
    """View to list all users for admin."""

    permission_classes = [IsAuthenticated]
    serializer_class = UserSerializer

    @extend_schema(
        responses={
            200: UserSerializer(many=True),
            403: OpenApiTypes.OBJECT,
        },
        description="List all users (Admin only).",
    )
    def get(self, request):
        if not (request.user.is_staff or request.user.is_superuser):
            return Response({"error": "Unauthorized"}, status=status.HTTP_403_FORBIDDEN)

        users = User.objects.all().order_by("-date_joined")
        return Response(
            UserSerializer(users, many=True, context={"request": request}).data,
            status=status.HTTP_200_OK,
        )


class UserBlockToggleView(APIView):
    """View to toggle user active status."""

    permission_classes = [IsAuthenticated]

    @extend_schema(
        request=None,
        responses={200: OpenApiTypes.OBJECT},
        description="Toggle user active status (block/unblock).",
    )
    def post(self, request, username):
        if not (request.user.is_staff or request.user.is_superuser):
            return Response({"error": "Unauthorized"}, status=status.HTTP_403_FORBIDDEN)

        try:
            user = User.objects.get(username=username)
        except User.DoesNotExist:
            return Response(
                {"error": "User not found"}, status=status.HTTP_404_NOT_FOUND
            )

        if user == request.user:
            return Response(
                {"error": "Cannot block yourself"}, status=status.HTTP_400_BAD_REQUEST
            )

        # Toggle status directly on user model
        user.is_active = not user.is_active
        user.save()

        return Response(
            {
                "message": f"User {'unblocked' if user.is_active else 'blocked'} successfully",
                "is_active": user.is_active,
            },
            status=status.HTTP_200_OK,
        )


class UserDeleteView(APIView):
    """View to delete a user account."""

    permission_classes = [IsAuthenticated]

    @extend_schema(
        request=None,
        responses={200: OpenApiTypes.OBJECT},
        description="Delete a user account (Admin only).",
    )
    def delete(self, request, username):
        if not (request.user.is_staff or request.user.is_superuser):
            return Response({"error": "Unauthorized"}, status=status.HTTP_403_FORBIDDEN)

        try:
            user = User.objects.get(username=username)
        except User.DoesNotExist:
            return Response(
                {"error": "User not found"}, status=status.HTTP_404_NOT_FOUND
            )

        if user == request.user:
            return Response(
                {"error": "Cannot delete yourself"}, status=status.HTTP_400_BAD_REQUEST
            )

        user.delete()

        return Response(
            {"message": f"User {username} deleted successfully"},
            status=status.HTTP_200_OK,
        )
