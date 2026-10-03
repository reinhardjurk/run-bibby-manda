# Backend + built frontend in one serverless container image.
FROM node:22-bookworm-slim AS frontend
WORKDIR /fe
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
ARG GIT_SHA=dev
ENV VITE_BUILD=${GIT_SHA}
RUN npm run build

FROM python:3.11-slim-bookworm
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 UV_SYSTEM_PYTHON=1
# WeasyPrint runtime libraries
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpango-1.0-0 libpangoft2-1.0-0 libharfbuzz0b libffi8 libjpeg62-turbo libopenjp2-7 \
    fonts-dejavu-core shared-mime-info curl \
    && rm -rf /var/lib/apt/lists/*
COPY --from=ghcr.io/astral-sh/uv:0.8.17 /uv /usr/local/bin/uv
WORKDIR /app
COPY backend/pyproject.toml backend/uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project
COPY backend/ ./
RUN uv sync --frozen --no-dev
COPY --from=frontend /fe/dist /app/static
ARG GIT_SHA=dev
ENV BIBBY_GIT_SHA=${GIT_SHA} BIBBY_STATIC_DIR=/app/static PATH="/app/.venv/bin:$PATH"
EXPOSE 8080
HEALTHCHECK CMD curl -fs http://localhost:8080/health || exit 1
# Migrations are NOT run here – they run as a separate CI step before deploy.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080", "--proxy-headers", "--forwarded-allow-ips=*"]
