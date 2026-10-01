# ===========================================
# C2PRO Backend - Multi-Stage Dockerfile
# ===========================================
#
# Build:
#   docker build -t c2pro-api .
#
# Run:
#   docker run -p 8000:8000 --env-file .env c2pro-api
#
# Multi-stage build reduces final image size by ~50%
# - Builder stage: installs dependencies with build tools
# - Runtime stage: minimal image with only runtime requirements

# ===========================================
# Stage 1: Builder
# ===========================================
FROM python:3.11-slim AS builder

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Create virtual environment
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

 # Install Python dependencies
 COPY requirements.txt constraints.txt .
 RUN pip install --no-cache-dir --upgrade pip && \
     pip install --no-cache-dir --only-binary=:all: -r requirements.txt -c constraints.txt

# SEC-002: Spanish spaCy NER model for src.core.privacy.anonymizer's Presidio
# PERSON/LOCATION/PHONE_NUMBER recognizers (GATE 8, AnthropicWrapper). Pinned
# to wheel URL because `spacy download` generates a malformed URL with spacy 3.7.x.
# Travels with the `COPY --from=builder /opt/venv` below.
RUN pip install --no-cache-dir \
    https://github.com/explosion/spacy-models/releases/download/es_core_news_md-3.7.0/es_core_news_md-3.7.0-py3-none-any.whl

# ===========================================
# Stage 2: Runtime
# ===========================================
FROM python:3.11-slim AS runtime

# Metadata
LABEL maintainer="C2Pro Team <dev@c2pro.app>"
LABEL description="C2Pro Backend API"
LABEL version="1.0.0"

# Environment
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app \
    PATH="/opt/venv/bin:$PATH"

# Install runtime dependencies only (no build tools)
# Includes Tesseract OCR for scanned PDF text extraction
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    libpq5 \
    tesseract-ocr \
    tesseract-ocr-spa \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Create non-root user
RUN groupadd --gid 1000 appgroup && \
    useradd --uid 1000 --gid appgroup --shell /bin/bash --create-home appuser

# Working directory
WORKDIR /app

# Copy virtual environment from builder
COPY --from=builder /opt/venv /opt/venv

# Copy only production runtime surfaces. COPY defaults to root:root here,
# keeping runtime code/config immutable to the non-root app user.
# Requirements/constraints were consumed in the builder and the resulting
# virtualenv is copied above.
COPY src/ ./src/
COPY alembic/ ./alembic/
COPY alembic.ini ./alembic.ini
COPY scripts/ ./scripts/
COPY start.sh ./start.sh
RUN sed -i 's/\r$//' /app/start.sh /app/scripts/*.sh

# Create uploads directory with proper ownership for non-root user
RUN mkdir -p /app/uploads && chown appuser:appgroup /app/uploads

# Switch to non-root user
USER appuser

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD sh -c 'curl -f http://localhost:${PORT:-8000}/health || exit 1'

# Default image role is API-only. Railway worker and scheduler services reuse
# this image with explicit run_worker.sh / run_scheduler.sh start commands.
CMD ["bash", "scripts/run_api.sh"]
