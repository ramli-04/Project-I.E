"""Django settings for cabinet_backend — Cabinet 2.0 MVP."""

from pathlib import Path

import sys
import os
import secrets
from celery.schedules import crontab

try:
    from .local_settings import POSTGRES_PASSWORD as _local_postgres_password
except ImportError:
    _local_postgres_password = ""

if getattr(sys, 'frozen', False):
    # PyInstaller creates a temp folder and stores path in _MEIPASS
    BASE_DIR = Path(sys._MEIPASS)
    # The actual folder containing the .exe
    RUNTIME_BASE = Path(sys.executable).parent
else:
    BASE_DIR = Path(__file__).resolve().parent.parent
    RUNTIME_BASE = BASE_DIR
SECRET_KEY = os.environ.get('DJANGO_SECRET_KEY')
if not SECRET_KEY:
    _key_path = Path(os.environ.get('DJANGO_SECRET_KEY_FILE', BASE_DIR.parent / '.runtime' / 'signing-key'))
    _key_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        _fd = os.open(_key_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError:
        pass
    else:
        with os.fdopen(_fd, 'w') as _key_file:
            _key_file.write(secrets.token_urlsafe(64))
    SECRET_KEY = _key_path.read_text().strip()
    if len(SECRET_KEY) < 48:
        raise RuntimeError('Provide a strong DJANGO_SECRET_KEY or persistent signing-key file.')

DEBUG = os.environ.get('DJANGO_DEBUG', '0') == '1'

ALLOWED_HOSTS = os.environ.get('DJANGO_ALLOWED_HOSTS', '.localhost,127.0.0.1,tenant.test.com,testserver').split(',')

# ---------- TENANT APPS ----------
SHARED_APPS = [
    "django_tenants",
    "customers",
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
    "corsheaders",
]

TENANT_APPS = [
    "api",
]

INSTALLED_APPS = list(SHARED_APPS) + [
    app for app in TENANT_APPS if app not in SHARED_APPS
]

TENANT_MODEL = "customers.Client"
TENANT_DOMAIN_MODEL = "customers.Domain"
PUBLIC_SCHEMA_NAME = "public"
DATABASE_ROUTERS = ("django_tenants.routers.TenantSyncRouter",)

# ---------- MIDDLEWARE ----------
MIDDLEWARE = [
    "django_tenants.middleware.main.TenantMainMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

# ---------- CORS (dev only — allow everything) ----------
CORS_ALLOW_ALL_ORIGINS = False
CORS_ALLOWED_ORIGIN_REGEXES = [r'^http://([a-z0-9-]+\.)?localhost:(5173|4173|8000)$']
CORS_ALLOW_METHODS = [
    "DELETE",
    "GET",
    "OPTIONS",
    "PATCH",
    "POST",
    "PUT",
]

# ---------- URL CONFIG ----------
ROOT_URLCONF = "cabinet_backend.urls"

# ---------- TEMPLATES ----------
TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "frontend_build"],     # Serve index.html from here
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

WSGI_APPLICATION = "cabinet_backend.wsgi.application"

# ---------- DATABASE (PostgreSQL with schema-based tenants) ----------
DATABASES = {
    "default": {
        "ENGINE": "django_tenants.postgresql_backend",
        "NAME": os.environ.get("POSTGRES_DB", "cabinet"),
        "USER": os.environ.get("POSTGRES_USER", "postgres"),
        "PASSWORD": os.environ.get("POSTGRES_PASSWORD", _local_postgres_password),
        "HOST": os.environ.get("POSTGRES_HOST", "127.0.0.1"),
        "PORT": os.environ.get("POSTGRES_PORT", "5432"),
    }
}

# ---------- PASSWORD VALIDATORS ----------
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# ---------- i18n ----------
LANGUAGE_CODE = "fr-fr"
TIME_ZONE = "Africa/Casablanca"
USE_I18N = True
USE_TZ = True

# ---------- STATIC FILES ----------
STATIC_URL = "/static/"
STATICFILES_DIRS = [BASE_DIR / "frontend_build"]   # Frontend assets served here

# ---------- DRF ----------
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'customers.authentication.PlatformBearerAuthentication',
        'rest_framework.authentication.SessionAuthentication',
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],
}

# ---------- DEFAULT PK ----------
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
PRIVATE_MEDIA_ROOT = Path(os.environ.get('PRIVATE_MEDIA_ROOT', BASE_DIR.parent / 'private_media'))
DATA_UPLOAD_MAX_MEMORY_SIZE = 30 * 1024 * 1024
FILE_UPLOAD_MAX_MEMORY_SIZE = 2 * 1024 * 1024
EXTERNAL_DELIVERY_ENABLED = os.environ.get('EXTERNAL_DELIVERY_ENABLED', '0') == '1'
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = os.environ.get('EMAIL_HOST', '')
EMAIL_PORT = int(os.environ.get('EMAIL_PORT', '587'))
EMAIL_HOST_USER = os.environ.get('EMAIL_HOST_USER', '')
EMAIL_HOST_PASSWORD = os.environ.get('EMAIL_HOST_PASSWORD', '')
EMAIL_USE_TLS = os.environ.get('EMAIL_USE_TLS', '1') == '1'
EMAIL_TIMEOUT = 10
DEFAULT_FROM_EMAIL = os.environ.get('DEFAULT_FROM_EMAIL', 'noreply@cabinet2.local')
WHATSAPP_SEND_URL = os.environ.get('WHATSAPP_SEND_URL', '')
WHATSAPP_ACCESS_TOKEN = os.environ.get('WHATSAPP_ACCESS_TOKEN', '')

# Native Django uses loopback; Compose overrides URLs for the worker container.
CELERY_BROKER_URL = os.environ.get(
    "CELERY_BROKER_URL", "redis://127.0.0.1:6379/0"
)
CELERY_RESULT_BACKEND = os.environ.get(
    "CELERY_RESULT_BACKEND", "redis://127.0.0.1:6379/1"
)
CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TASK_SERIALIZER = "json"
CELERY_RESULT_SERIALIZER = "json"
CELERY_RESULT_EXPIRES = 3600
CELERY_BROKER_CONNECTION_RETRY_ON_STARTUP = True
CELERY_BROKER_CONNECTION_TIMEOUT = 2
CELERY_BROKER_TRANSPORT_OPTIONS = {
    'socket_connect_timeout': 2, 'socket_timeout': 2,
    'visibility_timeout': 3600, 'max_retries': 0,
}
CELERY_TASK_PUBLISH_RETRY = False
OUTBOX_PUBLISH_ON_COMMIT = True
CELERY_TIMEZONE = TIME_ZONE
CELERY_BEAT_SCHEDULE = {
    'recover-pending-business-events': {
        'task': 'api.tasks.recover_pending_outbox_task',
        'schedule': 60.0,
        'options': {'expires': 55},
    },
    'refresh-monthly-billing-every-15-minutes': {
        'task': 'api.tasks.refresh_monthly_billing_catalog_task',
        'schedule': crontab(minute='*/15'),
        'options': {'expires': 840},
    },
}

CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.redis.RedisCache",
        "LOCATION": os.environ.get(
            "REDIS_CACHE_URL", "redis://127.0.0.1:6379/2"
        ),
        "KEY_PREFIX": "cabinet",
        "KEY_FUNCTION": "django_tenants.cache.make_key",
        "TIMEOUT": 300,
        "OPTIONS": {
            "socket_connect_timeout": 2,
            "socket_timeout": 2,
        },
    }
}
