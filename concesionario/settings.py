from pathlib import Path
import os

# ==========================================================
# BASE
# ==========================================================
BASE_DIR = Path(__file__).resolve().parent.parent

# ==========================================================
# ENV (SEGURIDAD: NO ROMPE LOCAL)
# ==========================================================
try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass

# ==========================================================
# SECURITY
# ==========================================================
SECRET_KEY = os.getenv(
    "SECRET_KEY",
    "django-insecure-concesionario-local-dev"
)

DEBUG = os.getenv("DEBUG", "True") == "True"

# ==========================================================
# ALLOWED HOSTS (RENDER + LOCAL)
# ==========================================================
ALLOWED_HOSTS = [
    "localhost",
    "127.0.0.1",
]

RENDER_HOST = os.getenv("RENDER_EXTERNAL_HOSTNAME")
if RENDER_HOST:
    ALLOWED_HOSTS.append(RENDER_HOST)

ALLOWED_HOSTS.append(".onrender.com")

# ==========================================================
# CSRF (RENDER / PRODUCCIÓN)
# ==========================================================
CSRF_TRUSTED_ORIGINS = [
    "https://concesionario-k5i6.onrender.com",
    "https://*.onrender.com",
]

# ==========================================================
# APPLICATIONS
# ==========================================================
INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",

    # Apps del proyecto
    "inicio",
    "clientes",
    "vehiculos",
    "ventas.apps.VentasConfig",
    "cuentas",
    "gestoria",
    "calendario",
    "facturacion",
    "reportes.apps.ReportesConfig",
    "asistencia",
    "deudas",
    "boletos",
]

# ==========================================================
# MIDDLEWARE
# ==========================================================
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

# ==========================================================
# URLS / WSGI
# ==========================================================
ROOT_URLCONF = "concesionario.urls"
WSGI_APPLICATION = "concesionario.wsgi.application"

# ==========================================================
# DATABASE (SQLITE LOCAL + POSTGRES PRODUCCIÓN)
# ==========================================================
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",
        "OPTIONS": {
            "timeout": 20,
        },
    }
}

DATABASE_URL = os.getenv("DATABASE_URL")

if DATABASE_URL:
    try:
        import dj_database_url
        DATABASES["default"] = dj_database_url.parse(
            DATABASE_URL,
            conn_max_age=600,
            ssl_require=True,
        )
    except Exception:
        pass

# ==========================================================
# PASSWORD VALIDATION
# ==========================================================
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# ==========================================================
# INTERNATIONALIZATION
# ==========================================================
LANGUAGE_CODE = "es-ar"
TIME_ZONE = "America/Argentina/Buenos_Aires"

USE_I18N = True
USE_TZ = True

# ==========================================================
# STATIC & MEDIA FILES
# ==========================================================
STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"

STATICFILES_DIRS = [
    BASE_DIR / "static",
]

STATICFILES_STORAGE = "whitenoise.storage.CompressedManifestStaticFilesStorage"

MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

# ==========================================================
# TEMPLATES
# ==========================================================
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

# ==========================================================
# AUTH / LOGIN  ✅ FIX DEFINITIVO
# ==========================================================
LOGIN_URL = "/admin/login/"
LOGIN_REDIRECT_URL = "/inicio/"
LOGOUT_REDIRECT_URL = "/admin/login/"

# ==========================================================
# DEFAULT FIELD
# ==========================================================
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# ==========================================================
# HTTPS / PROXY (FIX DEFINITIVO CSRF EN RENDER)
# ==========================================================
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

CSRF_COOKIE_SECURE = True
SESSION_COOKIE_SECURE = True

CSRF_COOKIE_SAMESITE = "Lax"
SESSION_COOKIE_SAMESITE = "Lax"
