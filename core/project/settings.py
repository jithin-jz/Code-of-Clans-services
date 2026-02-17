import os
from pathlib import Path
from dotenv import load_dotenv
import dj_database_url
from django.core.exceptions import ImproperlyConfigured

# Base directory
BASE_DIR = Path(__file__).resolve().parent.parent

# Load environment variables
load_dotenv(BASE_DIR / ".env", override=False)

# Security
SECRET_KEY = os.getenv("SECRET_KEY")
if not SECRET_KEY:
    raise ImproperlyConfigured("SECRET_KEY is not set")

DEBUG = os.getenv("DEBUG", "false").lower() == "true"

def _parse_csv(value: str | None, default: list[str]) -> list[str]:
    if not value:
        return default
    return [item.strip() for item in value.split(",") if item.strip()]


ALLOWED_HOSTS = _parse_csv(
    os.getenv("ALLOWED_HOSTS"),
    ["localhost", "127.0.0.1", "core"],
)

# Applications
INSTALLED_APPS = [
    # "daphne",
    "django.contrib.admin",
    # "channels",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
    "corsheaders",
    "drf_spectacular",
    "auth",
    # 'chat',
    "rewards",
    "users",
    "xpoint",
    "payments",
    "store",
    "challenges",
    "learning",
    "certificates",
    "django_celery_beat",
    "django_celery_results",
    "administration",
    "posts",
    "notifications",
]

# Middleware
MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

# URLs
ROOT_URLCONF = "project.urls"

# Templates
TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    }
]

# WSGI
WSGI_APPLICATION = "project.wsgi.application"

# ASGI
# ASGI_APPLICATION = "project.asgi.application"

# Channels
# CHANNEL_LAYERS = {
#     "default": {
#         "BACKEND": "channels.layers.InMemoryChannelLayer"
#     }
# }

# Supabase

# DATABASE_URL = os.getenv("DATABASE_URL")
# if not DATABASE_URL:
#     raise ImproperlyConfigured("DATABASE_URL is not set")

# DATABASES = {
#     "default": dj_database_url.config(
#         default=DATABASE_URL,
#         conn_max_age=600,
#     )
# }

# pgadmin

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": os.getenv("DB_NAME"),
        "USER": os.getenv("DB_USER"),
        "PASSWORD": os.getenv("DB_PASSWORD"),
        "HOST": os.getenv("DB_HOST"),
        "PORT": os.getenv("DB_PORT"),
    }
}

# Validate database configuration
if not all([os.getenv("DB_NAME"), os.getenv("DB_USER"), os.getenv("DB_PASSWORD"), os.getenv("DB_HOST"), os.getenv("DB_PORT")]):
    raise ImproperlyConfigured("Database configuration incomplete. Ensure DB_NAME, DB_USER, DB_PASSWORD, DB_HOST, and DB_PORT are set.")


# Password validation
AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"
    },
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# Indian Timezone
LANGUAGE_CODE = "en-us"
TIME_ZONE = "Asia/Kolkata"
USE_I18N = True
USE_TZ = True

# Static files
STATIC_URL = "static/"

# Media files
MEDIA_URL = "/media/"
MEDIA_ROOT = os.path.join(BASE_DIR, "media")

# Backend URL (for absolute media paths)
BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000")

# Firebase
FIREBASE_SERVICE_ACCOUNT_PATH = os.getenv("FIREBASE_SERVICE_ACCOUNT_PATH")


# Cache Configuration
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.redis.RedisCache',
        'LOCATION': os.getenv("REDIS_URL", "redis://redis:6379/0"),
        'OPTIONS': {
            'db': 1,  # Use different Redis DB than Celery
        },
        'KEY_PREFIX': 'coc',
        'TIMEOUT': 300,  # Default timeout: 5 minutes
    }
}

# Default primary key
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# CORS
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:5173")
CORS_ALLOWED_ORIGINS = _parse_csv(
    os.getenv("CORS_ALLOWED_ORIGINS"),
    [
        FRONTEND_URL,
        "http://localhost:5173",
        "http://localhost:5174",
        "http://localhost:5175",
        "http://localhost:5176",
        "http://127.0.0.1:5173",
        "http://127.0.0.1:5174",
        "http://127.0.0.1:5175",
        "http://127.0.0.1:5176",
    ],
)
CORS_ALLOW_CREDENTIALS = True
CSRF_TRUSTED_ORIGINS = _parse_csv(
    os.getenv("CSRF_TRUSTED_ORIGINS"),
    [
        "http://localhost",
        "http://127.0.0.1",
    ],
)

# drf_spectacular

SPECTACULAR_SETTINGS = {
    "TITLE": "Clash of Code API",
    "DESCRIPTION": "API documentation for the Clash of Code gamification platform",
    "VERSION": "1.0.0",
    "SERVE_INCLUDE_SCHEMA": False,
}

# Django REST Framework
REST_FRAMEWORK = {
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "auth.authentication.JWTAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],
    "DEFAULT_THROTTLE_CLASSES": [
        "rest_framework.throttling.AnonRateThrottle",
        "rest_framework.throttling.UserRateThrottle",
    ],
    "DEFAULT_THROTTLE_RATES": {
        "anon": os.getenv("THROTTLE_ANON_RATE", "20/minute"),       # General anonymous limit
        "user": os.getenv("THROTTLE_USER_RATE", "100/minute"),      # General authenticated user limit
        "otp": os.getenv("THROTTLE_OTP_RATE", "5/minute"),          # Strict limit for OTP requests (SMS cost)
        "auth": os.getenv("THROTTLE_AUTH_RATE", "10/minute"),       # Login/register attempts (brute force protection)
        "store": os.getenv("THROTTLE_STORE_RATE", "30/minute"),     # Store/purchase operations
        "notifications": os.getenv("THROTTLE_NOTIFICATIONS_RATE", "180/minute"),  # Notification polling/read operations
        "sensitive": os.getenv("THROTTLE_SENSITIVE_RATE", "5/minute"),   # Password reset, email change
        "burst": os.getenv("THROTTLE_BURST_RATE", "10/second"),      # Short burst protection
    },
}

# JWT - RS256 Asymmetric Configuration
JWT_ALGORITHM = "RS256"

# Private key for signing tokens (keep secure!)
JWT_PRIVATE_KEY = os.getenv("JWT_PRIVATE_KEY", "").replace("\\n", "\n")

# Public key for verifying tokens (can be shared with other services)
JWT_PUBLIC_KEY = os.getenv("JWT_PUBLIC_KEY", "").replace("\\n", "\n")

JWT_ACCESS_TOKEN_LIFETIME = 60 * 60
JWT_REFRESH_TOKEN_LIFETIME = 60 * 60 * 24 * 7

# HttpOnly JWT cookie settings
JWT_COOKIE_SECURE = os.getenv("JWT_COOKIE_SECURE", "false").lower() == "true"
JWT_COOKIE_SAMESITE = os.getenv("JWT_COOKIE_SAMESITE", "Lax")
JWT_ACCESS_COOKIE_NAME = os.getenv("JWT_ACCESS_COOKIE_NAME", "access_token")
JWT_REFRESH_COOKIE_NAME = os.getenv("JWT_REFRESH_COOKIE_NAME", "refresh_token")

if JWT_COOKIE_SECURE:
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

# OAuth
GITHUB_CLIENT_ID = os.getenv("GITHUB_CLIENT_ID")
GITHUB_CLIENT_SECRET = os.getenv("GITHUB_CLIENT_SECRET")
GITHUB_REDIRECT_URI = f"{FRONTEND_URL}/auth/github/callback"

GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET")
GOOGLE_REDIRECT_URI = f"{FRONTEND_URL}/auth/google/callback"

# Email Configuration — AWS SES
EMAIL_BACKEND = "django_ses.SESBackend"
AWS_SES_REGION_NAME = os.getenv("AWS_SES_REGION", "ap-south-1")
AWS_SES_REGION_ENDPOINT = f"email.{AWS_SES_REGION_NAME}.amazonaws.com"
DEFAULT_FROM_EMAIL = os.getenv("DEFAULT_FROM_EMAIL", "jzdieheart@gmail.com")
OTP_EMAIL_ASYNC = os.getenv("OTP_EMAIL_ASYNC", "false" if DEBUG else "true").lower() == "true"

# Razorpay
RAZORPAY_KEY_ID = os.environ.get("RAZORPAY_KEY_ID")
RAZORPAY_KEY_SECRET = os.environ.get("RAZORPAY_KEY_SECRET")


# Celery Configuration
CELERY_BROKER_URL = os.getenv("REDIS_URL", "redis://redis:6379/0")
CELERY_RESULT_BACKEND = "django-db"
CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TASK_SERIALIZER = "json"
CELERY_RESULT_SERIALIZER = "json"
CELERY_TIMEZONE = TIME_ZONE

# Celery Beat
CELERY_BEAT_SCHEDULER = "django_celery_beat.schedulers:DatabaseScheduler"

CELERY_BEAT_SCHEDULE = {
    "update-leaderboard-every-5-minutes": {
        "task": "learning.tasks.update_leaderboard_cache",
        "schedule": 300.0,  # 5 minutes
    },
}
