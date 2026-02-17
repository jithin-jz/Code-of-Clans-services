import logging
from datetime import datetime
from html import escape

from django.core.mail import send_mail
from django.conf import settings

logger = logging.getLogger(__name__)


def _display_name(user):
    return escape((user.first_name or user.username or "Coder").strip())


def _avatar_url(user):
    profile = getattr(user, "profile", None)
    avatar = getattr(profile, "avatar", None) if profile else None
    if not avatar:
        return ""
    try:
        url = avatar.url
    except Exception:
        return ""

    if url.startswith("http://") or url.startswith("https://"):
        return url

    base_url = settings.BACKEND_URL.rstrip("/")
    return f"{base_url}{url}"


def _otp_email_html(otp):
    safe_otp = escape(str(otp))
    year = datetime.now().year
    return f"""
<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Your Login Code</title>
</head>
<body style="margin:0;padding:0;background:#111827;color:#E5E7EB;font-family:Segoe UI,Arial,sans-serif;">
  <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="padding:24px 12px;">
    <tr>
      <td align="center">
        <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="max-width:560px;background:#1F2937;border:1px solid #374151;border-radius:14px;">
          <tr>
            <td style="padding:28px 24px 12px;text-align:center;">
              <div style="font-size:24px;font-weight:800;letter-spacing:.3px;color:#F9FAFB;">CLASH OF <span style="color:#F59E0B;">CODE</span></div>
            </td>
          </tr>
          <tr>
            <td style="padding:0 24px 10px;text-align:center;">
              <div style="font-size:16px;color:#D1D5DB;">Your one-time login code</div>
            </td>
          </tr>
          <tr>
            <td style="padding:12px 24px;text-align:center;">
              <div style="display:inline-block;font-size:34px;line-height:1;font-weight:800;letter-spacing:8px;padding:16px 22px;background:#111827;color:#FBBF24;border:1px dashed #4B5563;border-radius:10px;">
                {safe_otp}
              </div>
            </td>
          </tr>
          <tr>
            <td style="padding:8px 24px 26px;text-align:center;color:#9CA3AF;font-size:14px;">
              This code expires in 10 minutes. If you did not request it, ignore this email.
            </td>
          </tr>
          <tr>
            <td style="padding:14px 24px;border-top:1px solid #374151;text-align:center;color:#6B7280;font-size:12px;">
              &copy; {year} Clash of Code
            </td>
          </tr>
        </table>
      </td>
    </tr>
  </table>
</body>
</html>
"""


def _welcome_email_html(user):
    name = _display_name(user)
    avatar = _avatar_url(user)
    year = datetime.now().year

    avatar_block = (
        f'<img src="{escape(avatar)}" alt="Avatar" width="96" height="96" '
        'style="display:block;width:96px;height:96px;border-radius:50%;object-fit:cover;border:2px solid #374151;">'
        if avatar
        else f'<div style="width:96px;height:96px;border-radius:50%;background:#374151;color:#F9FAFB;display:flex;align-items:center;justify-content:center;font-size:34px;font-weight:700;">{name[:1]}</div>'
    )

    return f"""
<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Welcome to Clash of Code</title>
</head>
<body style="margin:0;padding:0;background:#111827;color:#E5E7EB;font-family:Segoe UI,Arial,sans-serif;">
  <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="padding:24px 12px;">
    <tr>
      <td align="center">
        <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="max-width:560px;background:#1F2937;border:1px solid #374151;border-radius:14px;">
          <tr>
            <td style="padding:28px 24px 16px;text-align:center;">
              <div style="font-size:24px;font-weight:800;color:#F9FAFB;">CLASH OF <span style="color:#F59E0B;">CODE</span></div>
            </td>
          </tr>
          <tr>
            <td style="padding:0 24px;text-align:center;">
              {avatar_block}
            </td>
          </tr>
          <tr>
            <td style="padding:16px 24px 8px;text-align:center;">
              <div style="font-size:22px;font-weight:700;color:#F9FAFB;">Welcome, <span style="color:#FBBF24;">{name}</span></div>
            </td>
          </tr>
          <tr>
            <td style="padding:0 24px 22px;text-align:center;color:#D1D5DB;font-size:15px;line-height:1.6;">
              Your account is ready. Start your first challenge and level up your coding skills.
            </td>
          </tr>
          <tr>
            <td style="padding:14px 24px;border-top:1px solid #374151;text-align:center;color:#6B7280;font-size:12px;">
              &copy; {year} Clash of Code
            </td>
          </tr>
        </table>
      </td>
    </tr>
  </table>
</body>
</html>
"""


def send_welcome_email(user):
    """
    Send a minimal welcome email to a newly registered user.
    """
    subject = "Welcome to Clash of Code"

    try:
        html_message = _welcome_email_html(user)

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
        html_message = _otp_email_html(otp)

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
