FROM python:3.12-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PIP_NO_CACHE_DIR=1

WORKDIR /app
COPY services/api /app/services/api
COPY services/worker /app/services/worker
WORKDIR /app/services/worker

FROM base AS dev
RUN pip install --upgrade pip \
    && pip install -e /app/services/api \
    && pip install -e /app/services/worker
CMD ["celery", "-A", "manga_worker.celery_app.celery_app", "worker", "--loglevel=info"]

FROM base AS production
RUN pip install --upgrade pip \
    && pip install /app/services/api \
    && pip install /app/services/worker \
    && useradd --create-home --shell /usr/sbin/nologin appuser

USER appuser
CMD ["celery", "-A", "manga_worker.celery_app.celery_app", "worker", "--loglevel=info"]
