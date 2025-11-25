import os
from pydantic_settings import BaseSettings
from typing import Optional

class Settings(BaseSettings):
    EVENT_TIMEZONE: str = "America/Los_Angeles"
    MAX_MEDIA_SIZE_MB: int = 500
    MAX_VIDEO_DURATION_SEC: int = 60
    MAX_LOCAL_STORAGE_GB: float = 40.0
    GENERATE_VIDEO_THUMBNAILS: bool = True
    VIDEO_THUMBNAIL_TIMESTAMP: float = 2.0
    THROTTLE_DEFAULT_LIMIT: int = 5
    THROTTLE_WINDOW_MIN: int = 10
    SLIDESHOW_REFRESH_INTERVAL_SEC: int = 300
    ADMIN_PASSWORD: str = "changeme"
    ADMIN_MAGIC_TOKEN: str = "magic"
    DISCORD_WEBHOOK_URL: Optional[str] = None
    RCLONE_REMOTE_NAME: str = "gdrive"
    POST_UPLOAD_ACTION_URL: Optional[str] = None
    POST_UPLOAD_ACTION_LABEL: Optional[str] = None
    PURGE_PIN: str = "0523"

    # Paths - Use local paths for dev/test if /data is not writable
    UPLOAD_DIR: str = "/data/uploads" if os.access("/data", os.W_OK) else "data/uploads"
    THUMBNAIL_DIR: str = "/data/thumbnails" if os.access("/data", os.W_OK) else "data/thumbnails"
    ARCHIVE_DIR: str = "/data/archives" if os.access("/data", os.W_OK) else "data/archives"
    DATABASE_URL: str = "sqlite+aiosqlite:////data/database.sqlite" if os.access("/data", os.W_OK) else "sqlite+aiosqlite:///data/database.sqlite"

    class Config:
        env_file = ".env"

settings = Settings()
