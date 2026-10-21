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


def _read_env_file(path=None, required=False):
    """Load BASE_DIR/.env into the environment, if it is there.

    The error below tells people to copy .env.example to .env, and until this
    existed nothing read the file, so they did exactly as they were told and
    the app still refused to start. Running from an IDE made it worse: a run
    configuration has no shell to have sourced anything.

    Real environment variables win. In production systemd supplies them through
    EnvironmentFile and there is no .env on the server, so this does nothing
    there. No dependency: the format is KEY=value, which does not need one.

    DJANGO_ENV_FILE names another file instead. The deploy uses it to hand the
    server's own env file, the one systemd reads, to the management commands.
    It used to source that file in bash, and bash and systemd disagree about
    it: a value with a space and no quotes is one value to systemd, but bash
    runs everything after the space as a command, which stopped a release
    half-way. Read here, the commands see what the running site sees. A file
    named that way must be readable, because migrating without the site's
    settings is worse than not migrating.
    """
    if path is None:
        named = os.environ.get("DJANGO_ENV_FILE")
        path = BASE_DIR / named if named else BASE_DIR / ".env"
        required = required or bool(named)
    try:
        lines = Path(path).read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeDecodeError) as exc:
        if required:
            raise RuntimeError(f"The env file {path} cannot be read: {exc}") from exc
        return
    for line in lines:
        line = line.strip()
        # systemd treats ; as a comment as well as #.
        if not line or line[0] in "#;" or "=" not in line:
            continue
        name, _, value = line.partition("=")
        name = name.strip()
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        os.environ.setdefault(name, value)


_read_env_file()


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
    "django.contrib.sitemaps",
    "corsheaders",
    "content",
    "applications",
    "accounts",
    "events",
    "posters",
    "vault",
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
    # Last, so it sits closest to the views and sees what they answered.
    "config.login_throttle.SignInThrottle",
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
                # The site settings and the platform links, on every page. A
                # context processor rather than something each view passes, so
                # the rule that invite links are for members cannot be forgotten
                # by a view written later.
                "content.context_processors.site",
                # Search-engine metadata (verification token + JSON-LD). Kept
                # apart from `site` so its per-request JSON building is easy to
                # skip for the admin.
                "content.context_processors.seo",
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

# Fourteen days. This governs both the "forgotten password" link and the
# set-a-password link that goes out when the team accepts someone (their only
# way in — see accounts.services.accept_applications), so it is generous enough
# that an invitation does not lapse before a new member gets to their inbox.
PASSWORD_RESET_TIMEOUT = 14 * 24 * 60 * 60

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
# Uploaded files: presenters' photos and the talk posters drawn from them.
# Nothing in this folder is served straight from disk. The photos are shown
# only to the leadership team, through the admin, and a poster only through its
# event's page, which applies that event's visibility. Back it up with the
# database: a lost poster can be drawn again, a lost photo cannot.
MEDIA_ROOT = Path(env("DJANGO_MEDIA_ROOT", str(BASE_DIR / "media")))
MEDIA_URL = "/media/"

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
    # The real hasher is deliberately slow, which is the point in production
    # and a two-minute wait in a test suite that creates hundreds of accounts.
    # Tests only: nothing outside `manage.py test` ever uses this.
    PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]

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

# The address this app itself is served on, with scheme and no trailing slash.
# Links in emails sent from a web request are built from that request; this is
# for the ones that have no request to build from, like the event reminders a
# scheduled job sends. It is not the static site, which does not serve
# /account/ or /events/ at all. A deploy check warns if it is still pointing at
# localhost when DEBUG is off.
APP_URL = env("APP_URL", "http://localhost:8000").rstrip("/")

# The token Google Search Console gives for "HTML tag" verification. Set it in
# the environment and it appears as a <meta> tag in the site head; left empty,
# no tag is rendered. Verification by DNS or file does not need this.
GOOGLE_SITE_VERIFICATION = env("GOOGLE_SITE_VERIFICATION", "")

# The single password that unlocks the bespoke "vault" admin console. Kept in
# the environment, never in the code; empty means the vault cannot be unlocked.
VAULT_PASSWORD = env("VAULT_PASSWORD", "")

# Where the join form posts. Same-origin here, so the front-end script needs no
# change whether the pages are served by Django or by the static site.
FORM_ENDPOINT = env("FORM_ENDPOINT", "/api/register")

# --- Form protection ------------------------------------------------------
MIN_FILL_SECONDS = float(env("MIN_FILL_SECONDS", "1.5"))
MAX_FILL_SECONDS = float(env("MAX_FILL_SECONDS", str(12 * 60 * 60)))
# The join form refuses marketing pitches outright; applications/spam.py holds
# the built-in list. These two adjust it without a code change: extra terms to
# refuse, and terms from the built-in list to allow again (useful if a genuine
# member is ever turned away by a word like "seo").
EXTRA_BLOCKED_TERMS = env_list("EXTRA_BLOCKED_TERMS")
UNBLOCKED_TERMS = env_list("UNBLOCKED_TERMS")

RATE_LIMIT_MAX = int(env("RATE_LIMIT_MAX", "5"))
RATE_LIMIT_WINDOW_SECONDS = int(env("RATE_LIMIT_WINDOW_SECONDS", "600"))

# --- Failed sign-ins ------------------------------------------------------
# How many wrong passwords the sign-in pages will answer before refusing for a
# while. These count failures only, so signing in correctly as often as you
# like costs nothing. config/login_throttle.py explains the three counters.
#
# Eight from one connection is more than a person needs and far less than a
# script wants. Twenty against one account is high on purpose: anyone can send
# wrong passwords for an address they know, and the lower the number, the
# easier it is to keep a real member out.
LOGIN_FAIL_MAX = int(env("LOGIN_FAIL_MAX", "8"))
LOGIN_FAIL_ACCOUNT_MAX = int(env("LOGIN_FAIL_ACCOUNT_MAX", "20"))
# The Vault only. One shared password has no accounts to count against, so
# every failure against it counts together, however many places they come
# from. If this is ever reached the Django admin still works, so the
# leadership team is not shut out of everything by a flood.
LOGIN_FAIL_SHARED_MAX = int(env("LOGIN_FAIL_SHARED_MAX", "40"))
LOGIN_FAIL_WINDOW_SECONDS = int(env("LOGIN_FAIL_WINDOW_SECONDS", "900"))

# --- Events ---------------------------------------------------------------
# How far ahead of an event the reminder goes out. The reminder job runs once
# an hour, so a reminder arrives within an hour of this mark.
EVENT_REMINDER_HOURS = int(env("EVENT_REMINDER_HOURS", "24"))

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {"plain": {"format": "%(levelname)s %(name)s %(message)s"}},
    "handlers": {"console": {"class": "logging.StreamHandler", "formatter": "plain"}},
    "root": {"handlers": ["console"], "level": env("DJANGO_LOG_LEVEL", "INFO")},
}
