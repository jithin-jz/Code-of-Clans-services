import uuid
from datetime import datetime, time, timedelta

from django.contrib.auth.models import User
from django.core.paginator import Paginator
from django.db import models
from django.db.models import Avg, Count, Sum
from django.utils import timezone
from django.utils.dateparse import parse_date, parse_datetime
from drf_spectacular.utils import OpenApiParameter, OpenApiTypes, extend_schema, inline_serializer
from rest_framework import serializers, status
from rest_framework.response import Response
from rest_framework.views import APIView

from challenges.models import Challenge, UserProgress
from notifications.models import Notification
from store.models import StoreItem
from users.models import UserProfile
from users.serializers import UserSerializer

from .models import AdminAuditLog
from .permissions import IsAdminUser, can_manage_user
from .serializers import (
    AdminAuditLogSerializer,
    AdminStatsSerializer,
    ChallengeAnalyticsSerializer,
    StoreAnalyticsSerializer,
    SystemIntegritySerializer,
)


def _request_ip(request):
    forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR")


def _request_id(request):
    return request.headers.get("X-Request-ID") or str(uuid.uuid4())


def _parse_bool(value):
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.lower() in {"1", "true", "yes", "on"}
    return False


def _parse_int(value, default, min_value=None, max_value=None):
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    if min_value is not None:
        parsed = max(min_value, parsed)
    if max_value is not None:
        parsed = min(max_value, parsed)
    return parsed


def _parse_datetime_filter(value, end_of_day=False):
    if not value:
        return None

    dt = parse_datetime(value)
    if dt:
        if timezone.is_naive(dt):
            dt = timezone.make_aware(dt, timezone.get_current_timezone())
        return dt

    d = parse_date(value)
    if not d:
        return None

    if end_of_day:
        dt = datetime.combine(d, time.max).replace(microsecond=0)
    else:
        dt = datetime.combine(d, time.min)
    return timezone.make_aware(dt, timezone.get_current_timezone())


def log_admin_action(admin, action, request=None, target_user=None, details=None):
    """Helper to record administrative actions in the audit log."""
    AdminAuditLog.objects.create(
        admin=admin,
        admin_username=admin.username if admin else "system",
        action=action,
        target_user=target_user,
        target_username=target_user.username if target_user else "",
        target_email=target_user.email if target_user else "",
        details=details or {},
        actor_ip=_request_ip(request) if request else None,
        user_agent=(request.headers.get("User-Agent", "")[:512] if request else ""),
        request_id=_request_id(request) if request else "",
    )


class AdminStatsView(APIView):
    """View to get admin dashboard statistics."""

    permission_classes = [IsAdminUser]

    @extend_schema(
        responses={
            200: AdminStatsSerializer,
            403: OpenApiTypes.OBJECT,
        },
        description="Get administration statistics including total users, active sessions, and economy totals.",
    )
    def get(self, request):
        total_users = User.objects.count()
        yesterday = timezone.now() - timedelta(days=1)
        active_sessions = User.objects.filter(last_login__gte=yesterday).count()
        oauth_logins = UserProfile.objects.exclude(
            provider__in=["email", "local"]
        ).count()
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

    permission_classes = [IsAdminUser]
    serializer_class = UserSerializer

    @extend_schema(
        parameters=[
            OpenApiParameter("search", str, OpenApiParameter.QUERY),
            OpenApiParameter("role", str, OpenApiParameter.QUERY, enum=["user", "staff", "superuser"]),
            OpenApiParameter("status", str, OpenApiParameter.QUERY, enum=["active", "blocked"]),
            OpenApiParameter("page", int, OpenApiParameter.QUERY, default=1),
            OpenApiParameter("page_size", int, OpenApiParameter.QUERY, default=25),
        ],
        responses={
            200: inline_serializer(
                name="AdminUserListResponse",
                fields={
                    "count": serializers.IntegerField(),
                    "page": serializers.IntegerField(),
                    "page_size": serializers.IntegerField(),
                    "total_pages": serializers.IntegerField(),
                    "results": UserSerializer(many=True),
                },
            ),
            403: OpenApiTypes.OBJECT,
        },
        description="List all users with filtering and pagination. Staff can see all non-staff/superuser users; Superusers can see everyone.",
    )
    def get(self, request):
        users = User.objects.select_related("profile").annotate(
            followers_total=Count("followers", distinct=True),
            following_total=Count("following", distinct=True),
        )
        if not request.user.is_superuser:
            users = users.filter(is_staff=False, is_superuser=False)

        search = (request.query_params.get("search") or "").strip()
        role = (request.query_params.get("role") or "").strip().lower()
        status_filter = (request.query_params.get("status") or "").strip().lower()
        page = _parse_int(request.query_params.get("page"), 1, min_value=1)
        page_size = _parse_int(
            request.query_params.get("page_size"), 25, min_value=1, max_value=100
        )

        if search:
            users = users.filter(
                models.Q(username__icontains=search)
                | models.Q(email__icontains=search)
                | models.Q(first_name__icontains=search)
                | models.Q(last_name__icontains=search)
            )

        if role == "user":
            users = users.filter(is_staff=False, is_superuser=False)
        elif role == "staff":
            users = users.filter(is_staff=True, is_superuser=False)
        elif role == "superuser":
            users = users.filter(is_superuser=True)

        if status_filter == "active":
            users = users.filter(is_active=True)
        elif status_filter == "blocked":
            users = users.filter(is_active=False)

        users = users.order_by("-date_joined", "id")

        paginator = Paginator(users, page_size)
        page_obj = paginator.get_page(page)
        serialized = UserSerializer(
            page_obj.object_list, many=True, context={"request": request}
        ).data

        return Response(
            {
                "count": paginator.count,
                "page": page_obj.number,
                "page_size": page_size,
                "total_pages": paginator.num_pages,
                "results": serialized,
            },
            status=status.HTTP_200_OK,
        )


class UserBlockToggleView(APIView):
    """View to toggle user active status."""

    permission_classes = [IsAdminUser]

    @extend_schema(
        request=inline_serializer(
            name="UserBlockRequest",
            fields={"reason": serializers.CharField(required=False)},
        ),
        responses={200: OpenApiTypes.OBJECT, 400: OpenApiTypes.OBJECT, 403: OpenApiTypes.OBJECT, 404: OpenApiTypes.OBJECT},
        description="Toggle a user's active status. Blocking a user prevents them from logging in.",
    )
    def post(self, request, username):
        try:
            user = User.objects.get(username=username)
        except User.DoesNotExist:
            return Response(
                {"error": "User not found"}, status=status.HTTP_404_NOT_FOUND
            )

        allowed, message = can_manage_user(request.user, user)
        if not allowed:
            return Response({"error": message}, status=status.HTTP_403_FORBIDDEN)

        reason = (request.data.get("reason") or "").strip()
        new_is_active = not user.is_active

        if user.is_superuser and not new_is_active:
            active_superusers = User.objects.filter(
                is_superuser=True, is_active=True
            ).count()
            if active_superusers <= 1:
                return Response(
                    {"error": "Cannot block the last active superuser account."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        previous_is_active = user.is_active
        user.is_active = new_is_active
        user.save(update_fields=["is_active"])

        log_admin_action(
            admin=request.user,
            action="TOGGLE_USER_BLOCK",
            target_user=user,
            request=request,
            details={
                "before": {"is_active": previous_is_active},
                "after": {"is_active": user.is_active},
                "reason": reason,
            },
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

    permission_classes = [IsAdminUser]

    @extend_schema(
        parameters=[OpenApiParameter("reason", str, OpenApiParameter.QUERY)],
        responses={200: OpenApiTypes.OBJECT, 400: OpenApiTypes.OBJECT, 403: OpenApiTypes.OBJECT, 404: OpenApiTypes.OBJECT},
        description="Permanently delete a user account. This action cannot be undone.",
    )
    def delete(self, request, username):
        try:
            user = User.objects.get(username=username)
        except User.DoesNotExist:
            return Response(
                {"error": "User not found"}, status=status.HTTP_404_NOT_FOUND
            )

        allowed, message = can_manage_user(request.user, user)
        if not allowed:
            return Response({"error": message}, status=status.HTTP_403_FORBIDDEN)

        if user.is_superuser:
            superuser_count = User.objects.filter(is_superuser=True).count()
            if superuser_count <= 1:
                return Response(
                    {"error": "Cannot delete the last superuser account."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        reason = (request.query_params.get("reason") or "").strip()
        target_email = user.email

        log_admin_action(
            admin=request.user,
            action="DELETE_USER",
            target_user=user,
            request=request,
            details={"username": username, "email": target_email, "reason": reason},
        )

        user.delete()
        return Response(
            {"message": f"User {username} deleted successfully"},
            status=status.HTTP_200_OK,
        )


class ChallengeAnalyticsView(APIView):
    """View to get detailed challenge performance analytics."""

    permission_classes = [IsAdminUser]

    @extend_schema(
        responses={200: ChallengeAnalyticsSerializer(many=True)},
        description="Get detailed challenge performance analytics including completion rates and average stars.",
    )
    def get(self, request):
        challenges = Challenge.objects.all()
        progress_summary = UserProgress.objects.values("challenge_id").annotate(
            total_attempts=Count("id"),
            completions=Count(
                "id",
                filter=models.Q(status=UserProgress.Status.COMPLETED),
            ),
            avg_stars=Avg(
                "stars",
                filter=models.Q(status=UserProgress.Status.COMPLETED),
            ),
        )
        summary_map = {row["challenge_id"]: row for row in progress_summary}
        analytics_data = []

        for challenge in challenges:
            summary = summary_map.get(challenge.id, {})
            total_attempts = summary.get("total_attempts", 0)
            completions = summary.get("completions", 0)
            avg_stars = summary.get("avg_stars") or 0

            analytics_data.append(
                {
                    "id": challenge.id,
                    "title": challenge.title,
                    "completions": completions,
                    "completion_rate": (
                        (completions / total_attempts * 100) if total_attempts > 0 else 0
                    ),
                    "avg_stars": avg_stars,
                    "is_personalized": challenge.created_for_user is not None,
                }
            )

        serializer = ChallengeAnalyticsSerializer(analytics_data, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


class StoreAnalyticsView(APIView):
    """View to get store economy and item popularity."""

    permission_classes = [IsAdminUser]

    @extend_schema(
        responses={200: StoreAnalyticsSerializer},
        description="Get store economy analytics, item popularity, and total XP revenue.",
    )
    def get(self, request):
        items = StoreItem.objects.annotate(purchase_count=Count("purchases")).order_by(
            "-purchase_count"
        )

        item_stats = [
            {
                "name": item.name,
                "category": item.category,
                "cost": item.cost,
                "sales": item.purchase_count,
                "revenue": item.purchase_count * item.cost,
            }
            for item in items
        ]

        total_revenue = sum(item["revenue"] for item in item_stats)
        data = {"items": item_stats, "total_xp_spent": total_revenue}
        serializer = StoreAnalyticsSerializer(data)
        return Response(serializer.data, status=status.HTTP_200_OK)


class GlobalNotificationView(APIView):
    """View to send notifications to all users."""

    permission_classes = [IsAdminUser]

    @extend_schema(
        request=inline_serializer(
            name="GlobalNotificationRequest",
            fields={
                "message": serializers.CharField(max_length=500),
                "include_staff": serializers.BooleanField(default=False),
                "reason": serializers.CharField(required=False),
            },
        ),
        responses={200: OpenApiTypes.OBJECT, 400: OpenApiTypes.OBJECT},
        description="Broadcast a notification to all active users.",
    )
    def post(self, request):
        verb = request.data.get("message")
        if not verb:
            return Response(
                {"error": "Message is required"}, status=status.HTTP_400_BAD_REQUEST
            )

        if len(verb) > 500:
            return Response(
                {"error": "Message too long (max 500 characters)"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        include_staff = _parse_bool(request.data.get("include_staff", False))
        users_qs = User.objects.filter(is_active=True).exclude(id=request.user.id)
        if not include_staff:
            users_qs = users_qs.filter(is_staff=False, is_superuser=False)

        recipient_ids = list(users_qs.values_list("id", flat=True))
        notifications = [
            Notification(recipient_id=user_id, actor=request.user, verb=verb)
            for user_id in recipient_ids
        ]
        Notification.objects.bulk_create(notifications, batch_size=1000)

        reason = (request.data.get("reason") or "").strip()
        log_admin_action(
            admin=request.user,
            action="SEND_GLOBAL_NOTIFICATION",
            request=request,
            details={
                "message": verb,
                "recipient_count": len(recipient_ids),
                "include_staff": include_staff,
                "reason": reason,
            },
        )

        return Response(
            {"message": f"Broadcast sent to {len(recipient_ids)} users"},
            status=status.HTTP_200_OK,
        )


class AdminAuditLogView(APIView):
    """View to retrieve administrative action logs."""

    permission_classes = [IsAdminUser]

    @extend_schema(
        parameters=[
            OpenApiParameter("action", str, OpenApiParameter.QUERY),
            OpenApiParameter("admin", str, OpenApiParameter.QUERY),
            OpenApiParameter("target", str, OpenApiParameter.QUERY),
            OpenApiParameter("search", str, OpenApiParameter.QUERY),
            OpenApiParameter("ordering", str, OpenApiParameter.QUERY, default="-timestamp"),
            OpenApiParameter("date_from", str, OpenApiParameter.QUERY),
            OpenApiParameter("date_to", str, OpenApiParameter.QUERY),
            OpenApiParameter("page", int, OpenApiParameter.QUERY, default=1),
            OpenApiParameter("page_size", int, OpenApiParameter.QUERY, default=50),
        ],
        responses={
            200: inline_serializer(
                name="AdminAuditLogResponse",
                fields={
                    "count": serializers.IntegerField(),
                    "page": serializers.IntegerField(),
                    "page_size": serializers.IntegerField(),
                    "total_pages": serializers.IntegerField(),
                    "results": AdminAuditLogSerializer(many=True),
                },
            )
        },
        description="Retrieve administrative action logs with advanced filtering and search.",
    )
    def get(self, request):
        logs = AdminAuditLog.objects.select_related("admin", "target_user").all()

        action = (request.query_params.get("action") or "").strip()
        admin_username = (request.query_params.get("admin") or "").strip()
        target_username = (request.query_params.get("target") or "").strip()
        search = (request.query_params.get("search") or "").strip()
        ordering = request.query_params.get("ordering", "-timestamp")

        date_from = _parse_datetime_filter(request.query_params.get("date_from"))
        date_to = _parse_datetime_filter(
            request.query_params.get("date_to"), end_of_day=True
        )

        limit = _parse_int(request.query_params.get("limit"), 50, 1, 500)
        offset = _parse_int(request.query_params.get("offset"), 0, 0, None)
        page_size = _parse_int(
            request.query_params.get("page_size"), limit, min_value=1, max_value=500
        )
        page = _parse_int(request.query_params.get("page"), 1, min_value=1)

        if "offset" in request.query_params or "limit" in request.query_params:
            page_size = limit
            page = (offset // max(limit, 1)) + 1

        if action:
            logs = logs.filter(action=action)
        if admin_username:
            logs = logs.filter(admin_username__icontains=admin_username)
        if target_username:
            logs = logs.filter(target_username__icontains=target_username)
        if search:
            logs = logs.filter(
                models.Q(action__icontains=search)
                | models.Q(admin_username__icontains=search)
                | models.Q(target_username__icontains=search)
                | models.Q(request_id__icontains=search)
            )
        if date_from:
            logs = logs.filter(timestamp__gte=date_from)
        if date_to:
            logs = logs.filter(timestamp__lte=date_to)

        allowed_ordering = {
            "timestamp",
            "-timestamp",
            "action",
            "-action",
            "admin_username",
            "-admin_username",
            "target_username",
            "-target_username",
        }
        if ordering not in allowed_ordering:
            ordering = "-timestamp"
        tie_breaker = "-id" if ordering.startswith("-") else "id"
        logs = logs.order_by(ordering, tie_breaker)

        paginator = Paginator(logs, page_size)
        page_obj = paginator.get_page(page)
        serializer = AdminAuditLogSerializer(page_obj.object_list, many=True)
        return Response(
            {
                "count": paginator.count,
                "page": page_obj.number,
                "page_size": page_size,
                "total_pages": paginator.num_pages,
                "results": serializer.data,
            },
            status=status.HTTP_200_OK,
        )


class SystemIntegrityView(APIView):
    """View to check core system health and counts."""

    permission_classes = [IsAdminUser]

    @extend_schema(
        responses={200: SystemIntegritySerializer},
        description="Get current collection counts for key system models.",
    )
    def get(self, request):
        data = {
            "users": User.objects.count(),
            "challenges": Challenge.objects.count(),
            "store_items": StoreItem.objects.count(),
            "notifications": Notification.objects.count(),
            "audit_logs": AdminAuditLog.objects.count(),
        }
        serializer = SystemIntegritySerializer(data)
        return Response(serializer.data, status=status.HTTP_200_OK)
