# celeryconfig.py
import os
from celery.schedules import crontab

broker_url = os.environ.get("CELERY_BROKER_URL", "redis://redis:6379/0")
result_backend = os.environ.get("CELERY_RESULT_BACKEND", broker_url)
task_serializer = "json"
result_serializer = "json"
accept_content = ["json"]
timezone = "Asia/Tokyo"
enable_utc = False
worker_prefetch_multiplier = 1
task_acks_late = True
beat_schedule = {
    "nightly-batch-02:00-jst": {
        "task": "app.tasks.nightly_batch",
        "schedule": crontab(hour=2, minute=0),
        "args": ()
    }
}