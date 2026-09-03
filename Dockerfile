FROM python:3.11-slim

# Install system dependencies for Pillow image processing & health checks
RUN apt-get update && apt-get install -y --no-install-recommends \
    libjpeg-dev \
    zlib1g-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Create unprivileged application user
RUN groupadd -g 1000 appgroup && \
    useradd -u 1000 -g appgroup -s /bin/bash -m appuser

WORKDIR /app

# Install Python dependencies
COPY pyproject.toml .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir \
    "fastapi>=0.115.0" \
    "uvicorn[standard]>=0.30.0" \
    "sqlmodel>=0.0.22" \
    "pydantic>=2.8.0" \
    "apscheduler>=3.10.4" \
    "qrcode[pil]>=7.4.2" \
    "pillow>=10.0.0" \
    "jinja2>=3.1.4" \
    "python-multipart>=0.0.9" \
    "httpx>=0.27.0"

# Copy application source
COPY app/ ./app/

# Set environment defaults
ENV PYTHONUNBUFFERED=1 \
    DATA_DIR=/app/data \
    SERVER_HOST=0.0.0.0 \
    SERVER_PORT=8000

# Prepare persistent data directory with proper ownership
RUN mkdir -p /app/data && chown -R appuser:appgroup /app

USER appuser

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
  CMD curl -f http://localhost:8000/healthz || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
