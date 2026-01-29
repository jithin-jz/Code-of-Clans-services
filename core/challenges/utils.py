import qrcode
from PIL import Image, ImageDraw, ImageFont
from io import BytesIO
import os
from django.conf import settings


def generate_certificate_image(user_certificate):
    """
    Generates a certificate image for the given UserCertificate instance.
    """
    # 1. Setup Canvas (A4 Landscape-ish: 2000x1400)
    width, height = 2000, 1400
    background_color = (255, 255, 255)  # White
    border_color = (184, 134, 11)  # Dark Golden Rod

    image = Image.new("RGB", (width, height), background_color)
    draw = ImageDraw.Draw(image)

    # 2. Draw Fancy Border
    border_width = 40
    draw.rectangle(
        [(border_width, border_width), (width - border_width, height - border_width)],
        outline=border_color,
        width=15,
    )
    # Inner border
    draw.rectangle(
        [
            (border_width + 20, border_width + 20),
            (width - border_width - 20, height - border_width - 20),
        ],
        outline=border_color,
        width=5,
    )

    # 3. Load Fonts
    # We'll use default font if custom ones aren't available, but try to load a nice one if possible
    # For container environments, usually nice fonts need to be installed or vendored.
    # We will use basic PIL default for fail-safety if proper TTF paths aren't found.
    try:
        title_font = ImageFont.truetype(
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 100
        )
        text_font = ImageFont.truetype(
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 40
        )
        name_font = ImageFont.truetype(
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 80
        )
    except IOError:
        # Fallback for Windows Dev or minimal Linux
        title_font = ImageFont.load_default()
        text_font = ImageFont.load_default()
        name_font = ImageFont.load_default()

    # 4. Draw Content
    # Title
    draw.text(
        (width / 2, 200),
        "CERTIFICATE OF COMPLETION",
        fill="black",
        font=title_font,
        anchor="mm",
    )

    # Body
    draw.text(
        (width / 2, 400),
        "This certifies that",
        fill="gray",
        font=text_font,
        anchor="mm",
    )

    # User Name
    user_name = (
        user_certificate.user.username.upper()
    )  # Use Full Name if available in profile
    draw.text(
        (width / 2, 550), user_name, fill=border_color, font=name_font, anchor="mm"
    )

    # Course Info
    draw.text(
        (width / 2, 700),
        "Has successfully completed the",
        fill="black",
        font=text_font,
        anchor="mm",
    )
    draw.text(
        (width / 2, 800),
        "PYTHON MASTERY COURSE",
        fill="black",
        font=name_font,
        anchor="mm",
    )

    # Date
    date_str = user_certificate.issued_at.strftime("%B %d, %Y")
    draw.text(
        (width / 2, 900),
        f"Issued on: {date_str}",
        fill="gray",
        font=text_font,
        anchor="mm",
    )

    # 5. Signatures
    # CEO Signature
    draw.text((400, 1100), "Jithin", fill="black", font=name_font, anchor="mm")
    draw.line([(250, 1150), (550, 1150)], fill="black", width=5)
    draw.text((400, 1200), "CEO & Founder", fill="gray", font=text_font, anchor="mm")

    # Platform Name
    draw.text(
        (width - 400, 1100), "Code of Clans", fill="black", font=name_font, anchor="mm"
    )
    draw.line([(width - 550, 1150), (width - 250, 1150)], fill="black", width=5)
    draw.text((width - 400, 1200), "Platform", fill="gray", font=text_font, anchor="mm")

    # 6. QR Code
    # Link: https://YOUR_DOMAIN/certificate/verify/{uuid}
    # For dev: http://localhost:5173/certificate/verify/{uuid}
    verify_url = f"http://localhost:5173/certificate/verify/{user_certificate.id}"
    qr = qrcode.QRCode(box_size=10, border=4)
    qr.add_data(verify_url)
    qr.make(fit=True)
    qr_img = qr.make_image(fill_color="black", back_color="white")

    # Resize QR
    qr_size = 250
    qr_img = qr_img.resize((qr_size, qr_size))

    # Paste QR (Bottom Center)
    image.paste(qr_img, (int(width / 2 - qr_size / 2), 1050))

    # 7. Save to Buffer
    buffer = BytesIO()
    image.save(buffer, format="PNG")

    # Return a Django File object name
    from django.core.files.base import ContentFile

    return ContentFile(buffer.getvalue(), name=f"cert_{user_certificate.id}.png")
