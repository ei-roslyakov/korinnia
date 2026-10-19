# syntax=docker/dockerfile:1.7
# nginx image: serves the built frontend and proxies /api to the backend (plain HTTP;
# TLS is terminated by the ingress / load balancer).
# Build context: repository root.

FROM node:22-alpine AS frontend-build
WORKDIR /src
COPY frontend/package.json frontend/package-lock.json ./
RUN --mount=type=cache,target=/root/.npm npm ci --no-audit --no-fund
COPY frontend/ ./
# Release version shown in the app's footer (set by the Publish workflow).
ARG APP_VERSION=dev
ENV VITE_APP_VERSION=$APP_VERSION
RUN npm run build \
 && find dist -type f \( -name '*.js' -o -name '*.css' -o -name '*.html' -o -name '*.svg' -o -name '*.json' -o -name '*.map' \) \
      -exec gzip -k -9 {} \;

# --- base: nginx + config (used directly in dev, where Vite serves the frontend)
FROM nginx:1.31.7-alpine AS base
RUN rm -f /etc/nginx/conf.d/default.conf
COPY deploy/nginx/nginx.conf /etc/nginx/nginx.conf
COPY deploy/nginx/snippets/ /etc/nginx/snippets/
COPY deploy/nginx/templates/ /etc/nginx/templates/
ENV NGINX_MAX_BODY_SIZE=2048m \
    NGINX_BACKEND_UPSTREAM=backend:8000
RUN mkdir -p /usr/share/nginx/html \
 && chown nginx:nginx /etc/nginx/conf.d
# Unprivileged (uid 101). Listening on port 80 still works: Docker and the Helm chart set
# net.ipv4.ip_unprivileged_port_start=0. conf.d is written at start-up from the templates.
USER 101
HEALTHCHECK --interval=15s --timeout=3s --retries=5 CMD wget -qO- http://127.0.0.1/nginx-health || exit 1

# --- prod: base + built static frontend
FROM base AS prod
COPY --from=frontend-build /src/dist/ /usr/share/nginx/html/
