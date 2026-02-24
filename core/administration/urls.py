from django.urls import path
from .views import (
    AdminStatsView,
    UserListView,
    UserBlockToggleView,
    UserDeleteView,
    ChallengeAnalyticsView,
    StoreAnalyticsView,
    GlobalNotificationView,
    AdminAuditLogView,
    SystemIntegrityView,
)

urlpatterns = [
    path("stats/", AdminStatsView.as_view(), name="admin_stats"),
    path(
        "analytics/challenges/",
        ChallengeAnalyticsView.as_view(),
        name="admin_challenge_analytics",
    ),
    path(
        "analytics/store/", StoreAnalyticsView.as_view(), name="admin_store_analytics"
    ),
    path("audit-logs/", AdminAuditLogView.as_view(), name="admin_audit_logs"),
    path(
        "notifications/broadcast/",
        GlobalNotificationView.as_view(),
        name="admin_broadcast",
    ),
    path("users/", UserListView.as_view(), name="admin_user_list"),
    path(
        "users/<str:username>/toggle-block/",
        UserBlockToggleView.as_view(),
        name="admin_toggle_block_user",
    ),
    path(
        "users/<str:username>/delete/",
        UserDeleteView.as_view(),
        name="admin_delete_user",
    ),
    path(
        "system/integrity/",
        SystemIntegrityView.as_view(),
        name="admin_system_integrity",
    ),
]
