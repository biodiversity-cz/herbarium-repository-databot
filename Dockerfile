FROM python:3.13@sha256:30e9dfceaeb4fba9bcb1f0db73ca0e6d0c04add3f48c53c69918d713f986213c

RUN pip install --no-cache-dir poetry
RUN useradd --uid 1000  --shell /bin/bash appuser

RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY pyproject.toml poetry.lock* /app/
RUN poetry config virtualenvs.create false \
 && poetry install --no-interaction --no-ansi --no-root

COPY src ./src
RUN chown -R appuser:appuser /app

EXPOSE 5000

USER appuser
ENTRYPOINT ["python", "src/main.py"]
