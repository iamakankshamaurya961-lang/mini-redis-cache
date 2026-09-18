# ============================================
# Mini-Redis Cache — Production Dockerfile
# ============================================
FROM python:3.11-slim AS base

# Security: Create non-root user
RUN groupadd --gid 1000 appuser && \
    useradd --uid 1000 --gid appuser --shell /bin/bash --create-home appuser

# Set working directory
WORKDIR /app

# Copy source files
COPY lru_cache.py main.py ./
COPY static/ ./static/

# Switch to non-root user
USER appuser

# Expose port
EXPOSE 8000

# Health check (polls the health endpoint every 30s)
HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
    CMD python3 -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/api/health')" || exit 1

# Run the server
CMD ["python3", "main.py"]
