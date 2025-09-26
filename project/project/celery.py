# myproject/celery.py
import os
from celery import Celery

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'project.settings') # Replace 'myproject' with your project's name
app = Celery('project') # Replace 'myproject'
app.config_from_object('django.conf:settings', namespace='CELERY')
app.autodiscover_tasks()
