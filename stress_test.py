import os
import shutil
import time
import zipfile
import unittest
from unittest.mock import MagicMock, patch
import sys
import tempfile

# Add project root to path
sys.path.append(os.getcwd())

# Create temp dirs for testing
TEST_DIR = tempfile.mkdtemp()
ARCHIVE_DIR = os.path.join(TEST_DIR, "archives")
UPLOAD_DIR = os.path.join(TEST_DIR, "uploads")
os.makedirs(ARCHIVE_DIR, exist_ok=True)
os.makedirs(UPLOAD_DIR, exist_ok=True)

# Set environment variables BEFORE importing app/daemon
os.environ["ARCHIVE_DIR"] = ARCHIVE_DIR
os.environ["UPLOAD_DIR"] = UPLOAD_DIR
os.environ["MAX_LOCAL_STORAGE_GB"] = "0.0001" # 100KB
os.environ["RCLONE_REMOTE_NAME"] = "mock"
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///:memory:"

# Now import
from daemon import archive_daemon
from app.config import settings

class TestPruning(unittest.TestCase):
    def tearDown(self):
        # We don't remove TEST_DIR here because we reuse it across tests (logging keeps file open)
        # But for correctness we should close logging handlers.
        pass

    @classmethod
    def tearDownClass(cls):
        # Close logging handlers to allow cleanup
        import logging
        logging.shutdown()
        if os.path.exists(TEST_DIR):
            shutil.rmtree(TEST_DIR)

    @patch("daemon.archive_daemon.subprocess.run")
    def test_pruning_logic(self, mock_subprocess):
        # 1. Create dummy large zip files
        zip1 = os.path.join(ARCHIVE_DIR, "batch_1.zip")
        zip2 = os.path.join(ARCHIVE_DIR, "batch_2.zip")

        with open(zip1, 'wb') as f:
            f.write(os.urandom(1024 * 1024)) # 1MB

        # Ensure timestamp diff
        os.utime(zip1, (time.time() - 100, time.time() - 100))

        with open(zip2, 'wb') as f:
            f.write(os.urandom(1024 * 1024)) # 1MB

        # 2. Mock rclone verify response
        mock_subprocess.return_value.returncode = 0
        mock_subprocess.return_value.stdout = '[{"Name":"batch_1.zip"}]'

        # 3. Run pruning
        archive_daemon.smart_pruning()

        # 4. Verify zip1 is gone (oldest)
        self.assertFalse(os.path.exists(zip1), "Oldest zip should be deleted")

        # zip2 should also be deleted as usage (1MB) > limit (100KB)
        # The pruning loop continues until usage < limit.
        self.assertFalse(os.path.exists(zip2), "Second zip should also be deleted if over limit")

if __name__ == '__main__':
    unittest.main()
