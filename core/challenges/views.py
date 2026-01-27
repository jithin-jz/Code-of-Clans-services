from rest_framework import viewsets, status, decorators
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, IsAdminUser, AllowAny
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.db.models import Count, Q
from rest_framework.views import APIView
import logging

from .models import Challenge, Hint, UserProgress, UserCertificate
from .serializers import ChallengeSerializer, HintSerializer, UserProgressSerializer, UserCertificateSerializer
from .services import ChallengeService
from .utils import generate_certificate_image
from users.models import UserProfile
from django.contrib.auth.models import User

class ChallengeViewSet(viewsets.ModelViewSet):
    queryset = Challenge.objects.all()
    serializer_class = ChallengeSerializer
    lookup_field = 'slug'

    def get_permissions(self):
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            permission_classes = [IsAdminUser]
        else:
            permission_classes = [IsAuthenticated]
        return [permission() for permission in permission_classes]

    def list(self, request, *args, **kwargs):
        """
        Return list of challenges annotated with user progress (status, stars).
        """
        queryset = self.filter_queryset(self.get_queryset())
        annotated_challenges = ChallengeService.get_annotated_challenges(request.user, queryset)
        
        # Serialize simply
        data = []
        for item in annotated_challenges:
            serializer = self.get_serializer(item)
            challenge_data = serializer.data
            challenge_data['status'] = item.user_status
            challenge_data['stars'] = item.user_stars
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
        
        data['status'] = details['status']
        data['stars'] = details['stars']
        data['unlocked_hints'] = HintSerializer(details['unlocked_hints'], many=True).data
        data['ai_assist_used'] = details['ai_assist_used']
        
        return Response(data)

    @decorators.action(detail=True, methods=['post'])
    def submit(self, request, slug=None):
        challenge = self.get_object()
        passed = request.data.get('passed', False)
        
        result = ChallengeService.process_submission(request.user, challenge, passed)
        
        # Determine status code
        # A failed test is a valid processed request, so 200 OK is often appropriate for "Result: Fail".
        # However, if passed=False means "Client says it failed", 200 is correct acknowledgment.
        
        if result['status'] == 'failed':
             # Return 200 but indicating failure in body, OR 422 Unprocessable Entity
             # user requested 200 with status=failed is easier for frontend usually.
             return Response(result, status=status.HTTP_200_OK)
             
        return Response(result, status=status.HTTP_200_OK)

    @decorators.action(detail=True, methods=['post'])
    def purchase_ai_assist(self, request, slug=None):
        challenge = self.get_object()
        try:
            remaining_xp = ChallengeService.purchase_ai_assist(request.user, challenge)
            return Response({'status': 'purchased', 'remaining_xp': remaining_xp}, status=status.HTTP_200_OK)
        except PermissionError:
            return Response({'error': 'Insufficient XP'}, status=status.HTTP_402_PAYMENT_REQUIRED)

    @decorators.action(detail=True, methods=['post'])
    def unlock_hint(self, request, slug=None):
        challenge = self.get_object()
        hint_order = request.data.get('hint_order', 1)
        
        try:
            hint = ChallengeService.unlock_hint(request.user, challenge, hint_order)
            return Response(HintSerializer(hint).data, status=status.HTTP_200_OK)
        except Hint.DoesNotExist:
            return Response({'error': 'Hint not found'}, status=status.HTTP_404_NOT_FOUND)
        except PermissionError:
            return Response({'error': 'Insufficient XP'}, status=status.HTTP_402_PAYMENT_REQUIRED)


class CertificateViewSet(viewsets.ViewSet):
    permission_classes = [IsAuthenticated]

    def list(self, request):
        certs = UserCertificate.objects.filter(user=request.user)
        serializer = UserCertificateSerializer(certs, many=True)
        return Response(serializer.data)

    @decorators.action(detail=False, methods=['post'])
    def claim(self, request):
        """
        Claim certificate if all levels are completed.
        """
        user = request.user
        
        # Check if already has certificate
        if UserCertificate.objects.filter(user=user).exists():
            return Response({'error': 'Certificate already claimed'}, status=status.HTTP_400_BAD_REQUEST)

        # Check completion
        total_challenges = Challenge.objects.count()
        completed_challenges = UserProgress.objects.filter(
            user=user, 
            status=UserProgress.Status.COMPLETED
        ).count()

        if completed_challenges < total_challenges and total_challenges > 0:
             return Response({
                 'error': 'Course not completed', 
                 'completed': completed_challenges, 
                 'total': total_challenges
             }, status=status.HTTP_400_BAD_REQUEST)

        # Generate Certificate
        cert = UserCertificate(user=user)
        image_file = generate_certificate_image(cert)
        cert.certificate_image.save(image_file.name, image_file)
        cert.save()

        serializer = UserCertificateSerializer(cert)
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class VerifyCertificateView(APIView):
    permission_classes = [AllowAny]

    def get(self, request, certificate_id):
        try:
            cert = UserCertificate.objects.get(id=certificate_id)
            serializer = UserCertificateSerializer(cert)
            return Response({
                'valid': True,
                'certificate': serializer.data,
                'user': cert.user.username,
                'issued_at': cert.issued_at
            })
        except UserCertificate.DoesNotExist:
             return Response({'valid': False, 'error': 'Invalid Certificate ID'}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({'valid': False, 'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)


class LeaderboardView(APIView):
    """
    Returns the global leaderboard based on completed challenges.
    Ranked by:
    1. Number of completed challenges (descending)
    2. Total XP (descending)
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        from django.core.cache import cache
        
        # Try to get cached leaderboard
        cached_data = cache.get('leaderboard_data')
        if cached_data:
            return Response(cached_data)

        users = User.objects.annotate(
            completed_count=Count(
                'challenge_progress', 
                filter=Q(challenge_progress__status=UserProgress.Status.COMPLETED)
            )
        ).select_related('profile').filter(
            is_active=True, 
            is_staff=False, 
            is_superuser=False
        ).order_by('-completed_count', '-profile__xp')[:100]

        data = []
        for user in users:
            try:
                profile = user.profile
                avatar_url = profile.avatar.url if profile.avatar else None
                xp = profile.xp
            except UserProfile.DoesNotExist:
                avatar_url = None
                xp = 0

            data.append({
                'username': user.username,
                'avatar': avatar_url,
                'completed_levels': user.completed_count,
                'xp': xp,
            })
            
        # Cache fallback result
        cache.set('leaderboard_data', data, timeout=300) 
            
        return Response(data)
