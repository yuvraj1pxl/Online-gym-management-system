from pathlib import Path
import os
import dj_database_url
from import_export.formats.base_formats import XLSX, CSV

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = os.environ.get('SECRET_KEY', 'django-insecure-n587#^$6wnzmupy@dg3mvq6#7=hq&is2kb#f-9r8_7y1w$8pp_')

DEBUG = os.environ.get('DEBUG', 'True').lower() == 'true'

ALLOWED_HOSTS = ['*']

CSRF_TRUSTED_ORIGINS = [
    "https://*.ngrok-free.app", 
    "https://*.vscode.dev",      
    "https://vqmmdgzt-8000.inc1.devtunnels.ms"
]

# --- Application Definition ---
INSTALLED_APPS = [
    'body',          # CRITICAL: Move your app to the top to override Jazzmin/Admin templates
    'jazzmin',
    'import_export',
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'widget_tweaks',
]

# --- Professional IMS Settings ---
JAZZMIN_SETTINGS = {
    "site_title": "GYM-SHIM Admin",
    "site_header": "GYM-SHIM",
    "site_brand": "GYM-SHIM ELITE",
    "site_logo": None, 
    "welcome_sign": "GYM-SHIM: Professional Inventory & Membership Suite",
    "copyright": "2026 GYM-SHIM Elite",
    "search_model": ["body.Admission", "body.Product", "body.ProductOrder"],
    "user_avatar": None,
    "topmenu_links": [
        {"name": "Home", "url": "admin:index", "permissions": ["auth.view_user"]},
        {"name": "View Site", "url": "/", "new_window": True},
        {"name": "Support", "url": "https://github.com/yuvraj", "new_window": True},
    ],
    "show_sidebar": True,
    "navigation_expanded": True,
    "icons": {
        "auth": "fas fa-users-cog",
        "auth.user": "fas fa-user",
        "auth.Group": "fas fa-users",
        "body.Admission": "fas fa-user-plus",
        "body.AdmissionPayment": "fas fa-file-invoice-dollar",
        "body.Product": "fas fa-boxes",
        "body.Sale": "fas fa-chart-line",
        "body.ProductOrder": "fas fa-truck-loading",
        "body.Trainer": "fas fa-user-tie",
        "body.MembershipPlan": "fas fa-gem",
        "body.GalleryImage": "fas fa-image",
    },
    "order_with_respect_to": ["body.Admission", "body.Product", "body.Sale", "body.ProductOrder"],
    "show_ui_builder": False, # Set to False once your theme is locked in for a cleaner look
}

JAZZMIN_UI_TWEAKS = {
    "navbar_small_text": False,
    "footer_small_text": False,
    "body_small_text": False,
    "brand_small_text": False,
    "brand_colour": "navbar-warning", 
    "accent": "accent-warning",
    "navbar": "navbar-dark",
    "no_navbar_border": False,
    "navbar_fixed": True,
    "layout_boxed": False,
    "footer_fixed": True,
    "sidebar_fixed": True,
    "sidebar": "sidebar-dark-warning", 
    "sidebar_nav_small_text": False,
    "sidebar_disable_expand": False,
    "sidebar_nav_child_indent": True,
    "sidebar_nav_compact_style": False,
    "sidebar_nav_legacy_style": False,
    "sidebar_nav_flat_style": False,
    "theme": "darkly",
    "dark_mode_theme": "darkly",
    "button_classes": {
        "primary": "btn-primary",
        "secondary": "btn-secondary",
        "info": "btn-info",
        "warning": "btn-warning",
        "danger": "btn-danger",
        "success": "btn-success"
    }
}

IMPORT_EXPORT_FORMATS = [XLSX, CSV]

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

ROOT_URLCONF = 'gym.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        # Updated DIRS to ensure it finds your 'admin/index.html' inside body/templates
        'DIRS': [BASE_DIR / 'body' / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'gym.wsgi.application'

DATABASES = {
    'default': dj_database_url.config(
        default=f"sqlite:///{BASE_DIR / 'db.sqlite3'}",
        conn_max_age=600,
        ssl_require=False if os.environ.get('DISABLE_DATABASE_SSL') else True
    )
}

if 'sqlite' in DATABASES['default']['ENGINE']:
    DATABASES['default'] = {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'Asia/Kolkata' # Updated for Ranchi/IST accuracy
USE_I18N = True
USE_TZ = True

STATIC_URL = '/static/'
STATICFILES_DIRS = [BASE_DIR / 'body' / 'static']
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# settings.py

LOGIN_URL = 'body:profile'