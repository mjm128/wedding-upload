import pytest
from unittest.mock import patch

@pytest.fixture(scope="module")
def client():
    from app.main import app
    from fastapi.testclient import TestClient
    with TestClient(app) as c:
        yield c

def test_slideshow_order(client):
    # Test "newest" order
    response = client.get("/slideshow/feed?order=newest")
    assert response.status_code == 200
    data = response.json()
    items = data["items"]
    # Check that items are sorted by created_at descending
    for i in range(len(items) - 1):
        assert items[i]["created_at"] >= items[i+1]["created_at"]

    # Test "random" order (default)
    response = client.get("/slideshow/feed")
    assert response.status_code == 200

def test_admin_media_visibility(client):
    # Log in as admin
    response = client.get("/admin/login?token=magic", follow_redirects=True)
    assert response.status_code == 200

    # Upload a file to ensure there's at least one item
    content = b"fake image content for admin test"
    files = {"file": ("admin_test.jpg", content, "image/jpeg")}
    client.cookies.set("guest_name", "AdminTestUser")
    client.cookies.set("guest_uuid", "admin-test-uuid")
    response = client.post("/upload", files=files, data={"caption": "Admin Test Caption"})
    assert response.status_code == 200

    # Fetch media from admin endpoint
    response = client.get("/slideshow/feed?admin_mode=true")
    assert response.status_code == 200
    data = response.json()
    items = data["items"]

    # Check that the response contains the filename and original_filename
    assert len(items) > 0
    assert "filename" in items[0]
    assert "original_filename" in items[0]

def test_my_uploads_endpoint(client):
    # Set a unique UUID for this test
    test_uuid = "my-uploads-test-uuid"
    client.cookies.set("guest_uuid", test_uuid)
    client.cookies.set("guest_name", "MyUploadsUser")

    # Upload a file
    content = b"fake image content for my-uploads test"
    files = {"file": ("my_uploads_test.jpg", content, "image/jpeg")}
    response = client.post("/upload", files=files, data={"caption": "My Uploads Test"})
    assert response.status_code == 200

    # Fetch uploads for this user
    response = client.get("/my-uploads")
    assert response.status_code == 200
    data = response.json()
    assert len(data) > 0
    assert data[0]["caption"] == "My Uploads Test"

def test_public_stats_endpoint(client):
    response = client.get("/public/stats")
    assert response.status_code == 200
    data = response.json()
    assert "photos" in data
    assert "videos" in data
    assert "total_media" in data

def test_admin_stats_endpoint(client):
    # Log in as admin
    client.get("/admin/login?token=magic", follow_redirects=True)

    response = client.get("/admin/stats")
    assert response.status_code == 200
    data = response.json()
    assert "disk_total_gb" in data
    assert "media_total" in data
    assert "cpu_percent" in data
