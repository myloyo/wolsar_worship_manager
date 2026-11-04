# Worship backend

Python 3.12+, FastAPI, PostgreSQL. See the root README for complete setup.
Run `poetry install --with dev` here; configuration is loaded from the root `.env`.
Run `poetry run alembic upgrade head`, then `poetry run uvicorn worship_bot.main:app --reload`.
Run `poetry run pytest -q` and `poetry run mypy`.
