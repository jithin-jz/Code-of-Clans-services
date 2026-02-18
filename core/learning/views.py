import logging

from django.contrib.auth.models import User
from django.core.cache import cache
from django.db.models import Count, Q
from drf_spectacular.utils import OpenApiTypes, extend_schema, inline_serializer
from rest_framework import decorators, serializers, status, viewsets
from rest_framework.permissions import AllowAny, IsAdminUser, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from challenges.models import Challenge, UserProgress
from challenges.serializers import ChallengeSerializer
from challenges.services import ChallengeService
from users.models import UserProfile

logger = logging.getLogger(__name__)


class ChallengeViewSet(viewsets.ModelViewSet):
    queryset = Challenge.objects.all()
    serializer_class = ChallengeSerializer
    lookup_field = "slug"

    def get_queryset(self):
        user = self.request.user
        if not user.is_authenticated:
            return Challenge.objects.all()
        return Challenge.objects.all()

    def get_permissions(self):
        if self.action in ["internal_context", "internal_list", "create"]:
            permission_classes = [AllowAny]
        elif self.action in ["update", "partial_update", "destroy"]:
            permission_classes = [IsAdminUser]
        else:
            permission_classes = [IsAuthenticated]
        return [permission() for permission in permission_classes]

    def create(self, request, *args, **kwargs):
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
        queryset = self.filter_queryset(self.get_queryset())
        annotated_challenges = ChallengeService.get_annotated_challenges(
            request.user, queryset
        )

        data = []
        for item in annotated_challenges:
            serializer = self.get_serializer(item)
            challenge_data = serializer.data
            challenge_data["status"] = item.user_status
            challenge_data["stars"] = item.user_stars
            data.append(challenge_data)

        return Response(data)

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(instance)
        data = serializer.data

        details = ChallengeService.get_challenge_details(request.user, instance)
        data["status"] = details["status"]
        data["stars"] = details["stars"]
        data["ai_hints_purchased"] = details["ai_hints_purchased"]
        data["started_at"] = (
            details["started_at"].isoformat() if details["started_at"] else None
        )

        return Response(data)

    @extend_schema(
        request=inline_serializer(
            name="ChallengeSubmissionRequest",
            fields={
                "passed": serializers.BooleanField(),
            },
        ),
        responses={200: OpenApiTypes.OBJECT},
        description="Submit a challenge solution.",
    )
    @decorators.action(detail=True, methods=["post"])
    def submit(self, request, slug=None):
        challenge = self.get_object()
        passed = request.data.get("passed", False)
        result = ChallengeService.process_submission(request.user, challenge, passed)
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
                },
            ),
            402: OpenApiTypes.OBJECT,
        },
        description="Purchase AI assistance for a challenge.",
    )
    @decorators.action(detail=True, methods=["post"])
    def purchase_ai_assist(self, request, slug=None):
        challenge = self.get_object()
        user = request.user
        progress, _ = UserProgress.objects.get_or_create(user=user, challenge=challenge)

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
                    "message": f"AI hint purchased! {remaining_xp} XP remaining.",
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
                        "max_hints": 3,
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )
            return Response(
                {
                    "error": "Insufficient XP",
                    "detail": f"You need {next_cost} XP to purchase this hint, but you only have {user_xp} XP.",
                    "required_xp": next_cost,
                    "current_xp": user_xp,
                    "shortage": next_cost - user_xp,
                    "how_to_earn": "Complete challenges to earn XP (50 XP per challenge) or visit the shop.",
                },
                status=status.HTTP_402_PAYMENT_REQUIRED,
            )

    @extend_schema(
        request=inline_serializer(
            name="AIHintProxyRequest",
            fields={
                "user_code": serializers.CharField(),
                "hint_level": serializers.IntegerField(),
            },
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
        challenge = self.get_object()
        user = request.user
        progress, _ = UserProgress.objects.get_or_create(user=user, challenge=challenge)

        try:
            hint_level = int(request.data.get("hint_level", 1))
        except (TypeError, ValueError):
            return Response(
                {"error": "hint_level must be an integer between 1 and 3."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if hint_level < 1 or hint_level > 3:
            return Response(
                {"error": "hint_level must be between 1 and 3."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if progress.ai_hints_purchased < hint_level:
            return Response(
                {"error": f"AI Hint Level {hint_level} not purchased for this level."},
                status=status.HTTP_402_PAYMENT_REQUIRED,
            )

        # Enforce deterministic max of 3 generated hints per challenge:
        # one unique hint per level, cached per user/challenge/level.
        cache_key = f"ai_hint:{user.id}:{challenge.id}:level:{hint_level}"
        cached_hint = cache.get(cache_key)
        if cached_hint:
            return Response(
                {
                    "hint": cached_hint,
                    "hint_level": hint_level,
                    "max_hints": 3,
                    "cached": True,
                },
                status=status.HTTP_200_OK,
            )

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
            "Content-Type": "application/json",
        }

        try:
            resp = requests.post(f"{ai_url}/hints", json=payload, headers=headers, timeout=30)
            if resp.status_code == 200:
                body = resp.json()
                hint_text = body.get("hint")
                if isinstance(hint_text, str) and hint_text.strip():
                    cache.set(cache_key, hint_text, timeout=60 * 60 * 24 * 30)
                body.setdefault("hint_level", hint_level)
                body.setdefault("max_hints", 3)
                return Response(body)
            return Response(
                {"error": "AI Service Error", "details": resp.text},
                status=resp.status_code,
            )
        except requests.exceptions.RequestException as e:
            logger.error("AI Connection Error: %s", e)
            return Response(
                {"error": "AI Service Unavailable"},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

    @extend_schema(
        request=inline_serializer(
            name="AIAnalysisProxyRequest",
            fields={
                "user_code": serializers.CharField(),
            },
        ),
        responses={
            200: OpenApiTypes.OBJECT,
            403: OpenApiTypes.OBJECT,
        },
        description="Request an AI code analysis via Core Gateway.",
    )
    @decorators.action(detail=True, methods=["post"], url_path="ai-analyze")
    def ai_analyze(self, request, slug=None):
        challenge = self.get_object()

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
            "Content-Type": "application/json",
        }

        try:
            resp = requests.post(
                f"{ai_url}/analyze", json=payload, headers=headers, timeout=60
            )
            if resp.status_code == 200:
                return Response(resp.json())
            return Response(
                {"error": "AI Service Error", "details": resp.text},
                status=resp.status_code,
            )
        except requests.exceptions.RequestException as e:
            logger.error("AI Connection Error: %s", e)
            return Response(
                {"error": "AI Service Unavailable"},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
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
                },
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

        if not internal_key or request_key != internal_key:
            return Response({"error": "Unauthorized"}, status=status.HTTP_403_FORBIDDEN)

        try:
            challenge = Challenge.objects.get(slug=slug)
            return Response(
                {
                    "challenge_title": challenge.title,
                    "challenge_description": challenge.description,
                    "description": challenge.description,
                    "initial_code": challenge.initial_code,
                    "test_code": challenge.test_code,
                }
            )
        except Challenge.DoesNotExist:
            return Response(
                {"error": "Challenge not found"},
                status=status.HTTP_404_NOT_FOUND,
            )
        except Exception:
            return Response(
                {"error": "Internal error fetching context"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class LeaderboardView(APIView):
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
                many=True,
            )
        },
        description="Get global leaderboard.",
    )
    def get(self, request):
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

        cache.set("leaderboard_data", data, timeout=30)
        return Response(data)
