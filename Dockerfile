FROM python:3.11-slim

WORKDIR /app

COPY pyproject.toml uv.lock README.md /app/
COPY elia_chat /app/elia_chat
COPY .env.example /app/.env.example

RUN pip install --no-cache-dir uv && uv pip install --system .

EXPOSE 8000

CMD ["python", "-m", "elia_chat", "web", "--host", "0.0.0.0", "--port", "8000"]
