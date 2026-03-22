FROM python:3.12-slim

WORKDIR /app

# System deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Python deps
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# App code
COPY . .

# Create dirs for persistent data
RUN mkdir -p /data /app/db

# Symlink db to persistent volume
RUN ln -sf /data/pgk_laboral.db /app/db/pgk_laboral.db

EXPOSE 8765

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8765/api/health || exit 1

CMD ["python", "app.py", "--host", "0.0.0.0", "--port", "8765"]
