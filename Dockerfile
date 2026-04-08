FROM python:3.11-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PATH="/app/.venv/bin:$PATH" PYTHONPATH=/app

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app

COPY pyproject.toml uv.lock ./

RUN uv sync --all-groups --no-install-project

COPY . .

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=3s --retries=3 --start-period=10s \
    CMD python -c "import httpx; httpx.get('http://localhost:8000')"

CMD ["sh", "-c", "exec textual serve elia_chat/__main__.py --host 0.0.0.0 --port 8000 --url $CHAT_DOMEN"]
