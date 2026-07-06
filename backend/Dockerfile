FROM python:3.11-slim

WORKDIR /app

# Unbuffered stdout/stderr so logs stream straight to CloudWatch on Fargate,
# and no .pyc writes (keeps the read-only-friendly image cleaner).
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Install python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Run as a non-root user (defense in depth for Fargate)
RUN useradd --create-home --uid 1000 appuser

# Copy application code owned by the runtime user
COPY --chown=appuser:appuser . .

# Ensure the media folders the app writes to are owned by appuser
RUN mkdir -p /app/data/images /app/data/videos \
    && chown -R appuser:appuser /app/data

USER appuser

EXPOSE 8000

# Production command: no --reload. Single uvicorn process per container on
# purpose — on Fargate we scale horizontally with more tasks rather than
# packing multiple workers into one task (simpler memory/health accounting).
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
