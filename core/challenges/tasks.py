from celery import shared_task
from django.core.cache import cache
from django.utils import timezone
from django.db.models import Count, Q
from django.contrib.auth import get_user_model
from users.models import UserProfile
import logging

logger = logging.getLogger(__name__)

@shared_task
def update_leaderboard_cache():
    """
    Periodic task to calculate and cache the leaderboard.
    This runs every X minutes (configured in beat schedule) to reduce DB load.
    """
    User = get_user_model()
    logger.info("Starting leaderboard calculation task...")
    
    try:
        # Aggregation Logic (Copied from LeaderboardView)
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
        
        # Cache the result for 15 minutes (or however long until next run)
        cache.set('leaderboard_data', data, timeout=None) 
        logger.info("Leaderboard updated successfully.")
        
    except Exception as e:
        logger.exception(f"Leaderboard task failed: {str(e)}")
