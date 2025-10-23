# Multi-stage build for smaller final image
FROM python:3.12-slim as builder

# Set working directory
WORKDIR /app

# Install system dependencies required for building Python packages
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    make \
    libffi-dev \
    libssl-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir --user -r requirements.txt

# Final stage
FROM python:3.12-slim

# Set working directory
WORKDIR /app

# Install runtime dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    libsndfile1 \
    && rm -rf /var/lib/apt/lists/*

# Copy Python packages from builder
COPY --from=builder /root/.local /root/.local

# Copy application code
COPY src/ ./src/
COPY run_bot.py .
COPY pytest.ini .

# Create necessary directories
RUN mkdir -p data backups logs

# Make sure scripts in .local are usable
ENV PATH=/root/.local/bin:$PATH

# Set Python path
ENV PYTHONPATH=/app/src:$PYTHONPATH

# Environment variables
ENV PYTHONUNBUFFERED=1
ENV DATABASE_PATH=/app/data/gym_tracker.db

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD python -c "import sys; sys.path.insert(0, '/app/src'); from services.async_health_service import AsyncHealthService; import asyncio; service = AsyncHealthService(); result = asyncio.run(service.check_health()); sys.exit(0 if result.status == 'healthy' else 1)" || exit 1

# Expose port for health checks (if you add HTTP endpoint)
EXPOSE 8080

# Run the bot
CMD ["python", "run_bot.py"]
