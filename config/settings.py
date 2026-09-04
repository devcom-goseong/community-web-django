"""
Django settings for the KDU Developer Community site.

The app does two things: it renders the public pages from content held in the
database and editable in the admin, and it receives the join / contact form,
storing each application and sending the two emails.

The static Netlify build is still the live site, in its own repository. This
runs alongside it until the team decides to switch over.

Everything environment-specific comes from environment variables. Nothing
secret is committed. See .env.example.
"""

import os
import sys
from pathlib import Path

import dj_database_url

BASE_DIR = Path(__file__).resolve().parent.parent


def env(name, default=None, required=False):
    value = os.environ.get(name, default)
    if required and not value:
        raise RuntimeError(
            f"{name} is not set. Copy .env.example to .env and fill it in, "
            f"or set it in the deployment environment."
        )
    return value


def env_bool(name, default=False):
    return str(os.environ.get(name, str(default))).strip().lower() in {"1", "true", "yes", "on"}


def env_list(name, default=""):
    return [item.strip() for item in os.environ.get(name, default).split(",") if item.strip()]


DEBUG = env_bool("DJANGO_DEBUG", False)

# In debug there is a throwaway key so a developer can start without ceremony.
# In production the app refuses to boot without a real one, which is the point.
SECRET_KEY = env("DJANGO_SECRET_KEY", "insecure-development-key" if DEBUG else None, required=not DEBUG)

ALLOWED_HOSTS = env_list("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1" if DEBUG else "")

# The public site posts here from another origin, so the origins that may do
# that are named explicitly rather than opened up.
PUBLIC_SITE_ORIGINS = env_list("PUBLIC_SITE_ORIGINS", "https://dev-comm.netlify.app")
CORS_ALLOWED_ORIGINS = PUBLIC_SITE_ORIGINS
CORS_ALLOW_CREDENTIALS = False
CSRF_TRUSTED_ORIGINS = env_list("CSRF_TRUSTED_ORIGINS", ",".join(PUBLIC_SITE_ORIGINS))

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "corsheaders",
    "content",
    "applications",
    "accounts",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"

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
    },
]

# SQLite locally so the app starts with no services running; Postgres in
# compose and in production, via DATABASE_URL.
DATABASES = {
    "default": dj_database_url.config(
        default=env("DATABASE_URL", f"sqlite:///{BASE_DIR / 'db.sqlite3'}"),
        conn_max_age=600,
        conn_health_checks=True,
    )
}

# The rate limiter needs a cache every worker shares, or it only limits the
# worker that happens to answer. The database gives us that without adding
# Redis for one counter. Run `manage.py createcachetable` after migrating.
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.db.DatabaseCache",
        "LOCATION": "applications_cache",
    }
}
if DEBUG or env_bool("DJANGO_LOCMEM_CACHE"):
    CACHES = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}

# Sign in with an email address rather than a username. The stock backend is
# kept behind it so `createsuperuser` accounts and the admin still work.
AUTHENTICATION_BACKENDS = [
    "accounts.backends.EmailBackend",
    "django.contrib.auth.backends.ModelBackend",
]

LOGIN_URL = "/account/sign-in/"
LOGIN_REDIRECT_URL = "/account/me/"
LOGOUT_REDIRECT_URL = "/"

# Three days, matching the confirmation link, so the two do not expire at
# noticeably different times and confuse someone working through their inbox.
PASSWORD_RESET_TIMEOUT = 3 * 24 * 60 * 60

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
     "OPTIONS": {"min_length": 12}},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "en-gb"
TIME_ZONE = env("DJANGO_TIME_ZONE", "Asia/Seoul")
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"

# The stylesheets, scripts and images live in this repository, under static/.
# They began life in the static site repository; if a change is made to the
# design in one place it has to be carried to the other by hand.
STATICFILES_DIRS = [BASE_DIR / "static"]
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"},
}

# The manifest storage refuses to build a URL for a file collectstatic has not
# hashed yet, which makes every template test depend on having run
# collectstatic first. Tests use the plain storage instead; CI still runs
# collectstatic as its own step, so the manifest path is verified separately.
if "test" in sys.argv:
    STORAGES["staticfiles"]["BACKEND"] = "django.contrib.staticfiles.storage.StaticFilesStorage"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# --- Security -------------------------------------------------------------
# nginx terminates TLS, so Django is told how to recognise a secure request.
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
X_FRAME_OPTIONS = "DENY"
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "strict-origin-when-cross-origin"

if not DEBUG:
    SECURE_SSL_REDIRECT = env_bool("DJANGO_SECURE_SSL_REDIRECT", True)
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SESSION_COOKIE_HTTPONLY = True
    SECURE_HSTS_SECONDS = int(env("DJANGO_HSTS_SECONDS", "31536000"))
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True

# --- Email ----------------------------------------------------------------
# The same variable names the Netlify function used, so whoever set them up
# once does not have to learn a second vocabulary.
EMAIL_BACKEND = env("DJANGO_EMAIL_BACKEND", "django.core.mail.backends.smtp.EmailBackend")
EMAIL_HOST = env("EMAIL_HOST", "smtp.gmail.com")
EMAIL_PORT = int(env("GMAIL_SMTP_PORT", "465"))
EMAIL_HOST_USER = env("GMAIL_USER", "")
EMAIL_HOST_PASSWORD = env("GMAIL_APP_PASSWORD", "")
EMAIL_USE_SSL = EMAIL_PORT == 465
EMAIL_USE_TLS = EMAIL_PORT == 587
EMAIL_TIMEOUT = int(env("EMAIL_TIMEOUT", "10"))

TEAM_NAME = "KDU Developer Community"
TEAM_INBOX = env("TEAM_INBOX", "") or EMAIL_HOST_USER
DEFAULT_FROM_EMAIL = f"{TEAM_NAME} <{EMAIL_HOST_USER}>" if EMAIL_HOST_USER else "webmaster@localhost"
SERVER_EMAIL = DEFAULT_FROM_EMAIL
PUBLIC_SITE_URL = env("PUBLIC_SITE_URL", "https://dev-comm.netlify.app")

# Where the join form posts. Same-origin here, so the front-end script needs no
# change whether the pages are served by Django or by the static site.
FORM_ENDPOINT = env("FORM_ENDPOINT", "/api/register")

# --- Form protection ------------------------------------------------------
MIN_FILL_SECONDS = float(env("MIN_FILL_SECONDS", "1.5"))
MAX_FILL_SECONDS = float(env("MAX_FILL_SECONDS", str(12 * 60 * 60)))
RATE_LIMIT_MAX = int(env("RATE_LIMIT_MAX", "5"))
RATE_LIMIT_WINDOW_SECONDS = int(env("RATE_LIMIT_WINDOW_SECONDS", "600"))

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {"plain": {"format": "%(levelname)s %(name)s %(message)s"}},
    "handlers": {"console": {"class": "logging.StreamHandler", "formatter": "plain"}},
    "root": {"handlers": ["console"], "level": env("DJANGO_LOG_LEVEL", "INFO")},
}
