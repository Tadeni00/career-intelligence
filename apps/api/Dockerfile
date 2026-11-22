# Career Intelligence API.
# Build context is the repo root: the image needs alembic.ini + migrations/ +
# apps/api + packages/matching, mirroring how alembic and pytest see the tree.
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /srv/app

RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml alembic.ini ./
COPY apps/api ./apps/api
COPY packages ./packages
COPY migrations ./migrations

RUN pip install --no-cache-dir -e .

ENV PYTHONPATH=/srv/app/apps/api:/srv/app/packages/matching \
    STORAGE_DIR=/srv/storage

EXPOSE 8011

# Migrate on startup so a fresh volume self-initialises; on an existing
# volume this is a no-op. Never seed data here.
CMD ["sh", "-c", "python -m alembic upgrade head && python -m uvicorn app.main:app --host 0.0.0.0 --port 8011"]
