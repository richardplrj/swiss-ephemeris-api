# Swiss Ephemeris Open API
# Python 3.11 is required: pyswisseph 2.10.3.2 ships prebuilt wheels only up to
# cp311, so the slim image needs no C compiler.
FROM python:3.11-slim

# Faster, quieter Python in a container.
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    SWISSAPI_EPHE_PATH=/app/ephe

WORKDIR /app

# Install deps first for better layer caching.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# App code + bundled ephemeris data files (~6 MB, committed to the repo).
COPY app/ ./app/
COPY ephe/ ./ephe/

# Cloud Run / most PaaS inject $PORT; default to 8080 locally.
ENV PORT=8080
EXPOSE 8080

# Single worker: the engine serializes on a process-global lock anyway
# (swisseph keeps ayanamsha/topocentre in C globals). Scale with instances.
CMD ["sh", "-c", "exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8080} --workers 1"]
