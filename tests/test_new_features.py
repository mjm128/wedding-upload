import os
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
import uuid

# Mock environment before importing app
os.environ["UPLOAD_DIR"] = "/tmp/test_uploads"
os.environ["ARCHIVE_DIR"] = "/tmp/test_archives"
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///:memory:"

# Ensure dirs exist
os.makedirs(os.environ["UPLOAD_DIR"], exist_ok=True)
os.makedirs(os.environ["ARCHIVE_DIR"], exist_ok=True)

from app.main import app

client = TestClient(app)

@pytest.fixture(scope="module", autouse=True)
def setup_db():
    with TestClient(app) as c:
        yield c

def test_my_uploads_endpoint(setup_db):
    # Test upload and then fetch my uploads
    client = setup_db
    content = f"fake image {uuid.uuid4()}".encode()

    # Set cookie for user identity
    client.cookies.set("guest_name", "TestUser")
    client.cookies.set("table_number", "1")

    # Upload
    response = client.post("/upload",
        files={"file": ("test.jpg", content, "image/jpeg")},
        data={"caption": "My Caption"}
    )
    assert response.status_code == 200

    # Fetch My Uploads
    response = client.get("/my-uploads")
    assert response.status_code == 200
    data = response.json()
    assert len(data) >= 1
    assert data[0]["caption"] == "My Caption"
    assert data[0]["type"] == "image"

def test_public_stats_endpoint(setup_db):
    client = setup_db
    response = client.get("/public/stats")
    assert response.status_code == 200
    data = response.json()
    assert "photos" in data
    assert "videos" in data
