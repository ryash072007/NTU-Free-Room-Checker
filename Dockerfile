# Stage 1: Build React frontend SPA
FROM node:22-slim AS frontend-builder
WORKDIR /build/web

# Install frontend dependencies cleanly using committed package-lock.json
COPY web/package.json web/package-lock.json ./
RUN npm ci

# Copy frontend source and configuration
COPY web/ ./

# Compile TypeScript and bundle with Vite into /build/web/dist
RUN npm run build

# Stage 2: Production Python runtime
FROM python:3.11-slim AS runtime

WORKDIR /app

# Ensure unbuffered standard output and avoid byte-code creation
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    NTU_ROOM_CHECKER_DB=/data/ntu_schedule.db \
    NTU_ROOM_CHECKER_STATIC_DIR=/app/web/dist

# Install application dependencies and the ntu-room-checker package
COPY pyproject.toml README.md ./
COPY src/ ./src/
RUN pip install --no-cache-dir .

# Copy built frontend assets from builder stage
COPY --from=frontend-builder /build/web/dist /app/web/dist

# Expose HTTP port
EXPOSE 8000

# Health check using Python's standard library to ping /api/v1/health
HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/v1/health')" || exit 1

# Start the unified production web service
ENTRYPOINT ["python", "-m", "ntu_room_checker", "serve", "--host", "0.0.0.0", "--port", "8000"]
