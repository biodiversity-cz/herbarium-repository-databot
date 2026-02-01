FROM python:3.14@sha256:17bc9f1d032a760546802cc4e406401eb5fe99dbcb4602c91628e73672fa749c

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
