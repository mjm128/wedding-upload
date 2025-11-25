import os
import pytest
import tempfile
import shutil

@pytest.fixture(scope="session", autouse=True)
def setup_test_environment():
    """Sets up a consistent test environment for all tests."""
    TEST_DIR = tempfile.mkdtemp(prefix="wedding_app_")
    os.environ["UPLOAD_DIR"] = os.path.join(TEST_DIR, "uploads")
    os.environ["THUMBNAIL_DIR"] = os.path.join(TEST_DIR, "thumbnails")
    os.environ["ARCHIVE_DIR"] = os.path.join(TEST_DIR, "archives")
    os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///{os.path.join(TEST_DIR, 'test.db')}"
    os.environ["MAX_LOCAL_STORAGE_GB"] = "0.0001" # 100KB

    os.makedirs(os.environ["UPLOAD_DIR"], exist_ok=True)
    os.makedirs(os.environ["THUMBNAIL_DIR"], exist_ok=True)
    os.makedirs(os.environ["ARCHIVE_DIR"], exist_ok=True)

    # Create dummy rclone.conf
    rclone_conf_path = os.path.join(TEST_DIR, "rclone.conf")
    with open(rclone_conf_path, "w") as f:
        f.write("[mock]\ntype = local\n")
    os.environ["RCLONE_CONFIG"] = rclone_conf_path

    yield

    shutil.rmtree(TEST_DIR)
