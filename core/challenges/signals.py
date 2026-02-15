from django.db.models.signals import post_save
from django.dispatch import receiver
from users.models import UserProfile
from .services import ChallengeService
from .models import UserProgress
from .certificate_service import CertificateService
from .dynamo import dynamo_challenge_client
from users.dynamo import dynamo_activity_client
import logging

logger = logging.getLogger(__name__)

# ... (rest of the file)

@receiver(post_save, sender=UserProgress)
def track_progress_in_dynamo(sender, instance, created, **kwargs):
    """
    Shadow progress tracking in DynamoDB for fast gamification queries.
    """
    dynamo_challenge_client.update_progress(
        user_id=instance.user.id,
        challenge_slug=instance.challenge.slug,
        status=instance.status,
        stars=instance.stars
    )
    
    # Log contribution for heatmap if completed
    if instance.status == UserProgress.Status.COMPLETED:
        dynamo_activity_client.log_activity(instance.user.id)

# @receiver(post_save, sender=UserProfile)
# def create_initial_challenge_signal(sender, instance, created, **kwargs):
#     """
#     Automatically creates the Level 1 challenge when a new UserProfile is created.
#     """
#     if created:
#         # Disabled in favor of AI generation on first access
#         # ChallengeService.create_initial_challenge(instance.user)
#         pass


@receiver(post_save, sender=UserProgress)
def auto_generate_certificate(sender, instance, created, **kwargs):
    """
    Automatically generate certificate when user completes all challenges.
    
    Triggered after UserProgress is saved with COMPLETED status.
    """
    # Only trigger on completion
    if instance.status != UserProgress.Status.COMPLETED:
        return
    
    user = instance.user
    
    # Check if user is now eligible for certificate
    if not CertificateService.is_eligible(user):
        return
    
    # Check if certificate already exists
    if CertificateService.has_certificate(user):
        # Update completion count in case user completed more challenges
        try:
            certificate = user.certificate
            current_count = CertificateService.get_completed_count(user)
            if current_count != certificate.completion_count:
                certificate.completion_count = current_count
                certificate.save(update_fields=['completion_count'])
                logger.info(
                    f"Auto-updated certificate for {user.username}: "
                    f"{certificate.completion_count} challenges"
                )
        except Exception as e:
            logger.error(f"Failed to update certificate for {user.username}: {e}")
        return
    
    # Generate new certificate
    try:
        certificate = CertificateService.get_or_create_certificate(user)
        logger.info(
            f"Auto-generated certificate for {user.username} "
            f"(ID: {certificate.certificate_id})"
       )
    except ValueError as e:
        # User not eligible (shouldn't happen due to check above, but defensive)
        logger.warning(f"Certificate generation failed for {user.username}: {e}")
    except Exception as e:
        logger.error(
            f"Unexpected error generating certificate for {user.username}: {e}",
            exc_info=True
        )
