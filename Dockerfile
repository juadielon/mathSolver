FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY pyproject.toml README.md ./
COPY solver_app ./solver_app
COPY tests ./tests

RUN python -m pip install --upgrade pip \
    && python -m pip install '.[test]' \
    && groupadd --system app \
    && useradd --system --gid app --home-dir /app app \
    && chown -R app:app /app

USER app

EXPOSE 8000

CMD ["uvicorn", "solver_app.main:app", "--host", "0.0.0.0", "--port", "8000"]
