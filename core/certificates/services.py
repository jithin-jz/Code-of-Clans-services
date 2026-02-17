"""
Certificate Service
Centralized logic for certificate eligibility, generation, and management.
"""

import logging

from challenges.models import UserProgress

from .models import UserCertificate

logger = logging.getLogger(__name__)


class CertificateService:
    """Service for managing user certificates."""

    TOTAL_CHALLENGES = 53

    @staticmethod
    def is_eligible(user):
        completed_count = CertificateService.get_completed_count(user)
        return completed_count >= CertificateService.TOTAL_CHALLENGES

    @staticmethod
    def get_completed_count(user):
        return UserProgress.objects.filter(
            user=user, status=UserProgress.Status.COMPLETED
        ).count()

    @staticmethod
    def get_or_create_certificate(user):
        if not CertificateService.is_eligible(user):
            completed = CertificateService.get_completed_count(user)
            raise ValueError(
                f"User not eligible. Completed {completed}/{CertificateService.TOTAL_CHALLENGES} challenges."
            )

        certificate, created = UserCertificate.objects.get_or_create(
            user=user,
            defaults={"completion_count": CertificateService.get_completed_count(user)},
        )

        if not created:
            current_count = CertificateService.get_completed_count(user)
            if current_count != certificate.completion_count:
                certificate.completion_count = current_count
                certificate.save(update_fields=["completion_count"])
                logger.info(
                    "Updated certificate completion count for %s: %s challenges",
                    user.username,
                    certificate.completion_count,
                )
        else:
            logger.info("Created new certificate for %s", user.username)

        return certificate

    @staticmethod
    def has_certificate(user):
        return hasattr(user, "certificate")

    @staticmethod
    def get_eligibility_status(user):
        completed_count = CertificateService.get_completed_count(user)
        is_eligible = completed_count >= CertificateService.TOTAL_CHALLENGES
        has_cert = CertificateService.has_certificate(user)

        return {
            "eligible": is_eligible,
            "completed_challenges": completed_count,
            "required_challenges": CertificateService.TOTAL_CHALLENGES,
            "has_certificate": has_cert,
            "remaining_challenges": max(
                0, CertificateService.TOTAL_CHALLENGES - completed_count
            ),
        }

