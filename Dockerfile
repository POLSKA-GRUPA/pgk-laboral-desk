FROM node:20-slim AS frontend-builder

WORKDIR /build
COPY laboral-frontend/package.json laboral-frontend/package-lock.json* ./
RUN npm ci --prefer-offline 2>/dev/null || npm install
COPY laboral-frontend/ .
RUN npm run build

FROM python:3.12-slim AS backend

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    libpango-1.0-0 \
    libpangocairo-1.0-0 \
    libgdk-pixbuf-2.0-0 \
    libcairo2 \
    libffi-dev \
    fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/*

COPY laboral-frontend/.env.example .env.example

COPY laboral-backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY laboral-backend/ .
COPY --from=frontend-builder /build/dist /app/static

COPY data/ /app/data/

RUN mkdir -p /data /app/db

RUN addgroup --system appgroup && adduser --system --ingroup appgroup appuser \
    && chown -R appuser:appgroup /data /app/db /app

USER appuser

ENV PYTHONUNBUFFERED=1
ENV DATABASE_URL=sqlite:////data/laboral.db
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8000/api/health || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
