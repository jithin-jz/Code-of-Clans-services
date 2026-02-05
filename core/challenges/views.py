from rest_framework import viewsets, status, decorators, serializers
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, IsAdminUser, AllowAny
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.db.models import Count, Q
from rest_framework.views import APIView
import logging
import os
import requests

logger = logging.getLogger(__name__)

from drf_spectacular.utils import extend_schema, OpenApiTypes, inline_serializer

from .models import Challenge, Hint, UserProgress
from .serializers import (
    ChallengeSerializer,
    HintSerializer,
    UserProgressSerializer,
)
from .services import ChallengeService
from users.models import UserProfile
from django.contrib.auth.models import User


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
            # Public view: only global challenges
            return Challenge.objects.filter(created_for_user__isnull=True)
        
        # Admin sees all? Or just standard + own? Let's say standard + own for now to keep things clean
        if user.is_staff:
            return Challenge.objects.all()

        return Challenge.objects.filter(
            Q(created_for_user__isnull=True) | Q(created_for_user=user)
        )

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
        # Professional Internal Bypass for Automation
        import os
        internal_key = os.getenv("INTERNAL_API_KEY")
        request_key = request.headers.get("X-Internal-API-Key")

        if internal_key and request_key == internal_key:
            return super().create(request, *args, **kwargs)
        
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
        
        # --- AI Level 1 Generation Trigger ---
        # If user is authenticated, not staff (optional check), and has NO challenges available
        if request.user.is_authenticated and not request.user.is_staff and not queryset.exists():
             logger.info(f"No challenges found for {request.user.username}. Triggering AI generation for Level 1.")
             
             import requests
             import time
             ai_url = os.getenv("AI_SERVICE_URL", "http://ai:8002")
             internal_key = os.getenv("INTERNAL_API_KEY")
             
             # Retry logic for AI service (may not be ready on startup)
             max_retries = 3
             for attempt in range(max_retries):
                 try:
                     # Synchronous call to AI service (background=false)
                     resp = requests.post(
                         f"{ai_url}/generate-level", 
                         params={"level": 1, "user_id": request.user.id, "background": "false"},
                         headers={"X-Internal-API-Key": internal_key},
                         timeout=25  # Wait up to 25s for generation
                     )
                     
                     if resp.status_code == 200:
                         logger.info("AI Level 1 generation successful. Refreshing queryset.")
                         # Refresh queryset to include the newly created level
                         queryset = self.filter_queryset(self.get_queryset())
                         break
                     else:
                         logger.error(f"AI Level 1 generation failed: {resp.text}")
                         break  # Don't retry on non-connection errors
                         
                 except requests.exceptions.ConnectionError as e:
                     if attempt < max_retries - 1:
                         logger.warning(f"AI service not ready (attempt {attempt + 1}/{max_retries}), retrying in 2s...")
                         time.sleep(2)
                     else:
                         logger.error(f"AI service unavailable after {max_retries} attempts: {e}")
                 except Exception as e:
                     logger.error(f"Error triggering AI Level 1: {e}")
                     break
        
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
        data["ai_hints_purchased"] = details["ai_hints_purchased"]

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

        # --- ENDLESS MODE TRIGGER ---
        # If passed, check if we need to generate the NEXT level.
        if passed and result["status"] in ["completed", "already_completed"]:
            try:
                current_order = challenge.order
                user = request.user
                user_id = user.id # Capture explicitly for thread safety
                
                # Check if next level exists FOR THIS USER
                # We check global (created_for_user__isnull=True) AND user-specific
                next_level_exists = Challenge.objects.filter(
                    Q(created_for_user__isnull=True) | Q(created_for_user=user),
                    order=current_order + 1
                ).exists()

                if not next_level_exists:
                    logger.info(f"Endless Mode: Triggering generation for Level {current_order + 1} for User {user.username}")
                    
                    # Fire and forget request to AI service
                    import threading
                    import requests
                    import os
                    
                    def trigger_ai():
                        ai_url = os.getenv("AI_SERVICE_URL", "http://ai:8002")
                        internal_key = os.getenv("INTERNAL_API_KEY")
                        # Pass user_id so AI creates personalized content
                        url = f"{ai_url}/generate-level?level={current_order + 1}&user_id={user_id}"
                        headers = {"X-Internal-API-Key": internal_key}
                        try:
                            # Use internal key to pass auth check
                            requests.post(url, headers=headers, timeout=1) 
                        except requests.exceptions.RequestException:
                            pass # Expected, as we don't wait for response
                            
                    threading.Thread(target=trigger_ai).start()
            except Exception as e:
                logger.error(f"Endless Mode Error: {e}")

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
        challenge = self.get_object()
        try:
            remaining_xp = ChallengeService.purchase_ai_assist(request.user, challenge)
            progress, _ = UserProgress.objects.get_or_create(user=request.user, challenge=challenge)
            return Response(
                {
                    "status": "purchased", 
                    "remaining_xp": remaining_xp,
                    "hints_purchased": progress.ai_hints_purchased
                },
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
