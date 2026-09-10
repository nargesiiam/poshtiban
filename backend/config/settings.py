from pathlib import Path
from datetime import timedelta
from decouple import config, Csv

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = config("DJANGO_SECRET_KEY", default="dev-only-not-for-production")
DEBUG = config("DJANGO_DEBUG", default=True, cast=bool)
ALLOWED_HOSTS = config("DJANGO_ALLOWED_HOSTS", default="*", cast=Csv())

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
    "rest_framework_simplejwt",
    "corsheaders",
    # نکته: Channels اینجا لازم نیست. SSE یک پاسخ HTTP طولانی‌عمر است، نه
    # WebSocket؛ Django به‌طور بومی از async view و StreamingHttpResponse
    # پشتیبانی می‌کند (از نسخه‌ی ۴.۲) — یعنی Daphne به‌تنهایی کافی است.
    # Channels فقط وقتی لازم می‌شود که WebSocket بخواهیم (بخش امتیازی).
    # اپ‌های دامنه — هرکدام یک مسئولیت مشخص، بدون هم‌پوشانی
    "apps.accounts",
    "apps.orders",
    "apps.documents",
    "apps.conversations",
    "apps.events",
]

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

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
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
# ASGI_APPLICATION عمداً اینجا نیست — آن یک تنظیم مخصوص Channels است.
# daphne مستقیماً با config.asgi:application اجرا می‌شود (ببین docker-compose.yml).

# --- پایگاه‌داده ---
# نام سرویس (POSTGRES_HOST=postgres) نه localhost — طبق توضیح بخش ۱
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": config("POSTGRES_DB", default="relay"),
        "USER": config("POSTGRES_USER", default="relay"),
        "PASSWORD": config("POSTGRES_PASSWORD", default="relay"),
        "HOST": config("POSTGRES_HOST", default="postgres"),
        "PORT": config("POSTGRES_PORT", default="5432"),
    }
}

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "fa-ir"
TIME_ZONE = "Asia/Tehran"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
MEDIA_URL = "media/"
MEDIA_ROOT = BASE_DIR / "media"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# --- DRF + JWT ---
# هیچ endpointـی بدون احراز هویت پیش‌فرض باز نیست. هر ویو که استثنا لازم دارد
# باید صریحاً AllowAny بگذارد — یعنی «باز بودن» یک تصمیم آگاهانه است، نه پیش‌فرض غفلت‌شده.
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "rest_framework_simplejwt.authentication.JWTAuthentication",
    ),
    "DEFAULT_PERMISSION_CLASSES": (
        "rest_framework.permissions.IsAuthenticated",
    ),
}

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(hours=1),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=7),
    "ROTATE_REFRESH_TOKENS": True,
}

CORS_ALLOWED_ORIGINS = config(
    "CORS_ALLOWED_ORIGINS",
    default="http://localhost:5173,http://localhost:5174",
    cast=Csv(),
)

# --- RabbitMQ / ChromaDB (مصرف در بخش ۳ به بعد) ---
RABBITMQ_HOST = config("RABBITMQ_HOST", default="rabbitmq")
RABBITMQ_USER = config("RABBITMQ_USER", default="relay")
RABBITMQ_PASSWORD = config("RABBITMQ_PASSWORD", default="relay")
