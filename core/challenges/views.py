import logging
from django.shortcuts import get_object_or_404
from django.db.models import Q, Avg, Sum, Count, F, Prefetch
from django.utils import timezone
from django.contrib.auth.models import User
from rest_framework import viewsets, status, decorators, serializers
from rest_framework.decorators import action, permission_classes
from rest_framework.permissions import IsAuthenticated, AllowAny, IsAdminUser
from rest_framework.response import Response
from rest_framework.views import APIView
from drf_spectacular.utils import extend_schema, OpenApiTypes, inline_serializer
import json
from datetime import datetime, timedelta

from .models import Challenge, UserProgress, UserCertificate
from .services import ChallengeService
from .certificate_service import CertificateService
from .serializers import (
    ChallengeSerializer,
    UserProgressSerializer,
    UserCertificateSerializer,
)
from users.models import UserProfile

logger = logging.getLogger(__name__)



class ChallengeViewSet(viewsets.ModelViewSet):
    queryset = Challenge.objects.all()
    serializer_class = ChallengeSerializer
    lookup_field = "slug"

    def get_queryset(self):
        """
        Return global challenges + challenges created specifically for this user.
        """
        user = self.request.user
        if not user.is_authenticated:
            # All users see the same 50 manual tasks
            return Challenge.objects.all()
        
        # Authenticated users also see all challenges
        return Challenge.objects.all()

    def get_permissions(self):
        if self.action in ["internal_context", "internal_list", "create"]:
            # If creating, we still check the internal key in perform_create/dispatch or here
            # For simplicity, we'll allow AllowAny here and check key in the action
            permission_classes = [AllowAny]
        elif self.action in ["update", "partial_update", "destroy"]:
            permission_classes = [IsAdminUser]
        else:
            permission_classes = [IsAuthenticated]
        return [permission() for permission in permission_classes]

    def create(self, request, *args, **kwargs):

        # Fallback to Admin only for manual creation
        if not request.user.is_staff:
            return Response({"error": "Unauthorized"}, status=status.HTTP_403_FORBIDDEN)
            
        return super().create(request, *args, **kwargs)

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
        data["ai_hints_purchased"] = details["ai_hints_purchased"]
        data["started_at"] = details["started_at"].isoformat() if details["started_at"] else None

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

        if result["status"] == "failed":
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
                    "hints_purchased": serializers.IntegerField(),
                }
            ),
            402: OpenApiTypes.OBJECT,
        },
        description="Purchase AI assistance for a challenge.",
    )
    @decorators.action(detail=True, methods=["post"])
    def purchase_ai_assist(self, request, slug=None):
        """
        Purchase an AI hint for this challenge (XP cost: 10, 20, or 30).
        """
        challenge = self.get_object()
        user = request.user
        
        # Get or create progress
        progress, _ = UserProgress.objects.get_or_create(user=user, challenge=challenge)
        
        # Calculate cost for next hint
        current_count = progress.ai_hints_purchased
        next_cost = 10 * (current_count + 1)
        user_xp = user.profile.xp

        try:
            remaining_xp = ChallengeService.purchase_ai_assist(request.user, challenge)
            progress.refresh_from_db()
            return Response(
                {
                    "status": "purchased", 
                    "remaining_xp": remaining_xp,
                    "hints_purchased": progress.ai_hints_purchased,
                    "cost": next_cost,
                    "message": f"AI hint purchased! {remaining_xp} XP remaining."
                },
                status=status.HTTP_200_OK,
            )
        except PermissionError as e:
            error_message = str(e)
            
            if "Maximum" in error_message:
                return Response(
                    {
                        "error": "Maximum AI hints reached",
                        "detail": "You've already purchased all 3 AI hints for this challenge.",
                        "hints_purchased": current_count,
                        "max_hints": 3
                    },
                    status=status.HTTP_400_BAD_REQUEST
                )
            else:
                return Response(
                    {
                        "error": "Insufficient XP",
                        "detail": f"You need {next_cost} XP to purchase this hint, but you only have {user_xp} XP.",
                        "required_xp": next_cost,
                        "current_xp": user_xp,
                        "shortage": next_cost - user_xp,
                        "how_to_earn": "Complete challenges to earn XP (50 XP per challenge) or visit the shop."
                    },
                    status=status.HTTP_402_PAYMENT_REQUIRED
                )



    @extend_schema(
        request=inline_serializer(
            name="AIHintProxyRequest",
            fields={
                "user_code": serializers.CharField(),
                "hint_level": serializers.IntegerField(),
            }
        ),
        responses={
            200: OpenApiTypes.OBJECT,
            402: OpenApiTypes.OBJECT,
            403: OpenApiTypes.OBJECT,
        },
        description="Request an AI hint via Core Gateway (Auth & Payment Check).",
    )
    @decorators.action(detail=True, methods=["post"], url_path="ai-hint")
    def ai_hint(self, request, slug=None):
        """
        Proxies the hint request to the AI service AFTER verifying permissions.
        """
        challenge = self.get_object()
        user = request.user
        
        # 1. Check permissions (e.g., ai_hints_purchased)
        progress, _ = UserProgress.objects.get_or_create(user=user, challenge=challenge)
        
        hint_level = int(request.data.get("hint_level", 1))
        
        if progress.ai_hints_purchased < hint_level:
             return Response(
                {"error": f"AI Hint Level {hint_level} not purchased for this level."},
                status=status.HTTP_402_PAYMENT_REQUIRED
            )

        # 2. Proxy to AI Service
        import os
        import requests
        
        ai_url = os.getenv("AI_SERVICE_URL", "http://ai:8002")
        internal_key = os.getenv("INTERNAL_API_KEY")
        
        payload = {
            "user_code": request.data.get("user_code", ""),
            "challenge_slug": challenge.slug,
            "hint_level": request.data.get("hint_level", 1),
            "user_xp": user.profile.xp,
        }
        
        headers = {
            "X-Internal-API-Key": internal_key,
            "Content-Type": "application/json"
        }
        
        try:
            resp = requests.post(
                f"{ai_url}/hints",
                json=payload,
                headers=headers,
                timeout=30
            )
            
            if resp.status_code == 200:
                return Response(resp.json())
            else:
                return Response(
                    {"error": "AI Service Error", "details": resp.text},
                    status=resp.status_code
                )
        except requests.exceptions.RequestException as e:
            logger.error(f"AI Connection Error: {e}")
            return Response(
                {"error": "AI Service Unavailable"},
                status=status.HTTP_503_SERVICE_UNAVAILABLE
            )

    @extend_schema(
        request=inline_serializer(
            name="AIAnalysisProxyRequest",
            fields={
                "user_code": serializers.CharField(),
            }
        ),
        responses={
            200: OpenApiTypes.OBJECT,
            403: OpenApiTypes.OBJECT,
        },
        description="Request an AI code analysis via Core Gateway.",
    )
    @decorators.action(detail=True, methods=["post"], url_path="ai-analyze")
    def ai_analyze(self, request, slug=None):
        """
        Proxies the analysis request to the AI service.
        """
        challenge = self.get_object()
        user = request.user
        
        # 2. Proxy to AI Service
        import os
        import requests
        
        ai_url = os.getenv("AI_SERVICE_URL", "http://ai:8002")
        internal_key = os.getenv("INTERNAL_API_KEY")
        
        payload = {
            "user_code": request.data.get("user_code", ""),
            "challenge_slug": challenge.slug,
        }
        
        headers = {
            "X-Internal-API-Key": internal_key,
            "Content-Type": "application/json"
        }
        
        try:
            resp = requests.post(
                f"{ai_url}/analyze",
                json=payload,
                headers=headers,
                timeout=60 # Analysis might take longer
            )
            
            if resp.status_code == 200:
                return Response(resp.json())
            else:
                return Response(
                    {"error": "AI Service Error", "details": resp.text},
                    status=resp.status_code
                )
        except requests.exceptions.RequestException as e:
            logger.error(f"AI Connection Error: {e}")
            return Response(
                {"error": "AI Service Unavailable"},
                status=status.HTTP_503_SERVICE_UNAVAILABLE
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
                "challenge_title": challenge.title,
                "challenge_description": challenge.description,
                "description": challenge.description,  # backwards compatibility
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
            .order_by("-profile__xp", "-completed_count")[:100]
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
        cache.set("leaderboard_data", data, timeout=30)

        return Response(data)


class CertificateViewSet(viewsets.ViewSet):
    """API endpoints for certificate generation and verification"""
    
    permission_classes = [IsAuthenticated]
    
    @decorators.action(detail=False, methods=['get'])
    def my_certificate(self, request):
        """
        Get or generate certificate for the authenticated user.
        GET /api/certificates/my_certificate/
        """
        user = request.user
        
        # Check eligibility using CertificateService
        if not CertificateService.is_eligible(user):
            status_info = CertificateService.get_eligibility_status(user)
            return Response(
                {
                    "error": f"You need to complete {CertificateService.TOTAL_CHALLENGES} challenges to earn a certificate.",
                    "completed": status_info['completed_challenges'],
                    "required": status_info['required_challenges'],
                    "remaining": status_info['remaining_challenges']
                },
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            # Get or create certificate using service
            certificate = CertificateService.get_or_create_certificate(user)
        except ValueError as e:
            logger.error(f"Certificate eligibility check failed for {user.username}: {e}")
            return Response(
                {"error": str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            logger.error(f"Failed to create certificate record for {user.username}: {e}")
            return Response(
                {"error": "Failed to generate certificate. Please try again later."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
        
        serializer = UserCertificateSerializer(certificate, context={'request': request})
        return Response(serializer.data)
    
    @decorators.action(detail=False, methods=['get'], url_path='verify/(?P<certificate_id>[^/.]+)', permission_classes=[AllowAny])
    def verify(self, request, certificate_id=None):
        """
        Verify a certificate by its ID.
        GET /api/certificates/verify/<certificate_id>/
        Public endpoint - no authentication required.
        """
        try:
            certificate = get_object_or_404(UserCertificate, certificate_id=certificate_id)
            serializer = UserCertificateSerializer(certificate, context={'request': request})
            return Response({
                "valid": certificate.is_valid,
                "certificate": serializer.data
            })
        except Exception as e:
            logger.error(f"Certificate verification error: {e}")
            return Response(
                {"valid": False, "error": "Certificate not found"},
                status=status.HTTP_404_NOT_FOUND
            )
    

    
    @decorators.action(detail=False, methods=['get'])
    def check_eligibility(self, request):
        """
        Check if user is eligible for certificate.
        GET /api/certificates/check_eligibility/
        """
        user = request.user
        status_info = CertificateService.get_eligibility_status(user)
        return Response(status_info)
