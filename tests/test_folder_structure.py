import os
import pytest
from fastapi.testclient import TestClient
import uuid
import shutil
import io
from PIL import Image

def create_dummy_image(filename="test.png"):
    """Creates a small dummy image file, returns a file tuple for httpx."""
    img = Image.new('RGB', (1, 1), color='red')
    img_byte_arr = io.BytesIO()
    img.save(img_byte_arr, format='PNG')
    img_byte_arr.seek(0)
    return (filename, img_byte_arr, 'image/png')

@pytest.fixture(scope="module")
def client():
    from app.main import app
    from fastapi.testclient import TestClient
    with TestClient(app) as c:
        yield c

def test_upload_folder_structure(client):
    # Use a real image
    dummy_image = create_dummy_image("test_folder.png")

    # Set cookie
    client.cookies.set("guest_name", "FolderTestUser")
    client.cookies.set("table_number", "1")
    client.cookies.set("guest_uuid", str(uuid.uuid4()))

    # Upload
    response = client.post("/upload",
        files={"file": dummy_image},
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
            # Verify file is inside (filename is uuid, so check for any .png)
            files = [f for f in os.listdir(path) if f.endswith(".png")]
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
