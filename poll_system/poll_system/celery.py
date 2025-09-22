import os
from celery import Celery

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'poll_system.settings')


app = Celery('poll_system')
app.config_from_object('django.conf:serrings', namespace='CELERY')
app.autodiscover_tasks()