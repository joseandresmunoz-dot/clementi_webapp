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
    "pwa",
    "webpush",
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
ACCOUNT_ADAPTER = "patients.adapters.CustomAccountAdapter"
ALLAUTH_TRUSTED_PROXY_COUNT = 1
ACCOUNT_LOGIN_METHODS = {"email"}
ACCOUNT_SIGNUP_FIELDS = ["email*", "password1*", "password2*"]
ACCOUNT_EMAIL_VERIFICATION = "optional"
SOCIALACCOUNT_AUTO_SIGNUP = True
SOCIALACCOUNT_EMAIL_AUTHENTICATION = True
SOCIALACCOUNT_EMAIL_AUTHENTICATION_AUTO_CONNECT = True
SOCIALACCOUNT_STORE_TOKENS = True
LOGIN_REDIRECT_URL = "/mi-panel/"
LOGOUT_REDIRECT_URL = "/"

# Email de la Dra.: único usuario con dashboard de estadísticas exclusivo
DOCTOR_EMAIL = "romina.c.clementi@gmail.com"

# Email
DEFAULT_FROM_EMAIL = "Microbiota y Salud Integral <noreply@microbiotaysaludintegral.com>"
EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"

# Google OAuth2 — las credenciales se leen desde .env.
# El scope de calendar NO va acá: se pide solo a la Dra. en el flujo
# "Conectar Google Calendar" (para que el login de pacientes no dispare
# el aviso de "app no verificada" por scopes sensibles).
SOCIALACCOUNT_PROVIDERS = {
    "google": {
        "SCOPE": [
            "profile",
            "email",
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

# ---------------------------------------------------------------------------
# PWA (django-pwa)
# ---------------------------------------------------------------------------
PWA_APP_NAME = "Microbiota y Salud Integral"
PWA_APP_SHORT_NAME = "MicrobiotaSalud"
PWA_APP_DESCRIPTION = "Consultoría integral de microbiota y salud — Romina Clementi"
PWA_APP_THEME_COLOR = "#82459D"
PWA_APP_BACKGROUND_COLOR = "#F8F5FA"
PWA_APP_DISPLAY = "standalone"
PWA_APP_ORIENTATION = "portrait-primary"
PWA_APP_START_URL = "/"
PWA_APP_SCOPE = "/"
PWA_APP_DEBUG_MODE = False
PWA_SERVICE_WORKER_PATH = BASE_DIR / "static" / "sw.js"
PWA_SERVICE_WORKER_URL = "/sw.js"
PWA_APP_OFFLINE_URL = "/offline/"
PWA_APP_ICONS = [
    {"src": "/static/images/favicon/android-chrome-192x192.png", "sizes": "192x192", "type": "image/png"},
    {"src": "/static/images/favicon/android-chrome-512x512.png", "sizes": "512x512", "type": "image/png"},
    {"src": "/static/images/favicon/android-chrome-maskable-512x512.png", "sizes": "512x512", "type": "image/png", "purpose": "maskable"},
]
PWA_APP_ICONS_APPLE = [
    {"src": "/static/images/favicon/apple-touch-icon.png", "sizes": "180x180", "type": "image/png"},
]
PWA_APP_SCREENSHOTS = [
    {"src": "/static/images/pwa/pwa-screenshot-mobile.png", "sizes": "412x915", "type": "image/png", "form_factor": "narrow", "label": "Inicio en el celular"},
    {"src": "/static/images/pwa/pwa-screenshot-desktop.png", "sizes": "1280x800", "type": "image/png", "form_factor": "wide", "label": "Inicio en escritorio"},
]
PWA_APP_SHORTCUTS = [
    {"name": "Agendar consulta", "short_name": "Consultas", "url": "/#contacto", "icons": [
        {"src": "/static/images/favicon/android-chrome-192x192.png", "sizes": "192x192", "type": "image/png"},
    ]},
    {"name": "Test Epigenético", "short_name": "Test", "url": "/test-epigenetico/", "icons": [
        {"src": "/static/images/favicon/android-chrome-192x192.png", "sizes": "192x192", "type": "image/png"},
    ]},
    {"name": "Tienda", "short_name": "Tienda", "url": "/tienda/", "icons": [
        {"src": "/static/images/favicon/android-chrome-192x192.png", "sizes": "192x192", "type": "image/png"},
    ]},
]
PWA_APP_DIR = "auto"
PWA_APP_LANG = "es-AR"
PWA_APP_STATUS_BAR_COLOR = "default"

# ---------------------------------------------------------------------------
# WEBPUSH (django-webpush)
# ---------------------------------------------------------------------------
WEBPUSH_SETTINGS = {
    "VAPID_PUBLIC_KEY": "BIp6NZxaw76Opgi_kgdnyaA9zL5yE6Ac_DrZENmte7Po5ag_rvkkzncRpVH3n76AOktzQAEwFR9g7MQH3mi0KRw",
    "VAPID_PRIVATE_KEY": "-GAKRzRhhoYLmZf8r9dEcCR7VvtOegsygHGZBa4uk_g",
    "VAPID_ADMIN_EMAIL": "info@microbiotaysalud.com",
    "VAPID_CLAIMS": {"sub": "mailto:info@microbiotaysalud.com"},
}

# ---------------------------------------------------------------------------
# MERCADO PAGO (OAuth 2.0 + Checkout Pro)
# ---------------------------------------------------------------------------
MP_CLIENT_ID = env("MP_CLIENT_ID", default="")
MP_CLIENT_SECRET = env("MP_CLIENT_SECRET", default="")
MP_REDIRECT_URI = env("MP_REDIRECT_URI", default="")
MP_PUBLIC_KEY = env("MP_PUBLIC_KEY", default="")
# Access token directo de la app (modo "credenciales") usado como fallback
# cuando el vendedor aún no conecta su cuenta vía OAuth.
MP_ACCESS_TOKEN = env("MP_ACCESS_TOKEN", default="")
MP_AUTH_URL = env("MP_AUTH_URL", default="https://auth.mercadopago.com/authorization")
MP_TOKEN_URL = env("MP_TOKEN_URL", default="https://api.mercadopago.com/oauth/token")
MP_BACK_URLS = {
    "success": env("MP_BACK_SUCCESS", default="http://localhost:8000/tienda/"),
    "pending": env("MP_BACK_PENDING", default="http://localhost:8000/tienda/"),
    "failure": env("MP_BACK_FAILURE", default="http://localhost:8000/tienda/"),
}
MP_NOTIFICATION_URL = env("MP_NOTIFICATION_URL", default="")

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
# CORS
# ---------------------------------------------------------------------------
CORS_ALLOWED_ORIGINS = env.list(
    "CORS_ALLOWED_ORIGINS",
    default=["http://localhost:8000", "http://127.0.0.1:8000"],
)

# ---------------------------------------------------------------------------
# Seguridad HTTPS (no UPSUN/Platform.sh)
# ---------------------------------------------------------------------------
if not DEBUG and os.getenv("PLATFORM_APPLICATION_NAME") is None:
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    CSRF_TRUSTED_ORIGINS = [f"https://{host}" for host in ALLOWED_HOSTS if host]
    CSRF_COOKIE_SECURE = True
    SESSION_COOKIE_SECURE = True
    ACCOUNT_DEFAULT_HTTP_PROTOCOL = "https"
    CORS_ALLOWED_ORIGINS = [f"https://{host}" for host in ALLOWED_HOSTS if host]

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

    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    SECURE_SSL_REDIRECT = False

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

    CSRF_TRUSTED_ORIGINS = [
        f"https://{host}"
        for host in ALLOWED_HOSTS
        if host
    ]

    STATICFILES_DIRS = [
        ("images", os.path.join(BASE_DIR, "images")),
        BASE_DIR / "static",
    ]
    PRIVATE_STORAGE_ROOT = BASE_DIR / "private_media"
    MEDIA_ROOT = BASE_DIR / "media"
