from django.urls import path
from .views import (
    AdminStatsView,
    UserListView,
    UserBlockToggleView,
    UserDeleteView,
)

urlpatterns = [
    path("stats/", AdminStatsView.as_view(), name="admin_stats"),
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
]
