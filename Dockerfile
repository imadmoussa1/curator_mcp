# syntax=docker/dockerfile:1

# 1. Grab official high-performance uv binary
FROM ghcr.io/astral-sh/uv:0.5.21 AS uv_bin

# 2. Build stage using python-slim + uv
FROM python:3.10-slim AS builder

# Enable unbuffered stream output and bytecode optimization
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

WORKDIR /app

# Copy uv binary from official image
COPY --from=uv_bin /uv /uvx /bin/

# Install dependencies into /opt/venv using uv (ultra-fast cached install)
RUN --mount=type=cache,target=/root/.cache/uv \
    python -m venv /opt/venv

ENV PATH="/opt/venv/bin:$PATH"

COPY pyproject.toml .
RUN --mount=type=cache,target=/root/.cache/uv \
    uv pip install --no-cache .

# 3. Final lean production runtime image
FROM python:3.10-slim AS runner

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:$PATH"

# Run as non-root user for container security
RUN useradd -m -u 1001 appuser
WORKDIR /app

# Copy virtualenv from builder
COPY --from=builder /opt/venv /opt/venv

# Copy application code
COPY . /app/
RUN chown -R appuser:appuser /app

USER appuser

# Expose HTTP/SSE port
EXPOSE 8000

# Default entrypoint runs the standard stdio MCP server
ENTRYPOINT ["python", "mcp_server.py"]
