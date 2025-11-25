import os
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from app.main import app, get_db
from app.config import settings

# Override settings for test
settings.UPLOAD_DIR = "/tmp/test_uploads"
settings.ARCHIVE_DIR = "/tmp/test_archives"
settings.DATABASE_URL = "sqlite+aiosqlite:///:memory:"

os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
os.makedirs(settings.ARCHIVE_DIR, exist_ok=True)

client = TestClient(app)

@pytest.fixture(scope="module", autouse=True)
def setup_db():
    # We need to initialize the DB for tests
    # Since TestClient calls the app, the lifespan context manager should run.
    # However, TestClient(app) runs lifespan context manager on __enter__ which happens per request or if used as context manager.
    # The current code uses `client = TestClient(app)` globally, which doesn't trigger lifespan automatically unless used in `with`.
    # But wait, TestClient only runs lifespan in `with TestClient(app) as client`.

    with TestClient(app) as c:
        yield c

def test_health_check(setup_db):
    client = setup_db
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["database"] == "ok"
    assert data["disk"] == "ok"

def test_upload_flow(setup_db):
    client = setup_db
    # 1. Upload a file
    # Mocking file upload
    import uuid
    content = f"fake image content {uuid.uuid4()}".encode()
    files = {"file": ("test.jpg", content, "image/jpeg")}

    response = client.post("/upload", files=files, data={"caption": "Test Caption"})

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert "id" in data

    # 2. Check if file exists
    # We can't easily check the unique filename without querying DB or hacking return,
    # but the health check confirms disk write.

    # 3. Check Slideshow Feed
    response = client.get("/slideshow/feed")
    assert response.status_code == 200
    feed = response.json()
    assert len(feed["items"]) > 0
    item = feed["items"][0]
    assert item["caption"] == "Test Caption"
    assert item["type"] == "image"

def test_config_endpoint(setup_db):
    client = setup_db
    response = client.get("/config")
    assert response.status_code == 200
    data = response.json()
    assert "max_file_size_mb" in data
