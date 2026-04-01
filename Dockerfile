FROM python:3.14@sha256:ffebef43892dd36262fa2b042eddd3320d5510a21f8440dce0a650a3c124b51d

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
