"""
Django settings for e_learning_platform project.
Version : 6.0 - IntÃ©gration Robuste .env et Ngrok
"""

import os
from pathlib import Path
from dotenv import load_dotenv
import dj_database_url

# Chemin de base du projet
BASE_DIR = Path(__file__).resolve().parent.parent

# Chargement du fichier .env Ã  la racine
load_dotenv(os.path.join(BASE_DIR, '.env'))

# --- SÃ‰CURITÃ‰ ---
SECRET_KEY = os.getenv('SECRET_KEY', 'django-insecure-default-key')
DEBUG = os.getenv('DEBUG', 'True') == 'True'

# Gestion de l'URL Ngrok pour les tests distants
NGROK_HOST = os.getenv('NGROK_URL', 'localhost')
VERCEL_URL = os.getenv('VERCEL_URL')

ALLOWED_HOSTS = ['127.0.0.1', 'localhost', NGROK_HOST, '.vercel.app']
extra_hosts = os.getenv('ALLOWED_HOSTS', '')
if extra_hosts:
    ALLOWED_HOSTS += [h.strip() for h in extra_hosts.split(',') if h.strip()]
if VERCEL_URL:
    ALLOWED_HOSTS.append(VERCEL_URL)
if DEBUG:
    ALLOWED_HOSTS.append('*')

# SÃ©curitÃ© pour les Webhooks (Indispensable pour Ngrok)
CSRF_TRUSTED_ORIGINS = []
extra_csrf = os.getenv('CSRF_TRUSTED_ORIGINS', '')
if extra_csrf:
    CSRF_TRUSTED_ORIGINS += [o.strip() for o in extra_csrf.split(',') if o.strip()]
if VERCEL_URL:
    CSRF_TRUSTED_ORIGINS.append(f'https://{VERCEL_URL}')
if NGROK_HOST and NGROK_HOST != 'localhost':
    CSRF_TRUSTED_ORIGINS.append(f'https://{NGROK_HOST}')

# --- APPLICATIONS ---
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'storages',
    'e_learning_app',
    'markdownify.apps.MarkdownifyConfig',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'e_learning_platform.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'django.template.context_processors.media',
            ],
        },
    },
]

WSGI_APPLICATION = 'e_learning_platform.wsgi.application'

# --- BASE DE DONNÃ‰ES ---
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}

DATABASE_URL = os.getenv('DATABASE_URL')
if DATABASE_URL:
    DATABASES['default'] = dj_database_url.parse(DATABASE_URL, conn_max_age=600)

# --- INTERNATIONALISATION ---
LANGUAGE_CODE = 'fr-fr'
TIME_ZONE = 'Africa/Porto-Novo'
USE_I18N = True
USE_TZ = True

# --- FICHIERS STATIQUES ET MÃ‰DIAS ---
AUTH_USER_MODEL = 'e_learning_app.User'
STATIC_URL = '/static/'
STATICFILES_DIRS = [BASE_DIR / 'static']
STATIC_ROOT = BASE_DIR / 'staticfiles'
SUPABASE_S3_ENDPOINT = os.getenv('SUPABASE_S3_ENDPOINT')
SUPABASE_S3_BUCKET = os.getenv('SUPABASE_S3_BUCKET')
SUPABASE_S3_ACCESS_KEY_ID = os.getenv('SUPABASE_S3_ACCESS_KEY_ID')
SUPABASE_S3_SECRET_ACCESS_KEY = os.getenv('SUPABASE_S3_SECRET_ACCESS_KEY')
SUPABASE_S3_REGION = os.getenv('SUPABASE_S3_REGION', 'us-east-1')
SUPABASE_URL = os.getenv('SUPABASE_URL')
SUPABASE_PUBLIC_URL = os.getenv('SUPABASE_PUBLIC_URL')
SUPABASE_BUCKET_PUBLIC = os.getenv('SUPABASE_BUCKET_PUBLIC', 'true').lower() in ('1', 'true', 'yes')
USE_SUPABASE_STORAGE = all([
    SUPABASE_S3_ENDPOINT,
    SUPABASE_S3_BUCKET,
    SUPABASE_S3_ACCESS_KEY_ID,
    SUPABASE_S3_SECRET_ACCESS_KEY,
])
STORAGES = {
    "default": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
    },
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"
    }
}
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

# Serverless filesystems are read-only; use /tmp for uploads unless S3 is configured.
_SERVERLESS = bool(os.getenv('VERCEL')) or bool(os.getenv('VERCEL_URL'))
_MEDIA_ROOT_ENV = os.getenv('MEDIA_ROOT')
if _MEDIA_ROOT_ENV:
    MEDIA_ROOT = Path(_MEDIA_ROOT_ENV)
elif _SERVERLESS and not USE_SUPABASE_STORAGE:
    MEDIA_ROOT = Path('/tmp') / 'media'

if USE_SUPABASE_STORAGE:
    AWS_ACCESS_KEY_ID = SUPABASE_S3_ACCESS_KEY_ID
    AWS_SECRET_ACCESS_KEY = SUPABASE_S3_SECRET_ACCESS_KEY
    AWS_STORAGE_BUCKET_NAME = SUPABASE_S3_BUCKET
    AWS_S3_ENDPOINT_URL = SUPABASE_S3_ENDPOINT
    AWS_S3_REGION_NAME = SUPABASE_S3_REGION
    AWS_S3_ADDRESSING_STYLE = 'path'
    AWS_S3_SIGNATURE_VERSION = 's3v4'
    AWS_DEFAULT_ACL = None
    AWS_QUERYSTRING_AUTH = not SUPABASE_BUCKET_PUBLIC
    # Use Supabase public URL for file access when bucket is public.
    AWS_S3_CUSTOM_DOMAIN = None
    if SUPABASE_BUCKET_PUBLIC:
        public_url = (SUPABASE_PUBLIC_URL or '').strip()
        if not public_url and SUPABASE_URL and SUPABASE_S3_BUCKET:
            public_url = f"{SUPABASE_URL.rstrip('/')}/storage/v1/object/public/{SUPABASE_S3_BUCKET}"
        if public_url:
            AWS_S3_CUSTOM_DOMAIN = public_url.replace('https://', '').replace('http://', '').rstrip('/')
    STORAGES["default"] = {
        "BACKEND": "storages.backends.s3boto3.S3Boto3Storage",
    }
    if SUPABASE_PUBLIC_URL and SUPABASE_BUCKET_PUBLIC:
        MEDIA_URL = SUPABASE_PUBLIC_URL.rstrip('/') + '/'
    elif SUPABASE_URL and SUPABASE_BUCKET_PUBLIC:
        MEDIA_URL = f"{SUPABASE_URL.rstrip('/')}/storage/v1/object/public/{SUPABASE_S3_BUCKET}/"

# --- REDIRECTIONS ---
LOGIN_URL = 'login'
LOGIN_REDIRECT_URL = 'home'
LOGOUT_REDIRECT_URL = 'home'
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# --- CONFIGURATION FEDAPAY CONNECTOR ---
FEDAPAY_API_KEY = os.getenv('FEDAPAY_API_KEY')
FEDAPAY_API_URL = os.getenv('FEDAPAY_API_URL')
FEDAPAY_AUTH_KEY = os.getenv('FEDAPAY_AUTH_KEY')
FEDAPAY_ENVIRONMENT = os.getenv('FEDAPAY_ENVIRONMENT', 'sandbox')

# --- LOGGING (use DJANGO_LOG_LEVEL in env for more/less verbosity) ---
DJANGO_LOG_LEVEL = os.getenv('DJANGO_LOG_LEVEL', 'INFO')
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {
        'console': {'class': 'logging.StreamHandler'},
    },
    'root': {
        'handlers': ['console'],
        'level': DJANGO_LOG_LEVEL,
    },
    'loggers': {
        'django.request': {
            'handlers': ['console'],
            'level': 'ERROR',
            'propagate': False,
        },
    },
}
