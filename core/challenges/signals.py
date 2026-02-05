from django.db.models.signals import post_save
from django.dispatch import receiver
from users.models import UserProfile
from .services import ChallengeService

# @receiver(post_save, sender=UserProfile)
# def create_initial_challenge_signal(sender, instance, created, **kwargs):
#     """
#     Automatically creates the Level 1 challenge when a new UserProfile is created.
#     """
#     if created:
#         # Disabled in favor of AI generation on first access
#         # ChallengeService.create_initial_challenge(instance.user)
#         pass
