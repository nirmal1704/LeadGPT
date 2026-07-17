from celery import Celery

from config import settings

celery_app = Celery(
    "leadgpt",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    task_always_eager=False,
    task_time_limit=1800,
    task_soft_time_limit=1700,
    worker_prefetch_multiplier=1,
    task_acks_late=True,
)

celery_app.autodiscover_tasks(["worker"])
