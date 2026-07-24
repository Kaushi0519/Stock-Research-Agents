# Shared image for both the `backend` (FastAPI) and `scheduler` services --
# same codebase and dependencies, only the command differs (set per-service
# in docker-compose.yml). Secrets (API keys, Robinhood login) are never
# baked in here -- they're injected at runtime via docker-compose's
# `env_file: .env`, which is gitignored and excluded from the build context
# via .dockerignore.

FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY src/ src/

EXPOSE 8000

CMD ["uvicorn", "src.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
