from rest_framework import viewsets, status, decorators, serializers
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, IsAdminUser, AllowAny
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.db.models import Count, Q
from rest_framework.views import APIView
import logging

logger = logging.getLogger(__name__)

from drf_spectacular.utils import extend_schema, OpenApiTypes, inline_serializer

from .models import Challenge, Hint, UserProgress, UserCertificate
from .serializers import (
    ChallengeSerializer,
    HintSerializer,
    UserProgressSerializer,
    UserCertificateSerializer,
)
from .services import ChallengeService
from .utils import generate_certificate_image
from users.models import UserProfile
from django.contrib.auth.models import User


class ChallengeViewSet(viewsets.ModelViewSet):
    queryset = Challenge.objects.all()
    serializer_class = ChallengeSerializer
    lookup_field = "slug"

    def get_permissions(self):
        if self.action in ["internal_context", "internal_list"]:
            permission_classes = [AllowAny]
        elif self.action in ["create", "update", "partial_update", "destroy"]:
            permission_classes = [IsAdminUser]
        else:
            permission_classes = [IsAuthenticated]
        return [permission() for permission in permission_classes]

    @extend_schema(
        request=None,
        responses={200: ChallengeSerializer(many=True)},
        description="Internal endpoint to list all challenges for indexing.",
    )
    @decorators.action(detail=False, methods=["get"], url_path="internal-list")
    def internal_list(self, request):
        import os
        internal_key = os.getenv("INTERNAL_API_KEY")
        request_key = request.headers.get("X-Internal-API-Key")

        if not internal_key or request_key != internal_key:
             return Response({"error": "Unauthorized"}, status=status.HTTP_403_FORBIDDEN)

        challenges = Challenge.objects.all()
        serializer = ChallengeSerializer(challenges, many=True)
        return Response(serializer.data)

    def list(self, request, *args, **kwargs):
        """
        Return list of challenges annotated with user progress (status, stars).
        """
        queryset = self.filter_queryset(self.get_queryset())
        annotated_challenges = ChallengeService.get_annotated_challenges(
            request.user, queryset
        )

        # Serialize simply
        data = []
        for item in annotated_challenges:
            serializer = self.get_serializer(item)
            challenge_data = serializer.data
            challenge_data["status"] = item.user_status
            challenge_data["stars"] = item.user_stars
            data.append(challenge_data)

        return Response(data)

    def retrieve(self, request, *args, **kwargs):
        """
        Get challenge details including unlocked hints/status.
        """
        instance = self.get_object()
        serializer = self.get_serializer(instance)
        data = serializer.data

        details = ChallengeService.get_challenge_details(request.user, instance)

        data["status"] = details["status"]
        data["stars"] = details["stars"]
        data["unlocked_hints"] = HintSerializer(
            details["unlocked_hints"], many=True
        ).data
        data["ai_assist_used"] = details["ai_assist_used"]

        return Response(data)

    @extend_schema(
        request=inline_serializer(
            name="ChallengeSubmissionRequest",
            fields={
                "passed": serializers.BooleanField(),
            }
        ),
        responses={
            200: OpenApiTypes.OBJECT,
        },
        description="Submit a challenge solution.",
    )
    @decorators.action(detail=True, methods=["post"])
    def submit(self, request, slug=None):
        challenge = self.get_object()
        passed = request.data.get("passed", False)

        result = ChallengeService.process_submission(request.user, challenge, passed)

        # Determine status code
        # A failed test is a valid processed request, so 200 OK is often appropriate for "Result: Fail".
        # However, if passed=False means "Client says it failed", 200 is correct acknowledgment.

        if result["status"] == "failed":
            # Return 200 but indicating failure in body, OR 422 Unprocessable Entity
            # user requested 200 with status=failed is easier for frontend usually.
            return Response(result, status=status.HTTP_200_OK)

        return Response(result, status=status.HTTP_200_OK)

    @extend_schema(
        request=None,
        responses={
            200: inline_serializer(
                name="AIAssistPurchaseResponse",
                fields={
                    "status": serializers.CharField(),
                    "remaining_xp": serializers.IntegerField(),
                }
            ),
            402: OpenApiTypes.OBJECT,
        },
        description="Purchase AI assistance for a challenge.",
    )
    @decorators.action(detail=True, methods=["post"])
    def purchase_ai_assist(self, request, slug=None):
        challenge = self.get_object()
        try:
            remaining_xp = ChallengeService.purchase_ai_assist(request.user, challenge)
            return Response(
                {"status": "purchased", "remaining_xp": remaining_xp},
                status=status.HTTP_200_OK,
            )
        except PermissionError:
            return Response(
                {"error": "Insufficient XP"}, status=status.HTTP_402_PAYMENT_REQUIRED
            )

    @extend_schema(
        request=inline_serializer(
            name="UnlockHintRequest",
            fields={
                "hint_order": serializers.IntegerField(default=1),
            }
        ),
        responses={
            200: HintSerializer,
            402: OpenApiTypes.OBJECT,
            404: OpenApiTypes.OBJECT,
        },
        description="Unlock a hint for a challenge.",
    )
    @decorators.action(detail=True, methods=["post"])
    def unlock_hint(self, request, slug=None):
        challenge = self.get_object()
        hint_order = request.data.get("hint_order", 1)

        try:
            hint = ChallengeService.unlock_hint(request.user, challenge, hint_order)
            return Response(HintSerializer(hint).data, status=status.HTTP_200_OK)
        except Hint.DoesNotExist:
            return Response(
                {"error": "Hint not found"}, status=status.HTTP_404_NOT_FOUND
            )
        except PermissionError:
            return Response(
                {"error": "Insufficient XP"}, status=status.HTTP_402_PAYMENT_REQUIRED
            )

    @extend_schema(
        request=None,
        responses={
            200: inline_serializer(
                name="ChallengeContextResponse",
                fields={
                    "description": serializers.CharField(),
                    "initial_code": serializers.CharField(),
                    "test_code": serializers.CharField(),
                }
            ),
            403: OpenApiTypes.OBJECT,
        },
        description="Internal endpoint to fetch challenge context for AI service.",
    )
    @decorators.action(detail=True, methods=["get"], url_path="context")
    def internal_context(self, request, slug=None):
        import os
        internal_key = os.getenv("INTERNAL_API_KEY")
        request_key = request.headers.get("X-Internal-API-Key")

        logger.info(f"Internal context request for slug: {slug}")

        if not internal_key or request_key != internal_key:
             logger.warning(f"Unauthorized internal context request for slug: {slug}")
             return Response(
                {"error": "Unauthorized"}, status=status.HTTP_403_FORBIDDEN
            )

        try:
            # Using direct lookup to avoid potential issues with self.get_object() 
            # when called from internal services or with specific queryset filtering.
            challenge = Challenge.objects.get(slug=slug)
            logger.info(f"Successfully fetched context for slug: {slug}")
            return Response({
                "description": challenge.description,
                "initial_code": challenge.initial_code,
                "test_code": challenge.test_code,
            })
        except Challenge.DoesNotExist:
            logger.error(f"Challenge not found for internal context: {slug}")
            return Response(
                {"error": "Challenge not found"}, status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            logger.error(f"Error in internal_context for slug {slug}: {str(e)}")
            return Response(
                {"error": "Internal error fetching context"}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class CertificateViewSet(viewsets.ViewSet):
    permission_classes = [IsAuthenticated]
    serializer_class = UserCertificateSerializer

    def list(self, request):
        certs = UserCertificate.objects.filter(user=request.user)
        serializer = UserCertificateSerializer(certs, many=True)
        return Response(serializer.data)

    @extend_schema(
        request=None,
        responses={
            201: UserCertificateSerializer,
            400: OpenApiTypes.OBJECT,
        },
        description="Claim certificate if course is completed.",
    )
    @decorators.action(detail=False, methods=["post"])
    def claim(self, request):
        """
        Claim certificate if all levels are completed.
        """
        user = request.user

        # Check if already has certificate
        if UserCertificate.objects.filter(user=user).exists():
            return Response(
                {"error": "Certificate already claimed"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Check completion
        total_challenges = Challenge.objects.count()
        completed_challenges = UserProgress.objects.filter(
            user=user, status=UserProgress.Status.COMPLETED
        ).count()

        if completed_challenges < total_challenges and total_challenges > 0:
            return Response(
                {
                    "error": "Course not completed",
                    "completed": completed_challenges,
                    "total": total_challenges,
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Generate Certificate
        cert = UserCertificate(user=user)
        image_file = generate_certificate_image(cert)
        cert.certificate_image.save(image_file.name, image_file)
        cert.save()

        serializer = UserCertificateSerializer(cert)
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class VerifyCertificateView(APIView):
    permission_classes = [AllowAny]

    @extend_schema(
        responses={
            200: inline_serializer(
                name="CertificateVerificationResponse",
                fields={
                    "valid": serializers.BooleanField(),
                    "certificate": UserCertificateSerializer(),
                    "user": serializers.CharField(),
                    "issued_at": serializers.DateTimeField(),
                }
            ),
            404: OpenApiTypes.OBJECT,
            400: OpenApiTypes.OBJECT,
        },
        description="Verify a certificate by ID.",
    )
    def get(self, request, certificate_id):
        try:
            cert = UserCertificate.objects.get(id=certificate_id)
            serializer = UserCertificateSerializer(cert)
            return Response(
                {
                    "valid": True,
                    "certificate": serializer.data,
                    "user": cert.user.username,
                    "issued_at": cert.issued_at,
                }
            )
        except UserCertificate.DoesNotExist:
            return Response(
                {"valid": False, "error": "Invalid Certificate ID"},
                status=status.HTTP_404_NOT_FOUND,
            )
        except Exception as e:
            return Response(
                {"valid": False, "error": str(e)}, status=status.HTTP_400_BAD_REQUEST
            )


class LeaderboardView(APIView):
    """
    Returns the global leaderboard based on completed challenges.
    Ranked by:
    1. Number of completed challenges (descending)
    2. Total XP (descending)
    """

    permission_classes = [IsAuthenticated]

    @extend_schema(
        responses={
            200: inline_serializer(
                name="LeaderboardEntry",
                fields={
                    "username": serializers.CharField(),
                    "avatar": serializers.URLField(allow_null=True),
                    "completed_levels": serializers.IntegerField(),
                    "xp": serializers.IntegerField(),
                },
                many=True
            )
        },
        description="Get global leaderboard.",
    )
    def get(self, request):
        from django.core.cache import cache

        # Try to get cached leaderboard
        cached_data = cache.get("leaderboard_data")
        if cached_data:
            return Response(cached_data)

        users = (
            User.objects.annotate(
                completed_count=Count(
                    "challenge_progress",
                    filter=Q(challenge_progress__status=UserProgress.Status.COMPLETED),
                )
            )
            .select_related("profile")
            .filter(is_active=True, is_staff=False, is_superuser=False)
            .order_by("-completed_count", "-profile__xp")[:100]
        )

        data = []
        for user in users:
            try:
                profile = user.profile
                avatar_url = profile.avatar.url if profile.avatar else None
                xp = profile.xp
            except UserProfile.DoesNotExist:
                avatar_url = None
                xp = 0

            data.append(
                {
                    "username": user.username,
                    "avatar": avatar_url,
                    "completed_levels": user.completed_count,
                    "xp": xp,
                }
            )

        # Cache fallback result
        cache.set("leaderboard_data", data, timeout=300)

        return Response(data)
