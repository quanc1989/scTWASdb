"""Standalone runtime configuration loaded from an owner-only JSON file."""
import json
import os
from pathlib import Path

CONFIG_PATH = Path(os.environ['SCTWAS_RUNTIME_CONFIG']).expanduser().resolve()
if CONFIG_PATH.stat().st_mode & 0o077:
    raise PermissionError('Runtime configuration must be readable only by its owner')
CONFIG = json.loads(CONFIG_PATH.read_text())
if not CONFIG.get('SECRET_KEY') or CONFIG['SECRET_KEY'] == 'REPLACE_WITH_A_RANDOM_SECRET':
    raise ValueError('Provide a generated SECRET_KEY in the private runtime configuration')

SECRET_KEY = CONFIG['SECRET_KEY']
DEBUG = False
ALLOWED_HOSTS = CONFIG.get('ALLOWED_HOSTS', ['localhost', '127.0.0.1'])
CSRF_TRUSTED_ORIGINS = CONFIG.get('CSRF_TRUSTED_ORIGINS', [])
ROOT_URLCONF = 'sctwas.urls'
INSTALLED_APPS = ['django.contrib.staticfiles', 'sctwas.apps.SctwasConfig']
DEFAULT_AUTO_FIELD = 'django.db.models.AutoField'
TEMPLATES = [{
    'BACKEND': 'django.template.backends.django.DjangoTemplates',
    'APP_DIRS': True,
    'OPTIONS': {'context_processors': ['django.template.context_processors.request']},
}]
DATABASES = {'default': CONFIG['DATABASE']}
MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'sctwas.deployment.middleware.ReleaseHeader',
    'sctwas.deployment.readonly.DemoReadOnly',
]
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True
STATIC_ROOT = CONFIG['STATIC_ROOT']
STATIC_URL = CONFIG.get('STATIC_URL', '/static/')
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
SESSION_COOKIE_SECURE = CONFIG.get('HTTPS', True)
CSRF_COOKIE_SECURE = CONFIG.get('HTTPS', True)
SCTWAS_RELEASE = CONFIG.get('SCTWAS_RELEASE', 'web-20261118-01')
SCTWAS_DATA_VERSION = CONFIG.get('SCTWAS_DATA_VERSION', 'example-catalogue')
SCTWAS_READ_ONLY_DEMO = CONFIG.get('READ_ONLY_DEMO', True)
SCTWAS_TASK_ROOT = CONFIG['SCTWAS_TASK_ROOT']
SCTWAS_EXPORT_ROOT = CONFIG['SCTWAS_EXPORT_ROOT']
SCTWAS_EXPORT_ASYNC = not SCTWAS_READ_ONLY_DEMO
SCTWAS_EXECUTOR = 'spool'
SCTWAS_EXPLORE_INDEX = CONFIG.get('SCTWAS_EXPLORE_INDEX', '')
SCTWAS_EXPLORE_INDEX_SHA256 = CONFIG.get('SCTWAS_EXPLORE_INDEX_SHA256', '')
SCTWAS_MAX_UPLOAD_BYTES = 100 * 1024 * 1024
DATA_UPLOAD_MAX_MEMORY_SIZE = 1024 * 1024
FILE_UPLOAD_MAX_MEMORY_SIZE = 2 * 1024 * 1024
FILE_UPLOAD_PERMISSIONS = 0o600
FILE_UPLOAD_DIRECTORY_PERMISSIONS = 0o700
CACHES = {
    'default': {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache'},
    'sctwas_queries': {
        'BACKEND': 'django.core.cache.backends.filebased.FileBasedCache',
        'LOCATION': CONFIG['SCTWAS_QUERY_CACHE_ROOT'],
        'TIMEOUT': 3600,
    },
}
MAIL = CONFIG.get('MAIL', {})
EMAIL_BACKEND = MAIL.get('BACKEND', 'django.core.mail.backends.console.EmailBackend')
EMAIL_HOST = MAIL.get('HOST', '')
EMAIL_PORT = MAIL.get('PORT', 465)
EMAIL_USE_SSL = MAIL.get('USE_SSL', True)
EMAIL_USE_TLS = MAIL.get('USE_TLS', False)
EMAIL_HOST_USER = MAIL.get('USER', '')
EMAIL_HOST_PASSWORD = MAIL.get('PASSWORD', '')
EMAIL_TIMEOUT = 25
DEFAULT_FROM_EMAIL = MAIL.get('FROM', EMAIL_HOST_USER or 'noreply@example.org')
