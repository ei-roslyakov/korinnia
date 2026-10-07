# syntax=docker/dockerfile:1.7
# Backend + worker image (same image, different command).

FROM python:3.12-slim-bookworm AS base
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/opt/venv \
    PATH="/opt/venv/bin:$PATH"
COPY --from=ghcr.io/astral-sh/uv:0.12 /uv /usr/local/bin/uv
# Media processing tools: ffmpeg (audio/video previews), poppler (PDF thumbnails).
RUN apt-get update \
 && apt-get install -y --no-install-recommends ffmpeg poppler-utils \
 && rm -rf /var/lib/apt/lists/*
RUN groupadd --system --gid 1000 korinnia \
 && useradd --system --uid 1000 --gid korinnia --home-dir /app --shell /usr/sbin/nologin korinnia \
 && mkdir -p /data/media \
 && chown -R korinnia:korinnia /data
WORKDIR /app

# --- dev: includes test/lint tools; source is bind-mounted by docker-compose.override.yml
FROM base AS dev
COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv uv sync --frozen --no-install-project
COPY . .
USER korinnia
ENTRYPOINT ["/app/docker-entrypoint.sh"]
CMD ["api"]

# --- prod: runtime dependencies only
FROM base AS prod
COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv uv sync --frozen --no-install-project --no-dev
COPY --chown=korinnia:korinnia app ./app
COPY --chown=korinnia:korinnia alembic ./alembic
COPY --chown=korinnia:korinnia alembic.ini docker-entrypoint.sh ./
USER korinnia
VOLUME ["/data/media"]
EXPOSE 8000
ENTRYPOINT ["/app/docker-entrypoint.sh"]
CMD ["api"]
