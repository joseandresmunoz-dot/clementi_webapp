"""
Django settings for config project.
"""

import os
from pathlib import Path

import environ

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# django-environ: lee variables desde .env
env = environ.Env(
    DEBUG=(bool, False),
)
env_file = BASE_DIR / ".env"
if env_file.exists():
    environ.Env.read_env(str(env_file))

# ---------------------------------------------------------------------------
# CORE
# ---------------------------------------------------------------------------
SECRET_KEY = env(
    "SECRET_KEY",
    default="django-insecure-CHANGE-ME-IN-PRODUCTION",
)
DEBUG = env("DEBUG", default=True)
ALLOWED_HOSTS = env.list("ALLOWED_HOSTS", default=["localhost", "127.0.0.1"])

# ---------------------------------------------------------------------------
# APPS
# ---------------------------------------------------------------------------
INSTALLED_APPS = [
    # Django
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.sites",
    # Third-party
    "allauth",
    "allauth.account",
    "allauth.socialaccount",
    "allauth.socialaccount.providers.google",
    "rest_framework",
    "corsheaders",
    "private_storage",
    # Local apps
    "patients.apps.PatientsConfig",
    "appointments.apps.AppointmentsConfig",
    "files_manager.apps.FilesManagerConfig",
]

SITE_ID = 1

# ---------------------------------------------------------------------------
# MIDDLEWARE
# ---------------------------------------------------------------------------
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "allauth.account.middleware.AccountMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"

# ---------------------------------------------------------------------------
# DATABASE — SQLite para desarrollo, PostgreSQL para producción
# ---------------------------------------------------------------------------
DATABASES = {
    "default": env.db(
        "DATABASE_URL",
        default=f"sqlite:///{BASE_DIR / 'db.sqlite3'}",
    ),
}

# ---------------------------------------------------------------------------
# AUTH / ALLAUTH
# ---------------------------------------------------------------------------
AUTHENTICATION_BACKENDS = [
    "django.contrib.auth.backends.ModelBackend",
    "allauth.account.auth_backends.AuthenticationBackend",
]

# django-allauth
ACCOUNT_LOGIN_METHODS = {"email"}
ACCOUNT_SIGNUP_FIELDS = ["email*", "password1*", "password2*"]
ACCOUNT_EMAIL_VERIFICATION = "optional"
SOCIALACCOUNT_AUTO_SIGNUP = True
SOCIALACCOUNT_EMAIL_AUTHENTICATION = True
SOCIALACCOUNT_EMAIL_AUTHENTICATION_AUTO_CONNECT = True
SOCIALACCOUNT_STORE_TOKENS = True
LOGIN_REDIRECT_URL = "/mi-panel/"
LOGOUT_REDIRECT_URL = "/"

# Google OAuth2 — las credenciales se leen desde .env
SOCIALACCOUNT_PROVIDERS = {
    "google": {
        "SCOPE": [
            "profile",
            "email",
            "https://www.googleapis.com/auth/calendar",
        ],
        "AUTH_PARAMS": {
            "access_type": "offline",
            "prompt": "consent",
        },
        "APP": {
            "client_id": env("GOOGLE_CLIENT_ID", default=""),
            "secret": env("GOOGLE_CLIENT_SECRET", default=""),
        },
    },
}

# ---------------------------------------------------------------------------
# PASSWORDS
# ---------------------------------------------------------------------------
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# ---------------------------------------------------------------------------
# I18N / L10N
# ---------------------------------------------------------------------------
LANGUAGE_CODE = "es-ar"
TIME_ZONE = "America/Argentina/Buenos_Aires"
USE_I18N = True
USE_TZ = True

# ---------------------------------------------------------------------------
# STATIC & MEDIA
# ---------------------------------------------------------------------------
STATIC_URL = "static/"
STATICFILES_DIRS = [
    ("images", BASE_DIR / "images"),
    BASE_DIR / "static",
]
STATIC_ROOT = BASE_DIR / "staticfiles"

MEDIA_URL = "media/"
MEDIA_ROOT = BASE_DIR / "media"

# ---------------------------------------------------------------------------
# PRIVATE STORAGE (archivos protegidos — no se sirven estáticamente)
# ---------------------------------------------------------------------------
PRIVATE_STORAGE_ROOT = BASE_DIR / "private_media"
PRIVATE_STORAGE_AUTH_FUNCTION = "files_manager.permissions.check_file_access"
PRIVATE_STORAGE_SERVER = "django"
PRIVATE_STORAGE_URL = "/private-media/"

# ---------------------------------------------------------------------------
# DJANGO REST FRAMEWORK
# ---------------------------------------------------------------------------
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework.authentication.SessionAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 20,
}

# ---------------------------------------------------------------------------
# CORS (desarrollo)
# ---------------------------------------------------------------------------
CORS_ALLOWED_ORIGINS = env.list(
    "CORS_ALLOWED_ORIGINS",
    default=["http://localhost:8000", "http://127.0.0.1:8000"],
)

# ---------------------------------------------------------------------------
# MISC
# ---------------------------------------------------------------------------
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# Google API — Credenciales de Service Account (para Calendar API server-side)
GOOGLE_CALENDAR_CREDENTIALS_FILE = env(
    "GOOGLE_CALENDAR_CREDENTIALS_FILE",
    default="",
)

# ---------------------------------------------------------------------------
# UPSUN (producción)
# ---------------------------------------------------------------------------
if os.getenv("PLATFORM_APPLICATION_NAME") is not None:
    DEBUG = False

    if os.getenv("PLATFORM_APP_DIR") is not None:
        STATIC_ROOT = os.path.join(os.getenv("PLATFORM_APP_DIR"), "staticfiles")

    if os.getenv("PLATFORM_PROJECT_ENTROPY") is not None:
        SECRET_KEY = os.getenv("PLATFORM_PROJECT_ENTROPY")

    if os.getenv("PLATFORM_ENVIRONMENT") is not None:
        DATABASES = {
            "default": {
                "ENGINE": "django.db.backends.postgresql",
                "NAME": os.getenv("DATABASE_PATH"),
                "USER": os.getenv("DATABASE_USERNAME"),
                "PASSWORD": os.getenv("DATABASE_PASSWORD"),
                "HOST": os.getenv("DATABASE_HOST"),
                "PORT": os.getenv("DATABASE_PORT"),
            },
        }

    ALLOWED_HOSTS = [
        host.strip()
        for host in os.getenv("DJANGO_ALLOWED_HOSTS", "").split(",")
        if host.strip()
    ] or [".platformsh.site"]

    STATICFILES_DIRS = [
        ("images", os.path.join(BASE_DIR, "images")),
        BASE_DIR / "static",
    ]
    PRIVATE_STORAGE_ROOT = BASE_DIR / "private_media"
    MEDIA_ROOT = BASE_DIR / "media"
