from priyomoney_client.settings import *
USE_SQLITE = os.getenv('USE_SQLITE_FOR_TESTS', "false").lower() == 'true'
if USE_SQLITE:
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': 'testdb',
        },
        'priyo_pay_slave': {
            'ENGINE': 'django.db.backends.sqlite3',
            'MIRROR': 'default'
        }
    }

PROFILE_CACHE_TTL = 0
CELERY_TASK_ALWAYS_EAGER = True
LOGGING = {}
AUTH_API_BASE = None
OWN_BASE_URL = None
CLIENT_SIDE_BASE_URL = None
SYNCTERA_BASE_URL = None
SMS_URL = None
EMAIL_HOST = None
TWILIO_AUTH_TOKEN = None
SENDGRID_API_KEY = None
GS_BUCKET_NAME = None
GS_BUCKET_CREDENTIAL = None
PERSONA_API_BASE = None
MONGODB_DB_NAME = 'test_priyo_pay_logs' # to not destroy local mongo
FIREBASE_CREDENTIAL = None