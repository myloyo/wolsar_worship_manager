FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    POETRY_VERSION=2.3.3

WORKDIR /app
RUN pip install --no-cache-dir "poetry==$POETRY_VERSION" \
    && poetry config virtualenvs.create false

COPY pyproject.toml poetry.lock README.md ./
RUN poetry install --only main --no-root --no-interaction --no-ansi

COPY worship_bot ./worship_bot
COPY alembic.ini ./
COPY migrations ./migrations

CMD ["sh", "-c", "alembic upgrade head && uvicorn worship_bot.main:app --host 0.0.0.0 --port 8000"]