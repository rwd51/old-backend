from __future__ import absolute_import, unicode_literals
import os
from celery import Celery
import django

# set the default Django settings module for the 'celery' program.
from dotenv import load_dotenv

load_dotenv()
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'priyomoney_client.settings')
django.setup()

# CELERY_RESULT_BACKEND is necessary to get the task results
app = Celery('priyomoney_client', CELERY_RESULT_BACKEND='redis://')

# Using a string here means the worker doesn't have to serialize
# the configuration object to child processes.
# - namespace='CELERY' means all celery-related configuration keys
#   should have a `CELERY_` prefix.
app.config_from_object('django.conf:settings', namespace='CELERY')

# Load task modules from all registered Django app configs.
app.conf.broker_transport_options = {'visibility_timeout': 3}
app.autodiscover_tasks(force=True)