from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import ChallengeViewSet, LeaderboardView, CertificateViewSet, VerifyCertificateView

router = DefaultRouter()
router.register(r'challenges', ChallengeViewSet)
router.register(r'certificates', CertificateViewSet, basename='certificates')

urlpatterns = [
    path('challenges/leaderboard/', LeaderboardView.as_view(), name='leaderboard'),
    path('certificates/verify/<uuid:certificate_id>/', VerifyCertificateView.as_view(), name='verify-certificate'),
    path('', include(router.urls)),
]
