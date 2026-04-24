# 1. UPGRADE: Move to Bookworm for long-term security support
FROM python:3.13-slim-bookworm

# 2. OBSERVABILITY: Prevent Python from buffering stdout/stderr
ENV PYTHONUNBUFFERED=1
ENV DEBIAN_FRONTEND=noninteractive

# 3. OS DEPENDENCIES
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg exiftool && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# 4. PYTHON DEPENDENCIES: Added 'gunicorn' to the orchestration layer
RUN pip install --no-cache-dir "markitdown[all]" fastapi uvicorn python-multipart gunicorn pytest httpx

# 5. LOCAL OVERWRITES
COPY . /app
RUN pip install --no-cache-dir ./packages/markitdown

# 6. PERMISSION ENFORCEMENT: Ensure UID 1000 can write to /tmp and owns /app
RUN chown -R 1000:1000 /app && chmod 1777 /tmp

# 7. ZERO TRUST: Drop root privileges
USER 1000:1000
EXPOSE 8080

# 8. PROCESS ORCHESTRATION: Gunicorn manages Uvicorn workers
# - workers: 2 (Prevents a single bad PDF from taking down the entire API)
# - timeout: 120 (Prevents Gunicorn from killing workers during slow, CPU-bound PDF parsing)
#CMD ["gunicorn", "app:app", "--workers", "2", "--worker-class", "uvicorn.workers.UvicornWorker", "--bind", "0.0.0.0:8080", "--timeout", "120"]
CMD ["gunicorn", "app:app", "--workers", "2", "--worker-class", "uvicorn.workers.UvicornWorker", "--bind", "0.0.0.0:8080", "--timeout", "600"]
