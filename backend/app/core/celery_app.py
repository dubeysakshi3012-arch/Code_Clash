"""Celery application configuration."""

import sys
from celery import Celery
from app.core.config import settings

# Create Celery app instance
celery_app = Celery(
    "codeclash",
    broker=settings.get_celery_broker_url(),
    backend=settings.get_celery_result_backend(),
    include=["app.workers.judge_tasks"]
)

# On Windows, prefork pool causes PermissionError with billiard semaphores; use solo pool
worker_pool = "solo" if sys.platform == "win32" else "prefork"

# Configure Celery
celery_app.conf.update(
    task_serializer=settings.CELERY_TASK_SERIALIZER,
    accept_content=settings.CELERY_ACCEPT_CONTENT,
    result_serializer=settings.CELERY_RESULT_SERIALIZER,
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=settings.CELERY_TASK_TIME_LIMIT,
    task_soft_time_limit=settings.CELERY_TASK_TIME_LIMIT - 30,  # Soft limit 30s before hard limit
    result_expires=3600,  # Results expire after 1 hour
    worker_prefetch_multiplier=1,  # Fair task distribution
    worker_max_tasks_per_child=50,  # Restart worker after 50 tasks to prevent memory leaks
    worker_pool=worker_pool,
)
