FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    HF_HUB_DISABLE_TELEMETRY=1

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends libgl1 libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml ./

# Install dependencies before copying frequently changed application code.
RUN python -m pip install --upgrade pip \
    && python -m pip install --index-url https://download.pytorch.org/whl/cpu \
        --extra-index-url https://pypi.org/simple \
        torch==2.4.1+cpu torchvision==0.19.1+cpu \
    && python -m pip install '.[test]'

COPY solver_app/fetch_unimernet.py /tmp/fetch_unimernet.py
RUN python /tmp/fetch_unimernet.py \
    && rm /tmp/fetch_unimernet.py \
    && rm -rf /opt/unimernet_small/.cache

ENV HF_HUB_OFFLINE=1 \
    TRANSFORMERS_OFFLINE=1

RUN groupadd --system app \
    && useradd --system --gid app --home-dir /app app \
    && chown -R app:app /app /opt/unimernet_small

COPY --chown=app:app solver_app ./solver_app
RUN python -m pip install --no-deps .

COPY --chown=app:app tests ./tests

USER app

EXPOSE 8000

CMD ["uvicorn", "solver_app.main:app", "--host", "0.0.0.0", "--port", "8000"]
