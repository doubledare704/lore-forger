# Stage 1: Build the frontend (SvelteKit)
FROM node:22-slim AS frontend-builder
WORKDIR /app/frontend
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# Stage 2: Prepare the backend and dependencies
FROM ghcr.io/astral-sh/uv:python3.13-bookworm-slim AS backend-builder
WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-cache --no-dev
COPY backend/ ./backend/
# Copy the built frontend into the backend's static directory
COPY --from=frontend-builder /app/frontend/build ./backend/app/static

# Final Stage: Lean production image
FROM python:3.13-slim-bookworm
WORKDIR /app

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH="/app/.venv/bin:$PATH"

# Copy the virtual environment and backend code
COPY --from=backend-builder /app/.venv /app/.venv
COPY --from=backend-builder /app/backend /app/backend

# Default port for Cloud Run
EXPOSE 8080

# Run the FastAPI app using uvicorn
CMD ["uvicorn", "backend.app.main:app", "--host", "0.0.0.0", "--port", "8080"]
