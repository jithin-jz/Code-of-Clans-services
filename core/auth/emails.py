import logging

from django.core.mail import send_mail
from django.template.loader import render_to_string

logger = logging.getLogger(__name__)


def send_welcome_email(user):
    """
    Send a minimal welcome email to a newly registered user.
    """
    subject = "Welcome to Clash of Code"

    try:
        context = {"user": user}

        html_message = render_to_string("emails/welcome.html", context)

        plain_message = (
            f"Welcome to Clash of Code.\n\n"
            f"Hi {user.first_name or user.username},\n\n"
            "Your account is ready.\n"
            "Start with your first challenge.\n\n"
            "— Clash of Code"
        )

        send_mail(
            subject=subject,
            message=plain_message,
            from_email=None,  # Uses DEFAULT_FROM_EMAIL from settings
            recipient_list=[user.email],
            html_message=html_message,
            fail_silently=False,
        )

        logger.info("Welcome email sent to %s", user.email)

    except Exception:
        logger.exception("Failed to send welcome email to %s", user.email)


def send_otp_email(email, otp):
    """
    Send an OTP email for login verification.
    """
    subject = "Your Login Code - Clash of Code"

    try:
        context = {"otp": otp}

        html_message = render_to_string("emails/otp_login.html", context)

        plain_message = (
            f"Your Clash of Code login code is {otp}.\n\n"
            "This code expires in 10 minutes.\n"
            "If you didn’t request this, ignore this email."
        )

        send_mail(
            subject=subject,
            message=plain_message,
            from_email=None,  # Uses DEFAULT_FROM_EMAIL from settings
            recipient_list=[email],
            html_message=html_message,
            fail_silently=False,
        )

        logger.info("OTP email sent to %s", email)

    except Exception:
        logger.exception("Failed to send OTP email to %s", email)
