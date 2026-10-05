# syntax=docker/dockerfile:1.7

# ─── Stage 1: builder — генерирует dist/ из Jinja2-шаблонов ─────────────────
FROM python:3.12-slim AS builder
WORKDIR /app

RUN pip install --no-cache-dir jinja2

COPY . .
RUN python3 build.py

# ─── Stage 2: runtime — статика отдаётся nginx ──────────────────────────────
FROM nginx:1.27-alpine AS runtime

COPY nginx/default.conf /etc/nginx/conf.d/default.conf
COPY --from=builder /app/dist /usr/share/nginx/html

EXPOSE 80

# 127.0.0.1, а не localhost: внутри контейнера localhost резолвится в ::1
# (IPv6), а nginx слушает только 0.0.0.0:80 — wget получает "Connection
# refused" и контейнер уходит в unhealthy, хотя сайт отвечает.
HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
    CMD wget --spider -q http://127.0.0.1/ || exit 1
