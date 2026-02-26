FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY pyproject.toml README.md ./
RUN pip install --no-cache-dir .

# Copy application code
COPY src/ src/
COPY config.yaml .

# Create required directory
RUN mkdir -p data

# Set environment variable for unbuffered output
ENV PYTHONUNBUFFERED=1

# Verify health check endpoint during docker build (optional)
# HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
#   CMD curl -f http://localhost:8080/health || exit 1

CMD ["python", "-m", "grok.main"]
