# Infrastructure

Local development infrastructure is managed by Docker Compose from the repository root.

- PostgreSQL stores durable application state.
- Redis backs Celery job dispatch.
- MinIO provides S3-compatible object storage for source assets and rendered images.

Run the full stack with:

```bash
docker compose up --build
```
