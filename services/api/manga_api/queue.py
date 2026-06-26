from celery import Celery

from manga_api.config import get_settings


def make_celery_client() -> Celery:
    settings = get_settings()
    return Celery("manga_api_client", broker=settings.redis_url, backend=settings.redis_url)


def enqueue_mock_render_panel(job_id: str) -> None:
    enqueue_render_panel(job_id)


def enqueue_render_panel(job_id: str) -> None:
    celery = make_celery_client()
    celery.send_task("manga_worker.render_panel", args=[job_id])


def enqueue_director_generate_draft(job_id: str) -> None:
    celery = make_celery_client()
    celery.send_task("manga_worker.director_generate_draft", args=[job_id])


def enqueue_founder_demo_run(job_id: str) -> None:
    celery = make_celery_client()
    celery.send_task("manga_worker.founder_demo_run", args=[job_id])
