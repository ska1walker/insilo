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
        "app.tasks.waechter",
    ],
)

celery_app.conf.update(
    task_default_queue="insilo",
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    timezone=settings.app_timezone,
    enable_utc=True,
    # Vorgabe für die kleinen Aufgaben — Webhooks, Einbettungen,
    # Aufräumen. Erkennung und Zusammenfassung bringen seit 0.1.99 ihre
    # eigenen, viel großzügigeren Limits am `@shared_task` mit: diese
    # dreißig Minuten waren jahrelang für sie gedacht und haben ab
    # ungefähr zwanzig Minuten Aufnahme jede Verarbeitung abgeschnitten
    # (die Messung steht in `app/verarbeitungszeit.py`).
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
        # Alle fünf Minuten nach Besprechungen sehen, die in einem
        # Zwischenzustand hängen geblieben sind. Täglich reicht hier
        # nicht: eine Besprechung, die auf „wird transkribiert" steht,
        # blockiert für den Nutzer die ganze Nachbearbeitung, und bis
        # 0.1.98 stand sie dort für immer.
        "waechter": {
            "task": "waechter",
            "schedule": 300.0,
        },
    },
)
