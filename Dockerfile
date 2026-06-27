FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# The catalog is re-seeded on startup from app/data/vocabulary_full.json, so a
# fresh container comes up populated even without a persisted database file.
EXPOSE 8000

# Most PaaS providers inject a $PORT. Default to 8000 for local `docker run`.
# --proxy-headers + --forwarded-allow-ips lets the app see the real https scheme
# behind the platform's reverse proxy, so generated URLs aren't insecure (http).
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --proxy-headers --forwarded-allow-ips=*"]
