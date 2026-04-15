FROM python:3.13-slim-bookworm@sha256:061b6e52a07ab675f0e4a9428c5a8ee6bed996983427f4691f6bebf29c56d9dc

RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 \
    curl \
    build-essential \
    libglib2.0-0 \
 && rm -rf /var/lib/apt/lists/*

# Ultralytics nemá CPU/GPU split v Poetry, musí se mu takto (+pyproject) vnucovat
RUN pip install torch==2.7.1 torchvision==0.22.1 pillow==11.3.0 --index-url https://download.pytorch.org/whl/cpu

RUN pip install --no-cache-dir poetry

WORKDIR /app

COPY pyproject.toml poetry.lock* /app/

RUN poetry config virtualenvs.create false \
 && poetry install --no-interaction --no-ansi --no-root \
 && rm -rf /root/.cache

COPY src ./src

EXPOSE 5000

RUN useradd -m -u 1000 -s /bin/bash appuser \
 && chown -R appuser:appuser /app

USER appuser

ENTRYPOINT ["python", "src/main.py"]
