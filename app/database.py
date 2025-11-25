from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import declarative_base
from sqlalchemy import text
from app.config import settings
import os

# Ensure the directory for the database exists if it's a file path
if "sqlite" in settings.DATABASE_URL:
    db_path = settings.DATABASE_URL.replace("sqlite+aiosqlite://", "").replace("sqlite://", "")
    # Handle absolute path with 3 or 4 slashes
    if db_path.startswith("//"):
         db_path = db_path[1:] # remove one slash to make it /path/to/db (e.g. //data/db -> /data/db)
    elif db_path.startswith("/"):
        pass # Absolute path like /data/database.sqlite
    else:
        # Relative path like data/database.sqlite
        pass

    # If it looks like a file path, ensure dir exists
    if "/" in db_path:
        directory = os.path.dirname(db_path)
        # Avoid trying to create /data if we are not root and it fails, but logic should be sound
        if directory and not os.path.exists(directory):
             try:
                 os.makedirs(directory, exist_ok=True)
             except OSError as e:
                 print(f"Warning: Could not create directory {directory}: {e}")

engine = create_async_engine(
    settings.DATABASE_URL,
    connect_args={"check_same_thread": False}, # Needed for SQLite
)

SessionLocal = async_sessionmaker(autocommit=False, autoflush=False, bind=engine, class_=AsyncSession)

Base = declarative_base()

async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

        # Check if guest_uuid column exists and add it if not.
        # This is a simple migration solution.
        try:
            await conn.execute(text("SELECT guest_uuid FROM media LIMIT 1;"))
        except:
            await conn.execute(text("ALTER TABLE media ADD COLUMN guest_uuid VARCHAR;"))
            await conn.execute(text("CREATE INDEX ix_media_guest_uuid ON media (guest_uuid);"))

        # Add view_count and last_viewed columns if they don't exist
        try:
            await conn.execute(text("SELECT view_count FROM media LIMIT 1;"))
        except:
            await conn.execute(text("ALTER TABLE media ADD COLUMN view_count INTEGER DEFAULT 0;"))

        try:
            await conn.execute(text("SELECT last_viewed FROM media LIMIT 1;"))
        except:
            await conn.execute(text("ALTER TABLE media ADD COLUMN last_viewed DATETIME;"))


        # Enable WAL mode for SQLite
        if "sqlite" in settings.DATABASE_URL:
            await conn.execute(text("PRAGMA journal_mode=WAL;"))
            await conn.execute(text("PRAGMA synchronous=NORMAL;"))

async def get_db():
    async with SessionLocal() as session:
        yield session
