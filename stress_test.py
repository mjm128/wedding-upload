import os
import shutil
import time
import zipfile
import unittest
from unittest.mock import MagicMock, patch
import sys
import tempfile
import importlib

# Add project root to path
sys.path.append(os.getcwd())

class TestPruning(unittest.TestCase):
    def setUp(self):
        self.ARCHIVE_DIR = os.environ["ARCHIVE_DIR"]
        # Clear out the dir for a clean test
        if os.path.exists(self.ARCHIVE_DIR):
            shutil.rmtree(self.ARCHIVE_DIR)
        os.makedirs(self.ARCHIVE_DIR)

    def test_pruning_logic(self):
        from daemon import archive_daemon
        import app.config
        importlib.reload(app.config)
        importlib.reload(archive_daemon)
        # 1. Create dummy large zip files
        zip1 = os.path.join(self.ARCHIVE_DIR, "batch_1.zip")
        zip2 = os.path.join(self.ARCHIVE_DIR, "batch_2.zip")

        with open(zip1, 'wb') as f:
            f.write(os.urandom(1024 * 1024)) # 1MB

        # Ensure timestamp diff
        os.utime(zip1, (time.time() - 100, time.time() - 100))

        with open(zip2, 'wb') as f:
            f.write(os.urandom(1024 * 1024)) # 1MB

        # 2. Run pruning
        archive_daemon.smart_pruning(verify_remote=False)

        # 3. Verify zip1 is gone (oldest)
        self.assertFalse(os.path.exists(zip1), "Oldest zip should be deleted")

        # zip2 should also be deleted as usage (1MB) > limit (100KB)
        # The pruning loop continues until usage < limit.
        self.assertFalse(os.path.exists(zip2), "Second zip should also be deleted if over limit")

if __name__ == '__main__':
    unittest.main()
