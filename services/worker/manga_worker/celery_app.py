from celery import Celery

from manga_api.config import get_settings

settings = get_settings()

celery_app = Celery("manga_worker", broker=settings.redis_url, backend=settings.redis_url)
celery_app.conf.update(
    accept_content=["json"],
    result_serializer="json",
    task_serializer="json",
    task_track_started=True,
)

import manga_worker.tasks  # noqa: E402,F401
