from django.contrib.auth.models import User
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from drf_spectacular.utils import extend_schema, OpenApiTypes, inline_serializer
from rest_framework import serializers
from django.utils import timezone
from datetime import timedelta
from django.db import models
from django.db.models import Sum, Avg, Count

from users.models import UserProfile
from users.serializers import UserSerializer
from .models import AdminAuditLog
from .serializers import (
    AdminStatsSerializer,
    AdminAuditLogSerializer,
    ChallengeAnalyticsSerializer,
    StoreAnalyticsSerializer,
    SystemIntegritySerializer,
)
from challenges.models import Challenge, UserProgress
from store.models import StoreItem, Purchase
from notifications.models import Notification

def log_admin_action(admin, action, target_user=None, details=None):
    """Helper to record administrative actions in the audit log."""
    AdminAuditLog.objects.create(
        admin=admin,
        action=action,
        target_user=target_user,
        details=details or {}
    )


class AdminStatsView(APIView):
    """View to get admin dashboard statistics."""

    permission_classes = [IsAuthenticated]

    @extend_schema(
        responses={
            200: AdminStatsSerializer,
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

        data = {
            "total_users": total_users,
            "active_sessions": active_sessions,
            "oauth_logins": oauth_logins,
            "total_gems": total_xp,
        }
        serializer = AdminStatsSerializer(data)
        return Response(serializer.data, status=status.HTTP_200_OK)


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

        log_admin_action(
            admin=request.user,
            action="TOGGLE_USER_BLOCK",
            target_user=user,
            details={"is_active": user.is_active}
        )

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

        log_admin_action(
            admin=request.user,
            action="DELETE_USER",
            target_user=user,
            details={"username": username}
        )

        user.delete()

        return Response(
            {"message": f"User {username} deleted successfully"},
            status=status.HTTP_200_OK,
        )


class ChallengeAnalyticsView(APIView):
    """View to get detailed challenge performance analytics."""
    permission_classes = [IsAuthenticated]

    @extend_schema(
        responses={200: ChallengeAnalyticsSerializer(many=True)},
        description="Get detailed challenge performance analytics.",
    )
    def get(self, request):
        if not (request.user.is_staff or request.user.is_superuser):
            return Response({"error": "Unauthorized"}, status=status.HTTP_403_FORBIDDEN)

        challenges = Challenge.objects.all()
        analytics_data = []

        for challenge in challenges:
            total_attempts = UserProgress.objects.filter(challenge=challenge).count()
            completions = UserProgress.objects.filter(
                challenge=challenge, status="COMPLETED"
            ).count()
            
            avg_stars = UserProgress.objects.filter(
                challenge=challenge, status="COMPLETED"
            ).aggregate(avg=Avg("stars"))["avg"] or 0

            analytics_data.append({
                "id": challenge.id,
                "title": challenge.title,
                "completions": completions,
                "completion_rate": (completions / total_attempts * 100) if total_attempts > 0 else 0,
                "avg_stars": avg_stars,
                "is_personalized": challenge.created_for_user is not None
            })

        serializer = ChallengeAnalyticsSerializer(analytics_data, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


class StoreAnalyticsView(APIView):
    """View to get store economy and item popularity."""
    permission_classes = [IsAuthenticated]

    @extend_schema(
        responses={200: StoreAnalyticsSerializer},
        description="Get store economy and item popularity analytics.",
    )
    def get(self, request):
        if not (request.user.is_staff or request.user.is_superuser):
            return Response({"error": "Unauthorized"}, status=status.HTTP_403_FORBIDDEN)

        items = StoreItem.objects.annotate(
            purchase_count=Count("purchases")
        ).order_by("-purchase_count")

        item_stats = [{
            "name": item.name,
            "category": item.category,
            "cost": item.cost,
            "sales": item.purchase_count,
            "revenue": item.purchase_count * item.cost
        } for item in items]

        total_revenue = sum(item["revenue"] for item in item_stats)

        data = {
            "items": item_stats,
            "total_xp_spent": total_revenue
        }
        serializer = StoreAnalyticsSerializer(data)
        return Response(serializer.data, status=status.HTTP_200_OK)


class GlobalNotificationView(APIView):
    """View to send notifications to all users."""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        if not (request.user.is_staff or request.user.is_superuser):
            return Response({"error": "Unauthorized"}, status=status.HTTP_403_FORBIDDEN)

        verb = request.data.get("message")
        if not verb:
            return Response({"error": "Message is required"}, status=status.HTTP_400_BAD_REQUEST)

        users = User.objects.all()
        notifications = [
            Notification(recipient=user, actor=request.user, verb=verb)
            for user in users
        ]
        Notification.objects.bulk_create(notifications)

        log_admin_action(
            admin=request.user,
            action="SEND_GLOBAL_NOTIFICATION",
            details={"message": verb, "recipient_count": users.count()}
        )

        return Response({"message": f"Broadcast sent to {users.count()} users"}, status=status.HTTP_200_OK)


class AdminAuditLogView(APIView):
    """View to retrieve administrative action logs."""
    permission_classes = [IsAuthenticated]

    @extend_schema(
        responses={200: AdminAuditLogSerializer(many=True)},
        description="Retrieve administrative action logs.",
    )
    def get(self, request):
        if not (request.user.is_staff or request.user.is_superuser):
            return Response({"error": "Unauthorized"}, status=status.HTTP_403_FORBIDDEN)

        logs = AdminAuditLog.objects.all()[:100]  # Last 100 actions
        serializer = AdminAuditLogSerializer(logs, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)



class SystemIntegrityView(APIView):
    """View to check core system health and counts."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not (request.user.is_staff or request.user.is_superuser):
            return Response({"error": "Unauthorized"}, status=status.HTTP_403_FORBIDDEN)

        data = {
            "users": User.objects.count(),
            "challenges": Challenge.objects.count(),
            "store_items": StoreItem.objects.count(),
            "notifications": Notification.objects.count(),
            "audit_logs": AdminAuditLog.objects.count()
        }
        serializer = SystemIntegritySerializer(data)
        return Response(serializer.data)


