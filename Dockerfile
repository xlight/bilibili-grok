FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml .
RUN pip install --no-cache-dir .

COPY src/ src/
COPY config.yaml .

RUN mkdir -p data

ENV PYTHONUNBUFFERED=1

CMD ["python", "-m", "grok.main"]
