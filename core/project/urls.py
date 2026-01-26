from django.contrib import admin
from django.urls import path, include
from drf_spectacular.views import (
    SpectacularAPIView,
    SpectacularRedocView,
    SpectacularSwaggerView,
)

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/auth/", include("auth.urls")),
    path("api/rewards/", include("rewards.urls")),
    path("api/profiles/", include("users.urls")),
    path("api/payments/", include("payments.urls")),
    path("api/store/", include("store.urls")),
    path("api/admin/", include("administration.urls")),
    path("api/", include("challenges.urls")),
    # Swagger Documentation routes
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path(
        "api/docs/",
        SpectacularSwaggerView.as_view(url_name="schema"),
        name="swagger-ui",
    ),
    path("api/redoc/", SpectacularRedocView.as_view(url_name="schema"), name="redoc"),
]

from django.conf import settings

if settings.DEBUG:
    from django.conf.urls.static import static
    from django.conf.urls.static import static

    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
