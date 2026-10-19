# syntax=docker/dockerfile:1.7
# Backend + worker image (same image, different command).

# Debian 13 (trixie): newer ffmpeg/poppler with far fewer known CVEs than bookworm.
FROM python:3.15-slim-trixie AS base
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/opt/venv \
    UV_PYTHON_DOWNLOADS=never \
    PATH="/opt/venv/bin:$PATH"
COPY --from=ghcr.io/astral-sh/uv:0.12 /uv /usr/local/bin/uv
# Media processing tools: ffmpeg (audio/video previews), poppler (PDF thumbnails).
RUN apt-get update \
 && apt-get install -y --no-install-recommends ffmpeg poppler-utils fonts-dejavu-core \
 && rm -rf /var/lib/apt/lists/*
# uv installs everything (the base image's Python must match requires-python: no downloads);
# pip is unused and only adds its bundled packages to vulnerability scans.
RUN python -m pip uninstall -y --root-user-action=ignore pip
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
# Release version (set by the Publish workflow); late in the file so it never busts the cache.
ARG APP_VERSION=dev
ENV APP_VERSION=$APP_VERSION
USER korinnia
VOLUME ["/data/media"]
EXPOSE 8000
ENTRYPOINT ["/app/docker-entrypoint.sh"]
CMD ["api"]
