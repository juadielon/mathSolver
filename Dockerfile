FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    HF_HUB_DISABLE_TELEMETRY=1

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends libgl1 libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml README.md ./
COPY solver_app ./solver_app
COPY tests ./tests

RUN python -m pip install --upgrade pip \
    && python -m pip install --index-url https://download.pytorch.org/whl/cpu \
        --extra-index-url https://pypi.org/simple \
        torch==2.4.1+cpu torchvision==0.19.1+cpu \
    && python -m pip install '.[test]' \
    && python -m solver_app.fetch_unimernet \
    && rm -rf /opt/unimernet_small/.cache

ENV HF_HUB_OFFLINE=1 \
    TRANSFORMERS_OFFLINE=1

RUN groupadd --system app \
    && useradd --system --gid app --home-dir /app app \
    && chown -R app:app /app /opt/unimernet_small

USER app

EXPOSE 8000

CMD ["uvicorn", "solver_app.main:app", "--host", "0.0.0.0", "--port", "8000"]
