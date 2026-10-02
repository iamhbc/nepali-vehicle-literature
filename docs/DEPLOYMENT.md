# Deployment

```
Netlify  ──────────▶  frontend (static React build)
Python host ───────▶  backend API (Docker: Render, Railway, Fly.io, any VM)
PostgreSQL ────────▶  database (+ pgvector when VECTOR_BACKEND=pgvector)
```

Netlify alone cannot run the Python API. Deploy the two parts separately.

## 1. Database

Use any managed PostgreSQL 14+ (Render, Neon, Supabase, RDS). For `VECTOR_BACKEND=pgvector` the server must allow `CREATE EXTENSION vector` (Render, Neon and Supabase do). `postgres://` URLs are accepted and rewritten for the psycopg driver.

Tables are created on first start and the corpus is imported automatically when the database is empty.

## 2. API

### Render (blueprint included)

1. Push the repository to GitHub.
2. In Render, choose **New → Blueprint** and select the repo. `render.yaml` creates `nvl-api` (Docker) and `nvl-db` (Postgres).
3. Set the secret environment variables:
   - `ANTHROPIC_API_KEY`
   - `CORS_ORIGINS` (your Netlify URL, e.g. `https://nepali-vehicle-literature.netlify.app`)
   - `ADMIN_USERNAME`
   - `ADMIN_PASSWORD_HASH`, generated locally with:

     ```bash
     backend/.venv/bin/python scripts/hash_password.py
     ```

4. Deploy, then check `https://<api>/api/health`.

### Any Docker host

```bash
docker build -f backend/Dockerfile -t nvl-api .
```

```bash
docker run -p 8000:8000 --env-file .env -e DATABASE_URL=postgresql://… nvl-api
```

### Local production-like stack

```bash
docker compose up --build
```

This starts PostgreSQL + pgvector and the API.

### Production checklist

- `ENVIRONMENT=production`, `TRUST_PROXY_HEADERS=true` behind a proxy.
- Strong `JWT_SECRET` and a bcrypt `ADMIN_PASSWORD_HASH`; `CORS_ORIGINS` limited to your frontend origin.
- `ANTHROPIC_API_KEY` set as a secret, never in the frontend.
- Review `RATE_LIMIT_ANALYZE_PER_HOUR` against your AI budget. Repeat analyses are served from cache.
- With more than one API instance, use `VECTOR_BACKEND=pgvector` and a shared rate limiter.
- Back up the database: it holds researcher decisions and the audit log.

## 3. Frontend (Netlify)

`netlify.toml` at the repository root builds `frontend/` and publishes `frontend/dist`, with SPA routing and security headers (camera allowed for this origin only).

1. **Add new site → Import from Git**, then pick the repo. The settings come from `netlify.toml`.
2. Set the environment variable `VITE_API_BASE_URL=https://<your-api-host>` (no trailing slash).
3. Deploy, then add the Netlify URL to the API's `CORS_ORIGINS`.

## Optional components

- **Transformer embeddings**:

  ```bash
  pip install -e "backend[embeddings]"
  ```

  Then set `EMBEDDING_PROVIDER=sentence-transformers`. Expect about 1 GB more image size and a slower cold start.
- **Local OCR**: install Tesseract with the `nep` traineddata and set `OCR_PROVIDER=tesseract`. It is weaker than vision models on painted lettering.
- **Municipalities**:

  ```bash
  backend/.venv/bin/python scripts/import_municipalities.py <csv> --source "<authority, year>"
  ```

  Or upload the CSV in Researcher area → Tools.
