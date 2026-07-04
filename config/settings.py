from pathlib import Path
import os

BASE_DIR = Path(__file__).resolve().parent.parent

_env_file = BASE_DIR / '.env'
if _env_file.exists():
    for _line in _env_file.read_text(encoding='utf-8').splitlines():
        _line = _line.strip()
        if _line and not _line.startswith('#') and '=' in _line:
            _key, _val = _line.split('=', 1)
            os.environ[_key.strip()] = _val.strip()

DEBUG = os.environ.get('DEBUG', '1') == '1'

SECRET_KEY = os.environ.get(
    'SECRET_KEY',
    'django-insecure-badminton-rotation-dev-key-change-in-production',
)

_allowed = [
    host.strip()
    for host in os.environ.get('ALLOWED_HOSTS', '').split(',')
    if host.strip()
]
ALLOWED_HOSTS = _allowed or (['*'] if DEBUG else [])

CSRF_TRUSTED_ORIGINS = [
    origin.strip()
    for origin in os.environ.get('CSRF_TRUSTED_ORIGINS', '').split(',')
    if origin.strip()
]
if DEBUG and not CSRF_TRUSTED_ORIGINS:
    CSRF_TRUSTED_ORIGINS = [
        'http://localhost:8000',
        'http://127.0.0.1:8000',
    ]

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'rotation',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'rotation.middleware.ClubMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'config.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'django.template.context_processors.csrf',
                'rotation.context_processors.site_context',
            ],
        },
    },
]

WSGI_APPLICATION = 'config.wsgi.application'

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

LANGUAGE_CODE = 'zh-hans'
TIME_ZONE = 'Asia/Shanghai'
USE_I18N = True
USE_TZ = True

STATIC_URL = 'static/'
STATICFILES_DIRS = [BASE_DIR / 'static']
STATIC_ROOT = BASE_DIR / 'staticfiles'
STORAGES = {
    'default': {
        'BACKEND': 'django.core.files.storage.FileSystemStorage',
    },
    'staticfiles': {
        'BACKEND': 'whitenoise.storage.CompressedStaticFilesStorage',
    },
}

MEDIA_URL = 'media/'
MEDIA_ROOT = BASE_DIR / 'media'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

LOGIN_URL = 'login'
LOGIN_REDIRECT_URL = 'home'
LOGOUT_REDIRECT_URL = 'login'

if not DEBUG:
    SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True

# 微信群截图导入（视觉识别 API，兼容 OpenAI 接口，支持多 provider 自动切换）
WECHAT_IMPORT_VISION_API_KEY = os.environ.get('WECHAT_IMPORT_VISION_API_KEY', '')
WECHAT_IMPORT_VISION_API_BASE = os.environ.get(
    'WECHAT_IMPORT_VISION_API_BASE', 'https://open.bigmodel.cn/api/paas/v4'
)
WECHAT_IMPORT_VISION_MODEL = os.environ.get(
    'WECHAT_IMPORT_VISION_MODEL', 'glm-4.6v-flash'
)
WECHAT_IMPORT_VISION_JSON_MODE = os.environ.get('WECHAT_IMPORT_VISION_JSON_MODE', '1') == '1'

WECHAT_IMPORT_VISION_BACKUP_1_API_KEY = os.environ.get('WECHAT_IMPORT_VISION_BACKUP_1_API_KEY', '')
WECHAT_IMPORT_VISION_BACKUP_1_API_BASE = os.environ.get(
    'WECHAT_IMPORT_VISION_BACKUP_1_API_BASE', 'https://api.siliconflow.cn/v1'
)
WECHAT_IMPORT_VISION_BACKUP_1_MODEL = os.environ.get(
    'WECHAT_IMPORT_VISION_BACKUP_1_MODEL', 'Qwen/Qwen3-VL-30B-A3B-Instruct'
)
WECHAT_IMPORT_VISION_BACKUP_1_JSON_MODE = (
    os.environ.get('WECHAT_IMPORT_VISION_BACKUP_1_JSON_MODE', '0') == '1'
)

WECHAT_IMPORT_VISION_BACKUP_2_API_KEY = os.environ.get('WECHAT_IMPORT_VISION_BACKUP_2_API_KEY', '')
WECHAT_IMPORT_VISION_BACKUP_2_API_BASE = os.environ.get(
    'WECHAT_IMPORT_VISION_BACKUP_2_API_BASE',
    'https://dashscope.aliyuncs.com/compatible-mode/v1',
)
WECHAT_IMPORT_VISION_BACKUP_2_MODEL = os.environ.get(
    'WECHAT_IMPORT_VISION_BACKUP_2_MODEL', 'qwen-vl-plus'
)
WECHAT_IMPORT_VISION_BACKUP_2_JSON_MODE = (
    os.environ.get('WECHAT_IMPORT_VISION_BACKUP_2_JSON_MODE', '0') == '1'
)
