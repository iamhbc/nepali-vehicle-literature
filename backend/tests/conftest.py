import os
import tempfile
from pathlib import Path

import bcrypt
import pytest

_tmp = Path(tempfile.mkdtemp(prefix="nvl-test-"))
os.environ.update({
    "ENVIRONMENT": "test",
    "DATABASE_URL": f"sqlite:///{_tmp / 'test.db'}",
    "LLM_PROVIDER": "baseline",
    "ANTHROPIC_API_KEY": "",
    "OCR_PROVIDER": "none",
    "ADMIN_USERNAME": "researcher",
    "ADMIN_PASSWORD_HASH": bcrypt.hashpw(b"correct horse", bcrypt.gensalt(4)).decode(),
    "JWT_SECRET": "test-secret-key-that-is-long-enough-32b",
})

from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402


@pytest.fixture(scope="session")
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture(scope="session")
def admin_headers(client):
    r = client.post("/api/admin/login", json={"username": "researcher", "password": "correct horse"})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['token']}"}


@pytest.fixture()
def db(client):
    from app.db import SessionLocal

    with SessionLocal() as session:
        yield session
