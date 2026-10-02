# Build from the repository root:  docker build -f backend/Dockerfile .
FROM python:3.12-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /srv

# Dependencies first so code changes don't invalidate this layer.
COPY backend/requirements.txt backend/requirements.txt
RUN pip install --upgrade pip && pip install -r backend/requirements.txt "psycopg[binary]>=3.2"
COPY backend/app backend/app

# Knowledge layer read at runtime (corpus, taxonomy, lexicon, references, geography).
COPY data/processed data/processed
COPY data/geo data/geo
COPY data/reference data/reference
COPY knowledge-base knowledge-base
COPY taxonomy taxonomy

RUN useradd --create-home --uid 10001 nvl && chown -R nvl /srv
USER nvl

ENV DATA_DIR=/srv/data \
    KNOWLEDGE_DIR=/srv/knowledge-base \
    TAXONOMY_PATH=/srv/taxonomy/taxonomy.v1.json \
    ENVIRONMENT=production \
    TRUST_PROXY_HEADERS=true \
    PORT=8000

EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s CMD python -c "import urllib.request,os; urllib.request.urlopen(f'http://127.0.0.1:{os.environ.get(\"PORT\",\"8000\")}/api/health')"
CMD ["sh", "-c", "uvicorn app.main:app --app-dir backend --host 0.0.0.0 --port ${PORT} --proxy-headers --forwarded-allow-ips='*'"]
