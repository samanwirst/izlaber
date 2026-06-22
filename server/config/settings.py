from pathlib import Path

import environ

BASE_DIR = Path(__file__).resolve().parent.parent
ROOT_DIR = BASE_DIR.parent

env = environ.Env(
    DJANGO_DEBUG=(bool, False),
    DJANGO_SECRET_KEY=(str, "unsafe-local-dev-key"),
    DJANGO_ALLOWED_HOSTS=(list, ["localhost", "127.0.0.1", "0.0.0.0"]),
    BOT_API_KEY=(str, ""),
    PARSER_API_KEY=(str, ""),
    ANALYTICS_COOKIE_ENABLED=(bool, False),
    ANALYTICS_COOKIE_NAME=(str, "izlaber_cid"),
    ANALYTICS_COOKIE_MAX_AGE_DAYS=(int, 180),
    ANALYTICS_HASH_IP=(bool, False),
    ANALYTICS_IP_HASH_SALT=(str, ""),
    USER_CONSENT_VERSION=(str, "2026-06-consent-v1"),
)
environ.Env.read_env(ROOT_DIR / ".env")
environ.Env.read_env(BASE_DIR / ".env")

SECRET_KEY = env("DJANGO_SECRET_KEY")
DEBUG = env("DJANGO_DEBUG")
ALLOWED_HOSTS = env("DJANGO_ALLOWED_HOSTS")

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
    "drf_spectacular",
    "apps.api_auth",
    "apps.catalog",
    "apps.crawling",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

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
    }
]

WSGI_APPLICATION = "config.wsgi.application"

DATABASE_URL = env("DATABASE_URL", default="")
if DATABASE_URL:
    DATABASES = {"default": env.db("DATABASE_URL")}
else:
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
STATIC_ROOT = BASE_DIR / "staticfiles"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

REST_FRAMEWORK = {
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.LimitOffsetPagination",
    "PAGE_SIZE": 20,
}

SPECTACULAR_SETTINGS = {
    "TITLE": "Izlaber Marketplace API",
    "DESCRIPTION": "Internal product catalog API for Telegram bot and parsers.",
    "VERSION": "0.1.0",
}

BOT_API_KEY = env("BOT_API_KEY")
PARSER_API_KEY = env("PARSER_API_KEY")
ANALYTICS_COOKIE_ENABLED = env("ANALYTICS_COOKIE_ENABLED")
ANALYTICS_COOKIE_NAME = env("ANALYTICS_COOKIE_NAME")
ANALYTICS_COOKIE_MAX_AGE_SECONDS = env("ANALYTICS_COOKIE_MAX_AGE_DAYS") * 24 * 60 * 60
ANALYTICS_HASH_IP = env("ANALYTICS_HASH_IP")
ANALYTICS_IP_HASH_SALT = env("ANALYTICS_IP_HASH_SALT") or SECRET_KEY
USER_CONSENT_VERSION = env("USER_CONSENT_VERSION")
