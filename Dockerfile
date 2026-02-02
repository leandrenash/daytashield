# DataShield Docker Image
# Multi-stage build for minimal image size

# Build stage
FROM python:3.11-slim as builder

WORKDIR /app

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy project files
COPY pyproject.toml README.md LICENSE ./
COPY src/ src/

# Build wheel
RUN pip install --no-cache-dir build && \
    python -m build --wheel

# Runtime stage
FROM python:3.11-slim as runtime

WORKDIR /app

# Install runtime dependencies for PDF processing
RUN apt-get update && apt-get install -y --no-install-recommends \
    libmagic1 \
    && rm -rf /var/lib/apt/lists/*

# Copy wheel from builder
COPY --from=builder /app/dist/*.whl /tmp/

# Install datashield
RUN pip install --no-cache-dir /tmp/*.whl && \
    rm /tmp/*.whl

# Create non-root user
RUN useradd --create-home --shell /bin/bash datashield
USER datashield

# Set working directory
WORKDIR /data

# Default command
ENTRYPOINT ["datashield"]
CMD ["--help"]

# Labels
LABEL org.opencontainers.image.title="DataShield"
LABEL org.opencontainers.image.description="The missing validation layer between unstructured data and AI systems"
LABEL org.opencontainers.image.source="https://github.com/datashield/datashield"
LABEL org.opencontainers.image.licenses="Apache-2.0"
