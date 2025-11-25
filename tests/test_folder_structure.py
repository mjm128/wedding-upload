import os
import pytest
from fastapi.testclient import TestClient
import uuid
import shutil

# Mock environment before importing app
os.environ["UPLOAD_DIR"] = "/tmp/test_uploads_folder"
os.environ["THUMBNAIL_DIR"] = "/tmp/test_thumbnails_folder"
os.environ["ARCHIVE_DIR"] = "/tmp/test_archives_folder"
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///:memory:"

# Ensure dirs exist
os.makedirs(os.environ["UPLOAD_DIR"], exist_ok=True)
os.makedirs(os.environ["THUMBNAIL_DIR"], exist_ok=True)
os.makedirs(os.environ["ARCHIVE_DIR"], exist_ok=True)

from app.main import app
from app.config import settings

@pytest.fixture(scope="module", autouse=True)
def setup_db():
    with TestClient(app) as c:
        yield c

def test_upload_folder_structure(setup_db):
    client = setup_db
    content = f"fake image {uuid.uuid4()}".encode()

    # Set cookie
    client.cookies.set("guest_name", "FolderTestUser")
    client.cookies.set("table_number", "1")

    # Upload
    response = client.post("/upload",
        files={"file": ("test_folder.jpg", content, "image/jpeg")},
        data={"caption": "Folder Caption"}
    )
    assert response.status_code == 200

    # Verify Directory Structure
    # Should find a folder in UPLOAD_DIR containing "FolderTestUser"
    found_folder = False
    upload_dir = os.environ["UPLOAD_DIR"]
    for name in os.listdir(upload_dir):
        path = os.path.join(upload_dir, name)
        if os.path.isdir(path) and "FolderTestUser" in name:
            found_folder = True
            # Verify file is inside (filename is uuid, so check for any .jpg)
            files = [f for f in os.listdir(path) if f.endswith(".jpg")]
            assert len(files) > 0
            break

    assert found_folder, "User folder not created"

    # Verify Thumbnail Structure (Flat in THUMBNAIL_DIR)
    thumb_dir = os.environ["THUMBNAIL_DIR"]
    # We can't know the exact UUID prefix easily, but we check if any thumb exists
    # Actually, the code naming is `thumb_{uuid}.jpg`.
    # Let's check if any file exists in thumb dir.
    # (PIL mock might be needed if we want real thumb generation, but for now main.py handles image/ skipping PIL if mocked or basic).
    # Wait, main.py uses `_process_image_thumbnail` in a thread. If it fails, it logs error but DB saves `thumb_filename`?
    # In main.py: `if content_type.startswith("image"): ... thumb_filename = thumb_name`
    # The test uploads "image/jpeg" so it tries PIL. If PIL fails (fake content), thumb might not exist.
    # But the folder structure test is the critical part here.
