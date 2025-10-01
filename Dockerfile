FROM python:3.13@sha256:081e7d0f7e520a653648602d10dcf11a832c8480b98698795d5fe8f456bbba4d

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
