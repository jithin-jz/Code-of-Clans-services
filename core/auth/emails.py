from django.conf import settings
from django.core.mail import send_mail
from django.template.loader import render_to_string
import logging

# Module-level logger for email-related events and errors
logger = logging.getLogger(__name__)


def send_welcome_email(user):
    """
    Send a welcome email to a newly registered user.

    - Renders an HTML email using a Django template
    - Provides a plain-text fallback for email clients
    - Logs success or failure for observability
    """
    subject = "Welcome to Code of Clans!"

    try:
        # Context passed to the HTML email template
        context = {"user": user}

        # Render HTML version of the email
        html_message = render_to_string("emails/welcome.html", context)

        # Plain-text fallback for clients that do not support HTML
        plain_message = (
            f"Welcome to Code of Clans!\n\n"
            f"Hi {user.first_name or user.username},\n"
            "We're excited to have you on board.\n"
            "Log in to start your journey."
        )

        # Send the email using Django's configured email backend
        send_mail(
            subject=subject,
            message=plain_message,
            from_email="Code of Clans <noreply@codeofclans.com>",
            recipient_list=[user.email],
            html_message=html_message,
            fail_silently=False,  # Raise exceptions on failure
        )

        # Log successful delivery
        logger.info("Welcome email sent to %s", user.email)

    except Exception:
        # Log full traceback if email sending fails
        logger.exception("Failed to send welcome email to %s", user.email)


def send_otp_email(email, otp):
    """
    Send an OTP email for login verification.
    """
    subject = "Your Login Code - Code of Clans"
    
    try:
        context = {"otp": otp}
        
        # HTML Message
        html_message = render_to_string("emails/otp_login.html", context)
        
        # Plain Text Fallback
        message = (
            f"Hello,\n\n"
            f"Your login code for Code of Clans is: {otp}\n\n"
            f"This code will expire in 10 minutes.\n"
            f"If you didn't request this code, please ignore this email."
        )
        
        send_mail(
            subject=subject,
            message=message,
            from_email="Code of Clans <noreply@codeofclans.com>",
            recipient_list=[email],
            fail_silently=False,
            html_message=html_message,
        )
        logger.info("OTP email sent to %s", email)
        
    except Exception:
        logger.exception("Failed to send OTP email to %s", email)

