import os
import pytest
from unittest.mock import patch

# Set env vars BEFORE importing app.main/database
# We use patch.dict to ensure it's set for the duration of the test module loading?
# No, patch.dict works on a dict object. os.environ is a dict-like object.
# But imports happen at module level.
# So we need to set them in the module scope before imports.

os.environ["UPLOAD_DIR"] = "/tmp/test_uploads"
os.environ["ARCHIVE_DIR"] = "/tmp/test_archives"
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///:memory:"

# Ensure dirs exist
os.makedirs(os.environ["UPLOAD_DIR"], exist_ok=True)
os.makedirs(os.environ["ARCHIVE_DIR"], exist_ok=True)

from fastapi.testclient import TestClient
from app.main import app

@pytest.fixture(scope="module", autouse=True)
def setup_db():
    # Initialize the DB for tests
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
    import uuid
    content = f"fake image content {uuid.uuid4()}".encode()
    files = {"file": ("test.jpg", content, "image/jpeg")}

    response = client.post("/upload", files=files, data={"caption": "Test Caption"})

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert "id" in data

    # Check Slideshow Feed
    response = client.get("/slideshow/feed")
    assert response.status_code == 200
    feed = response.json()
    assert len(feed["items"]) > 0

    # Find our item (since other tests might add items)
    found = False
    for item in feed["items"]:
        if item["caption"] == "Test Caption":
            found = True
            assert item["type"] == "image"
            break
    assert found, "Uploaded item not found in feed"

def test_config_endpoint(setup_db):
    client = setup_db
    response = client.get("/config")
    assert response.status_code == 200
    data = response.json()
    assert "max_file_size_mb" in data
