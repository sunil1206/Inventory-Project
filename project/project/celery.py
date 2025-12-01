# project/celery.py

import os
from celery import Celery
from celery.schedules import crontab

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "project.settings")

app = Celery("project")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()

# Celery Beat schedule
app.conf.beat_schedule = {
    "scrape-all-products-every-morning": {
        "task": "competitor.tasks.scrape_all_products_nightly",
        "schedule": crontab(hour=5, minute=0),   # 05:00 every day
    },
}
