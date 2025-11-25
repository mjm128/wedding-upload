import pytest
from sqlalchemy import text
import uuid

@pytest.fixture(scope="module")
def client():
    from app.main import app
    from fastapi.testclient import TestClient
    with TestClient(app) as c:
        yield c

def test_my_uploads_endpoint(client):
    # Test upload and then fetch my uploads
    content = f"fake image {uuid.uuid4()}".encode()

    # Set cookie for user identity
    client.cookies.set("guest_name", "TestUser")
    client.cookies.set("table_number", "1")
    client.cookies.set("guest_uuid", str(uuid.uuid4()))

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

def test_public_stats_endpoint(client):
    response = client.get("/public/stats")
    assert response.status_code == 200
    data = response.json()
    assert "photos" in data
    assert "videos" in data

def test_admin_stats_endpoint(client):
    # Setup admin login via token
    client.cookies.set("admin_token", "magic")

    response = client.get("/admin/stats")
    assert response.status_code == 200
    data = response.json()

    assert "cpu_percent" in data
    assert "ram_percent" in data
    assert "media_total" in data
    # Validate that it didn't crash on psutil
