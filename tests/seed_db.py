import pytest
from fastapi.testclient import TestClient
from app.main import app

@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c

def test_seed_database(client):
    content = b"fake image content for seeding"
    files = {"file": ("seed.jpg", content, "image/jpeg")}
    client.cookies.set("guest_name", "SeedUser")
    client.cookies.set("guest_uuid", "seed-uuid")
    response = client.post("/upload", files=files, data={"caption": "Seed Caption"})
    assert response.status_code == 200
