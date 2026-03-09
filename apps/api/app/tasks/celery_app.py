from celery import Celery

from app.core.settings import settings

celery_app = Celery("docsai", broker=settings.redis_url, backend=settings.redis_url)
celery_app.conf.update(
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    task_default_queue="document-processing",
)
