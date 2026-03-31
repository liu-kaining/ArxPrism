# =============================================================================
# ArxPrism Python Application Dockerfile
# =============================================================================
# Multi-stage build for smaller production image
# Stage 1: Dependencies
# Stage 2: Application

FROM python:3.11-slim as dependencies

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Create virtual environment
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Install Python dependencies
COPY requirements.txt .
RUN pip install -r requirements.txt

# =============================================================================
# Production Stage
# =============================================================================

FROM python:3.11-slim as production

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# Install curl for healthcheck (docker-compose healthcheck requires curl)
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy virtual environment from dependencies stage
COPY --from=dependencies /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Create non-root user for security
RUN useradd --create-home --shell /bin/bash appuser \
    && mkdir -p /home/appuser/app \
    && chown -R appuser:appuser /home/appuser

# Set working directory
WORKDIR /home/appuser/app

# Copy application source
COPY --chown=appuser:appuser src/ ./src/
COPY --chown=appuser:appuser pyproject.toml .

# Switch to non-root user
USER appuser

# Default command (can be overridden by docker-compose)
CMD ["python", "-c", "print('Use docker-compose to run services')"]
