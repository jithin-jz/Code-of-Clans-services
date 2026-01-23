from rest_framework import viewsets, status, decorators
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from .models import Challenge, Hint, UserProgress
from .serializers import ChallengeSerializer, HintSerializer, UserProgressSerializer
from django.shortcuts import get_object_or_404
from django.utils import timezone

from rest_framework.permissions import IsAuthenticated, IsAdminUser

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
        queryset = self.filter_queryset(self.get_queryset())
        
        # Get all progress for this user
        progress_dict = {
            p.challenge_id: p 
            for p in UserProgress.objects.filter(user=request.user)
        }
        
        data = []
        # Sort by order to determine implicit unlocking
        challenges = queryset.order_by('order')
        
        # Logic: First level is always unlocked. 
        # Subsequent levels unlocked if previous is COMPLETED.
        previous_completed = True 
        
        for challenge in challenges:
            serializer = self.get_serializer(challenge)
            item = serializer.data
            
            p = progress_dict.get(challenge.id)
            
            status = 'LOCKED'
            stars = 0
            
            if p:
                status = p.status
                stars = p.stars
            
            # If not explicitly unlocked/completed, check if it should be implicit
            if status == 'LOCKED' and previous_completed:
                status = 'UNLOCKED'
            
            # Update previous_completed for next iteration
            previous_completed = (status == 'COMPLETED')
            
            item['status'] = status
            item['stars'] = stars
            data.append(item)
            
        return Response(data)

    def get_object(self):
        # Support lookup by ID if numeric, else Slug
        lookup_url_kwarg = self.lookup_url_kwarg or self.lookup_field
        lookup_value = self.kwargs.get(lookup_url_kwarg)

        if lookup_value and lookup_value.isdigit():
            try:
                obj = Challenge.objects.get(pk=lookup_value)
                self.check_object_permissions(self.request, obj)
                return obj
            except Challenge.DoesNotExist:
                pass
        
        return super().get_object()

    def retrieve(self, request, *args, **kwargs):
        # Standard retrieve
        instance = self.get_object()
        serializer = self.get_serializer(instance)
        data = serializer.data
        
        # Determine user progress
        progress, created = UserProgress.objects.get_or_create(user=request.user, challenge=instance)
        
        # Check if Locked? (Logic: Previous challenge must be completed)
        # For simplicity, we might handle locking logic in list view or frontend.
        # Here we just return data.
        
        # Add unlocked hints
        unlocked_hints = progress.hints_unlocked.all()
        data['unlocked_hints'] = HintSerializer(unlocked_hints, many=True).data
        data['status'] = progress.status
        data['stars'] = progress.stars
        
        return Response(data)

    @decorators.action(detail=True, methods=['post'])
    def submit(self, request, slug=None):
        challenge = self.get_object()
        user = request.user
        
        passed = request.data.get('passed', False)
        
        if not passed:
            return Response({'status': 'failed'}, status=status.HTTP_400_BAD_REQUEST)

        # Update Progress
        progress, _ = UserProgress.objects.get_or_create(user=user, challenge=challenge)
        
        # Calculate Stars
        stars = 3
        if progress.ai_assist_used or progress.hints_unlocked.exists():
            stars -= 1
        
        # Could subtract based on time_taken if sent
        # time_taken = request.data.get('time_taken')
        # if time_taken and time_taken > challenge.time_limit:
        #     stars -= 1
        
        stars = max(1, stars) # Minimum 1 star if passed

        if progress.status != 'COMPLETED' or stars > progress.stars:
             # Reward only if first time completion or improved stars? 
             # Simplest: Reward XP only on first completion.
             
            newly_completed = progress.status != 'COMPLETED'
            
            progress.status = 'COMPLETED'
            progress.completed_at = timezone.now()
            progress.stars = max(progress.stars, stars) # Keep highest stars
            progress.save()
            
            # Award XP only on first completion
            if newly_completed:
                user.profile.xp += challenge.xp_reward
                user.profile.save()
            
            return Response({
                'status': 'completed' if newly_completed else 'already_completed',
                'xp_earned': challenge.xp_reward if newly_completed else 0,
                'stars': stars,
                'next_level_slug': self._get_next_level_slug(challenge)
            })
            
        return Response({'status': 'already_completed', 'message': 'No new XP awarded', 'stars': progress.stars})

    @decorators.action(detail=True, methods=['post'])
    def purchase_ai_assist(self, request, slug=None):
        challenge = self.get_object()
        cost = 10
        if request.user.profile.xp >= cost:
            request.user.profile.xp -= cost
            request.user.profile.save()
            
            # Record usage
            progress, _ = UserProgress.objects.get_or_create(user=request.user, challenge=challenge)
            progress.ai_assist_used = True
            progress.save()
            
            return Response({'status': 'purchased', 'remaining_xp': request.user.profile.xp})
        else:
            return Response({'error': 'Insufficient XP'}, status=status.HTTP_400_BAD_REQUEST)

    @decorators.action(detail=True, methods=['post'])
    def unlock_hint(self, request, slug=None):
        challenge = self.get_object()
        hint_order = request.data.get('hint_order', 1)
        
        hint = get_object_or_404(Hint, challenge=challenge, order=hint_order)
        progress, _ = UserProgress.objects.get_or_create(user=request.user, challenge=challenge)
        
        if progress.hints_unlocked.filter(id=hint.id).exists():
            return Response(HintSerializer(hint).data)
            
        if request.user.profile.xp >= hint.cost:
            request.user.profile.xp -= hint.cost
            request.user.profile.save()
            
            progress.hints_unlocked.add(hint)
            return Response(HintSerializer(hint).data)
        else:
            return Response({'error': 'Insufficient XP'}, status=status.HTTP_400_BAD_REQUEST)

    def _get_next_level_slug(self, current_challenge):
        next_challenge = Challenge.objects.filter(order__gt=current_challenge.order).order_by('order').first()
        return next_challenge.slug if next_challenge else None

from django.db.models import Count, Q
from rest_framework.views import APIView
from users.models import UserProfile
from django.contrib.auth.models import User

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

        # Fallback calculation (same logic as task)
        # In production, we might want to trigger the task asynchronously here
        # and return empty/stale data or wait, but for now we calculate synchronously on miss.
        users = User.objects.annotate(
            completed_count=Count(
                'challenge_progress', 
                filter=Q(challenge_progress__status='COMPLETED')
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
