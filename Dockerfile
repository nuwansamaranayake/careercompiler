# syntax=docker/dockerfile:1
FROM python:3.12-slim

WORKDIR /srv
ENV PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1

# git is required: aignite-groundwork resolves from a git+https URL (see pyproject.toml)
RUN apt-get update && apt-get install -y --no-install-recommends git \
    && rm -rf /var/lib/apt/lists/*

# NOTE: aignite-groundwork is a sibling editable dependency in local dev
# (pip install -e ../groundwork). In CI / image builds it resolves from the
# published wheel or a git ref; see .github/workflows/ci.yml.
COPY pyproject.toml README.md ./
RUN pip install --upgrade pip

COPY . .
RUN pip install .

# Build-time facts for the root page. Baked from build args so the deployed page can state
# what is actually running; absent values render as "unknown", never as a placeholder.
ARG APP_VERSION=unreleased
ARG GIT_SHA=unknown
ARG BUILD_TIME=unknown
ENV APP_VERSION=$APP_VERSION GIT_SHA=$GIT_SHA BUILD_TIME=$BUILD_TIME

EXPOSE 8000
# Migrate, assert the expected table count (Standard 4), then serve.
CMD ["sh", "-c", "alembic upgrade head && python scripts/check_migrations.py && exec uvicorn app.main:app --host 0.0.0.0 --port 8000"]
