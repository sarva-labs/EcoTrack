"""Celery worker entry point for EcoTrack background tasks."""
from __future__ import annotations

from celery import Celery

from ecotrack.config import get_config

config = get_config()

app = Celery(
    "ecotrack_worker",
    broker=config.redis.url,
    backend=config.redis.url,
)

# Celery configuration
app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    task_routes={
        "ecotrack_worker.tasks.data_ingestion.*": {"queue": "data"},
        "ecotrack_worker.tasks.model_training.*": {"queue": "ml"},
    },
)

# Auto-discover tasks from the tasks package
app.autodiscover_tasks(["ecotrack_worker.tasks"])

if __name__ == "__main__":
    app.start()
