# syntax=docker/dockerfile:1
FROM python:3.10-slim as base

# Prevent Python from writing .pyc files and enable unbuffered stdout/stderr for clean MCP transport
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Install dependencies in a clean virtual environment
FROM base as builder
RUN apt-get update && apt-get install -y --no-install-recommends gcc && rm -rf /var/lib/apt/lists/*
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

COPY pyproject.toml .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir .

# Final lean runtime image
FROM base as runner
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Run as non-root user for container security
RUN useradd -m -u 1001 appuser
WORKDIR /app

# Copy application source code
COPY . /app/
RUN chown -R appuser:appuser /app

USER appuser

# Expose HTTP/SSE port (used if running transport=sse)
EXPOSE 8000

# Default entrypoint runs the standard stdio MCP server
ENTRYPOINT ["python", "mcp_server.py"]
