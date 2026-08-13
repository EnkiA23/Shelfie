"""
Django settings for shelfie project.
"""

from pathlib import Path

import environ

BASE_DIR = Path(__file__).resolve().parent.parent

env = environ.Env(
    DEBUG=(bool, True),
    VLM_DRY_RUN=(bool, True),
    SCAN_USE_STUB=(bool, False),
    MAX_VLM_CALLS_PER_SCAN=(int, 10),
    MAX_UPLOAD_SIZE_MB=(int, 8),
    VLM_TIMEOUT_SECONDS=(int, 15),
    VLM_MAX_RETRIES=(int, 1),
    VLM_MAX_IMAGE_EDGE=(int, 512),
    DAILY_SPEND_CAP_USD=(float, 5.0),
    DAILY_VLM_CALLS_CAP=(int, 50),
    YOLO_MIN_CONFIDENCE=(float, 0.15),
    YOLO_IMAGE_SIZE=(int, 640),
    INCLUDE_CROP_THUMBNAILS=(bool, True),
    CROP_THUMBNAIL_MAX_EDGE=(int, 160),
    CONFIDENCE_THRESHOLD=(float, 0.85),
)

environ.Env.read_env(BASE_DIR / ".env")

SECRET_KEY = env("DJANGO_SECRET_KEY", default="dev-only-change-me")
DEBUG = env("DEBUG")
ALLOWED_HOSTS = env.list("ALLOWED_HOSTS", default=["127.0.0.1", "localhost", "0.0.0.0"])

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
    "corsheaders",
    "scanner",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "shelfie.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "shelfie.wsgi.application"

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",
    }
}

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

CORS_ALLOWED_ORIGINS = env.list(
    "CORS_ALLOWED_ORIGINS",
    default=["http://localhost:8081", "http://127.0.0.1:8081"],
)

REST_FRAMEWORK = {
    "DEFAULT_THROTTLE_CLASSES": ["rest_framework.throttling.ScopedRateThrottle"],
    "DEFAULT_THROTTLE_RATES": {
        "scan": env("SCAN_RATE_LIMIT", default="10/min"),
        "library_write": "30/min",
        "catalog_search": "60/min",
    },
}

APP_SHARED_TOKEN = env("APP_SHARED_TOKEN", default="")
VLM_PROVIDER = env("VLM_PROVIDER", default="gemini")
GEMINI_API_KEY = env("GEMINI_API_KEY", default="")
GEMINI_MODEL = env("GEMINI_MODEL", default="gemini-2.0-flash")
OPENAI_API_KEY = env("OPENAI_API_KEY", default="")
ANTHROPIC_API_KEY = env("ANTHROPIC_API_KEY", default="")
VLM_DRY_RUN = env("VLM_DRY_RUN")
SCAN_USE_STUB = env("SCAN_USE_STUB")
MAX_VLM_CALLS_PER_SCAN = env("MAX_VLM_CALLS_PER_SCAN")
MAX_UPLOAD_SIZE_MB = env("MAX_UPLOAD_SIZE_MB")
VLM_TIMEOUT_SECONDS = env("VLM_TIMEOUT_SECONDS")
VLM_MAX_RETRIES = env("VLM_MAX_RETRIES")
VLM_MAX_IMAGE_EDGE = env("VLM_MAX_IMAGE_EDGE")
DAILY_SPEND_CAP_USD = env("DAILY_SPEND_CAP_USD")
DAILY_VLM_CALLS_CAP = env("DAILY_VLM_CALLS_CAP")

DETECTOR_BACKEND = env("DETECTOR_BACKEND", default="auto")
YOLO_WEIGHTS = env("YOLO_WEIGHTS", default=str(BASE_DIR / "models" / "yolov8n.pt"))
YOLO_MIN_CONFIDENCE = env("YOLO_MIN_CONFIDENCE")
YOLO_IMAGE_SIZE = env("YOLO_IMAGE_SIZE")
INCLUDE_CROP_THUMBNAILS = env("INCLUDE_CROP_THUMBNAILS")
CROP_THUMBNAIL_MAX_EDGE = env("CROP_THUMBNAIL_MAX_EDGE")

# Scores at or above this are auto-accepted; everything else goes to human review.
CONFIDENCE_THRESHOLD = env("CONFIDENCE_THRESHOLD")
