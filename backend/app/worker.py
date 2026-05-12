"""Celery worker configuration.

Broker + result backend both run on the Olares system KVRocks (Redis-API
compatible). Locally we use the redis:7-alpine container from docker-compose.
"""

from celery import Celery

from app.config import settings


def _redis_url(db: int) -> str:
    pw = f":{settings.redis_password}@" if settings.redis_password else ""
    return f"redis://{pw}{settings.redis_host}:{settings.redis_port}/{db}"


celery_app = Celery(
    "insilo",
    broker=_redis_url(0),
    backend=_redis_url(1),
    include=["app.tasks.transcribe"],
)

celery_app.conf.update(
    task_default_queue="insilo",
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    timezone=settings.app_timezone,
    enable_utc=True,
    # Hard time limit for transcription tasks. Long meetings on tiny model
    # take a few minutes; large-v3 on GPU is much faster.
    task_time_limit=60 * 30,        # 30 min hard kill
    task_soft_time_limit=60 * 25,   # 25 min warn
)
