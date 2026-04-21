FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_LINK_MODE=copy

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates curl \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir uv

COPY pyproject.toml uv.lock README.md ./
COPY src ./src
COPY config ./config

RUN uv sync --frozen --no-dev

RUN mkdir -p /app/.runtime-data

ENV POLYMARKET_ALERT_BOT_DATA_DIR=/app/.runtime-data

EXPOSE 8080

CMD ["uv", "run", "polymarket-alert-bot", "serve"]
