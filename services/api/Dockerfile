FROM python:3.12-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PIP_NO_CACHE_DIR=1

WORKDIR /app
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

COPY services/api /app/services/api
WORKDIR /app/services/api

FROM base AS dev
RUN pip install --upgrade pip && pip install -e /app/services/api
EXPOSE 8000
CMD ["uvicorn", "manga_api.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]

FROM base AS production
RUN pip install --upgrade pip && pip install /app/services/api \
    && useradd --create-home --shell /usr/sbin/nologin appuser

USER appuser
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --retries=3 CMD curl -fsS http://127.0.0.1:8000/health || exit 1
CMD ["uvicorn", "manga_api.main:app", "--host", "0.0.0.0", "--port", "8000"]
