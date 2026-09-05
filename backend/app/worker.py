"""Celery worker configuration.

Broker + result backend both run on the Olares system KVRocks (Redis-API
compatible). Locally we use the redis:7-alpine container from docker-compose.
"""

from celery import Celery
from celery.schedules import crontab

from app.config import settings


def _redis_url(db: int) -> str:
    pw = f":{settings.redis_password}@" if settings.redis_password else ""
    return f"redis://{pw}{settings.redis_host}:{settings.redis_port}/{db}"


celery_app = Celery(
    "insilo",
    broker=_redis_url(0),
    backend=_redis_url(1),
    include=[
        "app.tasks.transcribe",
        "app.tasks.summarize",
        "app.tasks.embed",
        "app.tasks.notify",
        "app.tasks.aufraeumen",
    ],
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
    # Die beiden Aufbewahrungsfristen durchsetzen. Einmal am Tag reicht:
    # beide sind in Tagen bemessen, und der Lauf ist wiederholbar.
    #
    # Der Beat läuft eingebettet im Worker (`--beat` im Deployment), nicht
    # als eigener Prozess. Das ist zulässig, weil genau ein Worker läuft —
    # `workloads.insilo-worker.replicaCount` steht auf 1, und die Box hat
    # einen Knoten. Bei mehreren Replikaten würde jeder seinen eigenen
    # Beat mitbringen und der Job liefe mehrfach.
    beat_schedule={
        "aufraeumen-taeglich": {
            "task": "aufraeumen",
            # 03:30 Ortszeit — außerhalb der Bürozeiten, in denen
            # aufgenommen wird.
            "schedule": crontab(hour=3, minute=30),
        },
    },
)
