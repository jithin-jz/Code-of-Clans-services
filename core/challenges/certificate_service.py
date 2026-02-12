"""
Certificate Service
Centralized logic for certificate eligibility, generation, and management.
"""

import logging
from django.conf import settings
from .models import UserProgress, UserCertificate

logger = logging.getLogger(__name__)


class CertificateService:
    """Service for managing user certificates"""
    
    # Total challenges required for certificate
    TOTAL_CHALLENGES = 53
    
    @staticmethod
    def is_eligible(user):
        """
        Check if user is eligible for a certificate.
        
        Args:
            user: Django User instance
            
        Returns:
            bool: True if user has completed required challenges
        """
        completed_count = CertificateService.get_completed_count(user)
        return completed_count >= CertificateService.TOTAL_CHALLENGES
    
    @staticmethod
    def get_completed_count(user):
        """
        Get the number of challenges user has completed.
        
        Args:
            user: Django User instance
            
        Returns:
            int: Number of completed challenges
        """
        return UserProgress.objects.filter(
            user=user,
            status=UserProgress.Status.COMPLETED
        ).count()
    
    @staticmethod
    def get_or_create_certificate(user):
        """
        Get existing certificate or create new one if eligible.
        
        Args:
            user: Django User instance
            
        Returns:
            UserCertificate: The certificate object
            
        Raises:
            ValueError: If user is not eligible
        """
        if not CertificateService.is_eligible(user):
            completed = CertificateService.get_completed_count(user)
            raise ValueError(
                f"User not eligible. Completed {completed}/{CertificateService.TOTAL_CHALLENGES} challenges."
            )
        
        # Get or create certificate
        certificate, created = UserCertificate.objects.get_or_create(
            user=user,
            defaults={'completion_count': CertificateService.get_completed_count(user)}
        )
        
        # Update completion count if it changed (user completed more challenges)
        if not created:
            current_count = CertificateService.get_completed_count(user)
            if current_count != certificate.completion_count:
                certificate.completion_count = current_count
                certificate.save(update_fields=['completion_count'])
                logger.info(
                    f"Updated certificate completion count for {user.username}: "
                    f"{certificate.completion_count} challenges"
                )
        else:
            logger.info(f"Created new certificate for {user.username}")
        
        return certificate
    
    @staticmethod
    def has_certificate(user):
        """
        Check if user has a certificate.
        
        Args:
            user: Django User instance
            
        Returns:
            bool: True if user has certificate
        """
        return hasattr(user, 'certificate')
    
    @staticmethod
    def get_eligibility_status(user):
        """
        Get detailed eligibility status for user.
        
        Args:
            user: Django User instance
            
        Returns:
            dict: Eligibility information
        """
        completed_count = CertificateService.get_completed_count(user)
        is_eligible = completed_count >= CertificateService.TOTAL_CHALLENGES
        has_cert = CertificateService.has_certificate(user)
        
        return {
            'eligible': is_eligible,
            'completed_challenges': completed_count,
            'required_challenges': CertificateService.TOTAL_CHALLENGES,
            'has_certificate': has_cert,
            'remaining_challenges': max(0, CertificateService.TOTAL_CHALLENGES - completed_count)
        }
