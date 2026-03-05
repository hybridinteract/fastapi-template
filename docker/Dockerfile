# ==================== Multi-stage Dockerfile ====================
# Stage 1: Builder
FROM python:3.13-slim AS builder

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

RUN pip install uv

WORKDIR /app

COPY pyproject.toml ./

RUN uv pip install --system -r pyproject.toml


# ==================== Stage 2: Runtime ====================
FROM python:3.13-slim AS runtime

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    curl \
    netcat-openbsd \
    redis-tools \
    && rm -rf /var/lib/apt/lists/*

RUN groupadd -r appuser && \
    useradd -r -g appuser -u 1000 -m appuser

WORKDIR /app

COPY --from=builder /usr/local/lib/python3.13/site-packages /usr/local/lib/python3.13/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

COPY --chown=appuser:appuser . .

RUN mkdir -p /app/logs /app/migrations/versions && \
    chown -R appuser:appuser /app/logs /app/migrations

USER root
RUN chmod +x /app/docker/*.sh 2>/dev/null || true
USER appuser

EXPOSE 8000

HEALTHCHECK --interval=15s --timeout=5s --start-period=60s --retries=10 \
    CMD curl -f http://localhost:8000/health || exit 1

ENTRYPOINT ["/app/docker/docker-entrypoint.sh"]

CMD ["uvicorn", "app.core.main:app", "--host", "0.0.0.0", "--port", "8000"]
