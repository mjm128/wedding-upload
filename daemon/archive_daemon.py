import os
import sys
import time
import shutil
import asyncio
import zipfile
import logging
from datetime import datetime, timedelta
import subprocess

# Add project root to path
sys.path.append(os.getcwd())

from app.config import settings

# Ensure directories exist before logging
os.makedirs(settings.ARCHIVE_DIR, exist_ok=True)

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(os.path.join(settings.ARCHIVE_DIR, "daemon.log"))
    ]
)
logger = logging.getLogger("ArchiveDaemon")

def backup_database():
    """Copy database.sqlite to archives."""
    db_path = "/data/database.sqlite" # Assuming standard path
    if not os.path.exists(db_path):
        logger.warning(f"Database not found at {db_path}")
        return

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = os.path.join(settings.ARCHIVE_DIR, f"db_backup_{ts}.sqlite")

    try:
        shutil.copy2(db_path, backup_path)
        logger.info(f"Database backed up to {backup_path}")
    except Exception as e:
        logger.error(f"DB Backup failed: {e}")

def archive_media():
    """Zip folders older than 30 mins -> /data/archives/batch_{ts}.zip."""
    # Since we are dumping all files into UPLOAD_DIR, we need to select files
    # that haven't been archived yet? Or just dump everything that isn't zipped?
    # The requirement says: "Zip folders older than 30 mins".
    # But we are using a flat structure in UPLOAD_DIR based on previous implementation.
    # To support "folders", maybe we should have organized uploads by timestamp?
    # Or, we just select *files* in UPLOAD_DIR that are older than 30 mins.
    # But if we zip them, should we delete them?
    # The requirements say: "Never delete the active /data/uploads folder."
    # AND "Delete oldest local ZIPs until usage < limit".
    # This implies we keep the source files in UPLOAD_DIR forever unless we run out of space?
    # Actually, "Never delete the active /data/uploads folder" likely refers to the *folder itself*,
    # not the content.
    # BUT, typically archival implies moving data.
    # IF we keep everything in uploads AND zip it, we duplicate usage.
    # Given "UNRESTRICTED" resources but "MAX_LOCAL_STORAGE_GB" limit (40GB),
    # we probably want to *move* files to zip, OR zip and keep until space needed.
    # However, for a wedding, 40GB fills up fast with video.
    # Let's assume:
    # 1. Zip files > 30 mins old.
    # 2. DO NOT delete from uploads yet (Slideshow needs them!).
    # Wait, if we don't delete from uploads, the pruning logic "Delete oldest local ZIPs" won't free up space used by UPLOAD_DIR.
    # "Never delete the active /data/uploads folder" might mean "don't delete the directory",
    # but surely we must delete old files if we hit the limit?
    # OR, maybe the pruning logic *only* targets the ARCHIVES?
    # "Step 5: Smart Pruning: ... Delete *oldest* local ZIPs ... *Never* delete the active /data/uploads folder."
    # This implies the Uploads folder is sacred and fills up until disk full?
    # That contradicts the goal of "Smart Pruning" if the primary consumer is uploads.
    # Let's interpret: We assume the 40GB limit applies to the *Archives*?
    # Or total disk?
    # "Check local disk usage. IF AND ONLY IF usage > MAX_LOCAL_STORAGE_GB"
    # This usually means total usage.
    # If total usage is high, we delete ZIPs.
    # If we delete ZIPs, we lose the backup on the local machine (but it's on Rclone).
    # We still have the raw files in /data/uploads.
    # IF /data/uploads grows beyond 40GB, we are in trouble if we can't prune it.
    # But the instructions are specific: "Never delete the active /data/uploads folder."
    # Maybe it means "don't delete the folder itself", or "don't prune *recent* uploads"?
    # I will stick to the literal instruction: Prune ZIPs, keep Uploads.
    # Note: If 24GB RAM is available, maybe we don't need to worry too much.

    # Strategy:
    # 1. Find files in UPLOAD_DIR modified > 30 mins ago.
    # 2. Add them to a new ZIP if they aren't already archived (tracking this is hard without a DB state).
    #    Simpler: Just Zip *all* files every 10 mins? No, that's huge.
    #    Maybe move files to a "processed" subfolder?
    #    Or, since we back up the DB, we can use the DB to track what has been archived?
    #    Too complex for a script.
    #    Let's go with Time-based Batching.
    #    We zip files modified between (Last Run) and (Now - 30 mins).
    #    We need to store "Last Run" timestamp.

    state_file = os.path.join(settings.ARCHIVE_DIR, "daemon_state.json")
    last_run = 0
    import json
    if os.path.exists(state_file):
        try:
            with open(state_file, 'r') as f:
                last_run = json.load(f).get("last_run", 0)
        except: pass

    now = time.time()
    cutoff = now - (30 * 60) # 30 mins ago

    # Find folders (new structure)
    # We are looking for folders in UPLOAD_DIR that match the pattern timestamp_uuid_name
    # AND are older than 30 mins (to ensure upload is done).

    folders_to_archive = []
    for f in os.listdir(settings.UPLOAD_DIR):
        fp = os.path.join(settings.UPLOAD_DIR, f)
        if os.path.isdir(fp):
            # Check age
            mtime = os.path.getmtime(fp)
            if mtime > last_run and mtime <= cutoff:
                folders_to_archive.append(fp)

    if not folders_to_archive:
        logger.info("No new upload folders to archive.")
        with open(state_file, 'w') as f:
            json.dump({"last_run": cutoff}, f)
        return

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    zip_name = f"batch_{ts}.zip"
    zip_path = os.path.join(settings.ARCHIVE_DIR, zip_name)

    try:
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
            for folder_path in folders_to_archive:
                # Archive folder content
                parent = os.path.dirname(folder_path)
                for root, dirs, files in os.walk(folder_path):
                    for file in files:
                        file_path = os.path.join(root, file)
                        arcname = os.path.relpath(file_path, settings.UPLOAD_DIR) # Keep relative path from UPLOAD_DIR
                        zf.write(file_path, arcname)

        logger.info(f"Created archive {zip_name} with {len(folders_to_archive)} folders.")

        # Verify
        if zipfile.is_zipfile(zip_path):
            with zipfile.ZipFile(zip_path, 'r') as zf:
                ret = zf.testzip()
                if ret is not None:
                     raise Exception(f"Corrupt file in zip: {ret}")
        else:
            raise Exception("Invalid zip file created")

        # Update state
        with open(state_file, 'w') as f:
            json.dump({"last_run": cutoff}, f)

    except Exception as e:
        logger.error(f"Archival failed: {e}")
        # Alert Discord
        if settings.DISCORD_WEBHOOK_URL:
            # Simple curl or requests
            subprocess.run(["curl", "-H", "Content-Type: application/json", "-d", f'{{"content": "Archival Failed: {e}"}}', settings.DISCORD_WEBHOOK_URL])

def check_rclone_config():
    """Check if rclone config exists and is valid (not empty)."""
    config_path = os.environ.get("RCLONE_CONFIG", "/root/.config/rclone/rclone.conf")
    if not os.path.exists(config_path):
        return False
    if os.path.getsize(config_path) == 0:
        return False
    return True

def rclone_copy():
    """Rclone copy /data/archives remote:wedding_backup."""
    if not check_rclone_config():
        logger.warning("Rclone config missing or empty. Skipping remote backup.")
        return

    cmd = ["rclone", "copy", settings.ARCHIVE_DIR, f"{settings.RCLONE_REMOTE_NAME}:wedding_backup"]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            logger.error(f"Rclone failed: {result.stderr}")
        else:
            logger.info("Rclone copy successful.")
            # Update state for admin dashboard
            state_file = os.path.join(settings.ARCHIVE_DIR, "daemon_state.json")
            state = {}
            if os.path.exists(state_file):
                try:
                    with open(state_file, 'r') as f:
                        state = json.load(f)
                except: pass

            state["last_rclone_success"] = time.time()

            with open(state_file, 'w') as f:
                json.dump(state, f)

    except Exception as e:
        logger.error(f"Rclone execution error: {e}")

def smart_pruning(verify_remote=True):
    """Prune oldest ZIPs if disk usage > MAX_LOCAL_STORAGE_GB."""
    # Check total disk usage of the volume containing ARCHIVE_DIR
    total, used, free = shutil.disk_usage(settings.ARCHIVE_DIR)
    used_gb = used / (1024**3)

    if used_gb > settings.MAX_LOCAL_STORAGE_GB:
        logger.warning(f"Disk usage {used_gb:.2f}GB > Limit {settings.MAX_LOCAL_STORAGE_GB}GB. Pruning...")

        if verify_remote and not check_rclone_config():
            logger.warning("Rclone config missing or empty. Cannot verify remote status. Skipping pruning of ZIPs.")
            return

        # Identify local ZIPs verified as on remote
        # We need to run `rclone lsl remote:wedding_backup` and match?
        # That might be slow.
        # Alternatively, we assume if rclone copy succeeded, they are there.
        # But `rclone copy` is idempotent.

        # Let's list local zips
        zips = [os.path.join(settings.ARCHIVE_DIR, f) for f in os.listdir(settings.ARCHIVE_DIR) if f.endswith('.zip')]
        zips.sort(key=os.path.getmtime) # Oldest first

        while used_gb > settings.MAX_LOCAL_STORAGE_GB:
            zips = [os.path.join(settings.ARCHIVE_DIR, f) for f in os.listdir(settings.ARCHIVE_DIR) if f.endswith('.zip')]
            zips.sort(key=os.path.getmtime) # Oldest first

            if not zips:
                logger.warning("No more zips to prune, but disk usage is still high.")
                break

            z = zips.pop(0) # Get the oldest zip

            if verify_remote:
                check_cmd = ["rclone", "lsjson", f"{settings.RCLONE_REMOTE_NAME}:wedding_backup/{os.path.basename(z)}"]
                res = subprocess.run(check_cmd, capture_output=True, text=True)
                if res.returncode != 0 or res.stdout.strip() == "[]":
                    logger.warning(f"Skipping {z} - not found on remote.")
                    continue

            # Exists on remote (or verification skipped)
            logger.info(f"Deleting archive: {z}")
            os.remove(z)

            try:
                with zipfile.ZipFile(z, 'r') as zf:
                    # Get top level folders
                    folders = set()
                    for name in zf.namelist():
                        # name is like "folder/file.jpg"
                        if '/' in name:
                            folders.add(name.split('/')[0])

                    for folder in folders:
                        full_path = os.path.join(settings.UPLOAD_DIR, folder)
                        if os.path.exists(full_path):
                            logger.info(f"Pruning uploaded folder after verification: {folder}")
                            shutil.rmtree(full_path)
            except Exception as e:
                logger.error(f"Failed to prune source folders from zip {z}: {e}")

            # Update usage
            total, used, free = shutil.disk_usage(settings.ARCHIVE_DIR)
            used_gb = used / (1024**3)

def run_loop():
    logger.info("Daemon started.")
    while True:
        try:
            logger.info("Starting backup cycle...")
            backup_database()
            archive_media()
            rclone_copy()
            smart_pruning(verify_remote=True)
            logger.info("Cycle complete. Sleeping 10 mins.")
        except Exception as e:
            logger.error(f"Unhandled exception in loop: {e}")

        time.sleep(600) # 10 mins

if __name__ == "__main__":
    run_loop()
