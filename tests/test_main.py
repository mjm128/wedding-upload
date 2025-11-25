import pytest
from unittest.mock import patch

@pytest.fixture(scope="module")
def client():
    from app.main import app
    from fastapi.testclient import TestClient
    with TestClient(app) as c:
        yield c

def test_health_check(client):
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["database"] == "ok"
    assert data["disk"] == "ok"

def test_upload_flow(client):
    import uuid
    content = f"fake image content {uuid.uuid4()}".encode()
    files = {"file": ("test.jpg", content, "image/jpeg")}

    client.cookies.set("guest_name", "TestUser")
    client.cookies.set("guest_uuid", "test-uuid")

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

def test_config_endpoint(client):
    response = client.get("/config")
    assert response.status_code == 200
    data = response.json()
    assert "max_file_size_mb" in data
