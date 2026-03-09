import os
import time
from datetime import datetime, timedelta
from celery import Celery
from celery.schedules import crontab
from flask import current_app
from redis import Redis
from contextlib import contextmanager
from .extensions import db
from .models import Individual
from .services import schedule_and_train_models_for_uid, finalize_provisionals, aggregate_history_by_date, list_history

CELERY_BROKER_URL = os.environ.get("CELERY_BROKER_URL", os.environ.get("REDIS_URL", "redis://localhost:6379/0"))
CELERY_RESULT_BACKEND = os.environ.get("CELERY_RESULT_BACKEND", CELERY_BROKER_URL)

celery = Celery("app.tasks", broker=CELERY_BROKER_URL, backend=CELERY_RESULT_BACKEND)
celery.conf.update(task_serializer="json", result_serializer="json", accept_content=["json"], timezone="Asia/Tokyo", enable_utc=False)

REDIS_LOCK_DB = int(os.environ.get("REDIS_LOCK_DB", "1"))
redis_client = Redis.from_url(os.environ.get("REDIS_URL", "redis://localhost:6379/0"), db=REDIS_LOCK_DB)

LOCK_TTL = int(os.environ.get("TASK_LOCK_TTL_SECONDS", 60 * 60 * 2))

@contextmanager
def redis_lock(key: str, ttl: int = LOCK_TTL):
    token = str(time.time())
    acquired = redis_client.set(name=key, value=token, nx=True, ex=ttl)
    try:
        if acquired:
            yield True
        else:
            yield False
    finally:
        try:
            val = redis_client.get(key)
            if val and val.decode() == token:
                redis_client.delete(key)
        except Exception:
            pass

@celery.on_after_configure.connect
def setup_periodic_tasks(sender, **kwargs):
    sender.add_periodic_task(crontab(hour=2, minute=0), nightly_batch.s(), name="nightly-batch-02:00-jst")

@celery.task(bind=True, max_retries=3, default_retry_delay=60)
def nightly_batch(self):
    lock_key = "nightly_batch_lock"
    with redis_lock(lock_key) as ok:
        if not ok:
            return {"status": "skipped", "reason": "lock_exists"}
        try:
            inds = Individual.query.with_entities(Individual.id, Individual.uid).all()
            results = {"processed": 0, "errors": 0}
            for ind in inds:
                try:
                    uid = ind.uid
                    schedule_and_train_models_for_uid({"id": ind.id, "uid": uid, "history": []})
                    finalize_provisionals(ind.id)
                    results["processed"] += 1
                except Exception:
                    results["errors"] += 1
            return {"status": "ok", "result": results}
        except Exception as exc:
            raise self.retry(exc=exc)

@celery.task(bind=True, max_retries=2, default_retry_delay=30)
def train_for_individual(self, individual_id: int):
    lock_key = f"train_individual_{individual_id}"
    with redis_lock(lock_key) as ok:
        if not ok:
            return {"status": "skipped", "reason": "lock_exists"}
        try:
            ind = Individual.query.get(individual_id)
            if not ind:
                return {"status": "not_found"}
            history = [h.to_dict() for h in ind.history_entries.order_by().all()]
            schedule_and_train_models_for_uid({"id": ind.id, "uid": ind.uid, "history": history})
            return {"status": "ok", "individual_id": individual_id}
        except Exception as exc:
            raise self.retry(exc=exc)

@celery.task(bind=True)
def finalize_provisionals_task(self, individual_id: int):
    lock_key = f"finalize_provs_{individual_id}"
    with redis_lock(lock_key) as ok:
        if not ok:
            return {"status": "skipped", "reason": "lock_exists"}
        try:
            ind = Individual.query.get(individual_id)
            if not ind:
                return {"status": "not_found"}
            history = [h.to_dict() for h in ind.history_entries.order_by().all()]
            agg = aggregate_history_by_date(history)
            finalize_provisionals(ind.id)
            return {"status": "ok", "individual_id": individual_id}
        except Exception as exc:
            raise self.retry(exc=exc)