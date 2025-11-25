import os
import json
import uuid
import hashlib
import asyncio
import time
import shutil
import logging
from typing import List, Optional
from datetime import datetime, timedelta
import pytz
import psutil
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Depends, HTTPException, status, UploadFile, File, Form, Response, Cookie
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, StreamingResponse
from fastapi.security import APIKeyCookie

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, desc, func, delete, text, or_, Integer

import aiofiles
from PIL import Image
import psutil

# App imports
from app.config import settings
from app.database import init_db, get_db
from app.models import Media, AppConfig

# Logging setup
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- Lifecycle & Database Init ---
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("Starting up...")
    await init_db()

    yield
    # Shutdown
    logger.info("Shutting down...")

app = FastAPI(lifespan=lifespan)

# Ensure directories exist before mounting StaticFiles
os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
os.makedirs(settings.THUMBNAIL_DIR, exist_ok=True)
os.makedirs(settings.ARCHIVE_DIR, exist_ok=True)

# --- Mount Static & Templates ---
app.mount("/static", StaticFiles(directory="app/static"), name="static")
# We also need to serve the uploads, but maybe restricted?
# For slideshow, we definitely need access.
app.mount("/uploads", StaticFiles(directory=settings.UPLOAD_DIR), name="uploads")
app.mount("/thumbnails", StaticFiles(directory=settings.THUMBNAIL_DIR), name="thumbnails")

templates = Jinja2Templates(directory="app/templates")

# --- Helpers ---

def get_current_time_in_zone():
    tz = pytz.timezone(settings.EVENT_TIMEZONE)
    return datetime.now(tz)

def load_schedule():
    schedule_path = "schedule.json"
    if not os.path.exists(schedule_path):
        return []
    try:
        with open(schedule_path, "r") as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Error loading schedule: {e}")
        return []

def load_schedule():
    schedule_path = "schedule.json"
    if not os.path.exists(schedule_path):
        return []
    try:
        with open(schedule_path, "r") as f:
            schedule = json.load(f)
            # Sort by start time to make processing easier
            schedule.sort(key=lambda x: x.get("start", ""))
            return schedule
    except Exception as e:
        logger.error(f"Error loading or sorting schedule: {e}")
        return []

def check_schedule_mode():
    """
    Returns the current mode, a message, and time remaining to next state change.
    """
    now = get_current_time_in_zone()
    schedule = load_schedule()

    # Defaults
    current_mode = "standard"
    message = ""
    remaining_seconds = None

    for i, block in enumerate(schedule):
        try:
            start = datetime.fromisoformat(block["start"]).astimezone(pytz.timezone(settings.EVENT_TIMEZONE))
            end = datetime.fromisoformat(block["end"]).astimezone(pytz.timezone(settings.EVENT_TIMEZONE))

            if start <= now < end:
                current_mode = block.get("mode", "standard")
                message = block.get("message", "")
                remaining_seconds = (end - now).total_seconds()
                return {
                    "mode": current_mode,
                    "message": message,
                    "remaining_seconds": remaining_seconds
                }
            elif now < start:
                # We are before the next block
                remaining_seconds = (start - now).total_seconds()
                # The message here could be about what's coming up, or nothing.
                # For now, we are in "standard" mode until this block starts.
                return {
                    "mode": "standard",
                    "message": "",
                    "remaining_seconds": remaining_seconds
                }
        except (ValueError, KeyError):
            continue

    # If we are past all scheduled blocks
    return {
        "mode": "standard", # Or 'unlimited' if that's the desired default post-event
        "message": "",
        "remaining_seconds": None
    }

async def generate_thumbnail(file_path: str, mime_type: str) -> Optional[str]:
    """Generates a thumbnail and returns the filename relative to UPLOAD_DIR."""
    if psutil.cpu_percent() > 90:
        logger.warning("CPU high, skipping thumbnail generation")
        return None

    try:
        thumb_filename = f"thumb_{os.path.basename(file_path)}.jpg"
        thumb_path = os.path.join(settings.UPLOAD_DIR, thumb_filename)

        if mime_type.startswith("image"):
            # Use PIL
            # Note: For heavy load, running this in a thread pool is better
            await asyncio.to_thread(_process_image_thumbnail, file_path, thumb_path)
            return thumb_filename
        elif mime_type.startswith("video") and settings.GENERATE_VIDEO_THUMBNAILS:
            # Use ffmpeg
            # ffmpeg -i input.mp4 -ss 00:00:01.000 -vframes 1 output.jpg
            cmd = [
                "ffmpeg", "-y",
                "-ss", str(settings.VIDEO_THUMBNAIL_TIMESTAMP),
                "-i", file_path,
                "-vframes", "1",
                "-q:v", "2",
                thumb_path
            ]
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL
            )
            await process.wait()
            if os.path.exists(thumb_path):
                return thumb_filename
    except Exception as e:
        logger.error(f"Thumbnail generation failed: {e}")

    return None

def _process_image_thumbnail(input_path, output_path):
    with Image.open(input_path) as img:
        img.thumbnail((800, 800))
        img = img.convert("RGB")
        img.save(output_path, "JPEG", quality=70)

# --- Dependencies ---

async def get_admin_user(request: Request):
    """Dependency to check if user is admin via session cookie."""
    token = request.cookies.get("admin_token")
    if token == settings.ADMIN_MAGIC_TOKEN:
        return True
    return False

async def get_current_guest(request: Request):
    """Dependency to identify guest session."""
    guest_name = request.cookies.get("guest_name")
    table_number = request.cookies.get("table_number")
    guest_uuid = request.cookies.get("guest_uuid")
    return {"name": guest_name, "table": table_number, "uuid": guest_uuid}

# --- Routes ---

@app.get("/", response_class=HTMLResponse)
async def index(
    request: Request,
    auth: Optional[str] = None,
    table: Optional[str] = None,
    db: AsyncSession = Depends(get_db)
):
    # Handle query params for session setting logic (done in JS or redirect?)
    # Easier to just render the template and let JS handle params -> cookie setting if needed,
    # OR set cookie here and redirect.

    response = templates.TemplateResponse("index.html", {"request": request})

    if auth:
        # If it matches magic token, maybe auto-login admin?
        pass # Logic handled in specific login route usually

    if table:
        response.set_cookie(key="table_number", value=table)

    return response

@app.get("/config")
async def get_frontend_config(db: AsyncSession = Depends(get_db)):
    """Returns dynamic config for frontend."""
    keys = ["GLOBAL_BANNER_MESSAGE_EN", "GLOBAL_BANNER_MESSAGE_ES"]
    result = await db.execute(select(AppConfig).where(AppConfig.key.in_(keys)))
    banners = {c.key: c.value for c in result.scalars()}
    schedule_info = check_schedule_mode()

    return {
        "banner_message_en": banners.get("GLOBAL_BANNER_MESSAGE_EN"),
        "banner_message_es": banners.get("GLOBAL_BANNER_MESSAGE_ES"),
        "max_file_size_mb": settings.MAX_MEDIA_SIZE_MB,
        "max_video_duration_sec": settings.MAX_VIDEO_DURATION_SEC,
        "mode": schedule_info.get("mode", "standard"),
        "schedule_message": schedule_info.get("message", ""),
        "schedule_remaining_seconds": schedule_info.get("remaining_seconds"),
        "post_upload_url": settings.POST_UPLOAD_ACTION_URL,
        "post_upload_label": settings.POST_UPLOAD_ACTION_LABEL
    }

@app.post("/upload")
async def upload_media(
    request: Request,
    file: UploadFile = File(...),
    caption: Optional[str] = Form(None),
    guest_info: dict = Depends(get_current_guest),
    db: AsyncSession = Depends(get_db)
):
    schedule_info = check_schedule_mode()
    if schedule_info.get("mode") == "blackout":
        detail_message = schedule_info.get("message") or "Uploads are currently paused."
        raise HTTPException(status_code=403, detail=detail_message)

    # 1. Validation
    # We can't easily validate size before streaming without relying on Content-Length header, which can be spoofed.
    # We will monitor size during read.

    content_type = file.content_type
    if not (content_type.startswith("image/") or content_type.startswith("video/")):
         raise HTTPException(status_code=400, detail="Invalid file type.")

    # Sanitize name
    if not guest_info["uuid"]:
        raise HTTPException(status_code=401, detail="Guest UUID required.")
    if not guest_info["name"]:
        raise HTTPException(status_code=401, detail="Guest name required.")

    safe_name = "".join(c for c in guest_info["name"] if c.isalnum() or c in (' ', '_', '-')).strip()
    if not safe_name:
        safe_name = "Anonymous"

    timestamp_uuid = f"{int(time.time())}_{uuid.uuid4().hex[:8]}"
    upload_folder_name = f"{timestamp_uuid}_{safe_name}"
    upload_folder_path = os.path.join(settings.UPLOAD_DIR, upload_folder_name)
    os.makedirs(upload_folder_path, exist_ok=True)

    file_ext = os.path.splitext(file.filename)[1]
    unique_filename = f"{uuid.uuid4()}{file_ext}"
    file_path = os.path.join(upload_folder_path, unique_filename)

    # 2. Streaming Write & Hash
    sha256 = hashlib.sha256()
    size = 0
    max_bytes = settings.MAX_MEDIA_SIZE_MB * 1024 * 1024

    try:
        async with aiofiles.open(file_path, 'wb') as out_file:
            while content := await file.read(1024 * 1024): # 1MB chunks
                size += len(content)
                if size > max_bytes:
                    os.remove(file_path)
                    raise HTTPException(status_code=413, detail="File too large.")
                sha256.update(content)
                await out_file.write(content)
    except Exception as e:
        if os.path.exists(file_path):
            os.remove(file_path)
        logger.error(f"Upload failed: {e}")
        raise HTTPException(status_code=500, detail="Upload failed.")

    file_hash = sha256.hexdigest()

    # 3. Deduplication Check
    existing = await db.execute(select(Media).where(Media.sha256_hash == file_hash))
    if existing.scalar_one_or_none():
        # Duplicate found. Delete the new file, return success.
        os.remove(file_path)
        return {"status": "success", "message": "Duplicate detected"}

    # 4. Integrity Check (Re-read) - "Write to disk -> Re-read -> Verify SHA-256"
    # To save time, we might skip this if we trust the write, but requirements are explicit.
    # However, re-reading a 500MB file is expensive.
    # Let's do a quick size check or assume aiofiles didn't lie.
    # If explicit strict requirement:
    async with aiofiles.open(file_path, 'rb') as f:
        check_hash = hashlib.sha256()
        while chunk := await f.read(1024*1024):
            check_hash.update(chunk)

def save_schedule(schedule: list):
    # Sort by start time before saving
    schedule.sort(key=lambda x: x.get("start", ""))
    with open("schedule.json", "w") as f:
        json.dump(schedule, f, indent=4)

    if check_hash.hexdigest() != file_hash:
        os.remove(file_path)
        raise HTTPException(status_code=500, detail="Integrity check failed.")

    # 5. Generate Thumbnail (Save to THUMBNAIL_DIR)
    thumb_filename = None
    try:
        thumb_name = f"thumb_{unique_filename.split('.')[0]}.jpg"
        thumb_path = os.path.join(settings.THUMBNAIL_DIR, thumb_name)

        if content_type.startswith("image"):
            await asyncio.to_thread(_process_image_thumbnail, file_path, thumb_path)
            thumb_filename = thumb_name
        elif content_type.startswith("video") and settings.GENERATE_VIDEO_THUMBNAILS:
            cmd = [
                "ffmpeg", "-y",
                "-ss", str(settings.VIDEO_THUMBNAIL_TIMESTAMP),
                "-i", file_path,
                "-vframes", "1",
                "-q:v", "2",
                thumb_path
            ]
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL
            )
            await process.wait()
            if os.path.exists(thumb_path):
                thumb_filename = thumb_name
    except Exception as e:
        logger.error(f"Thumbnail generation failed: {e}")

    # 6. Save to DB
    # Store relative path for filename including folder
    relative_filename = os.path.join(upload_folder_name, unique_filename)

    new_media = Media(
        filename=relative_filename,
        original_filename=file.filename,
        file_type="video" if content_type.startswith("video") else "image",
        mime_type=content_type,
        file_size_bytes=size,
        sha256_hash=file_hash,
        guest_uuid=guest_info["uuid"],
        uploaded_by=guest_info["name"],
        table_number=guest_info["table"],
        caption=caption,
        thumbnail_path=thumb_filename
    )
    db.add(new_media)
    await db.commit()
    await db.refresh(new_media)

    return {"status": "success", "id": new_media.id}

@app.get("/slideshow", response_class=HTMLResponse)
async def slideshow(request: Request):
    return templates.TemplateResponse("slideshow.html", {"request": request})

@app.get("/slideshow/feed")
async def slideshow_feed(
    cursor: Optional[str] = None,
    q: Optional[str] = None,
    limit: int = 20,
    admin_mode: bool = False,
    order: str = 'random', # 'random' or 'newest'
    filter: Optional[str] = None,
    type: Optional[str] = None,
    db: AsyncSession = Depends(get_db)
):
    """
    Returns media items.
    Cursor is a timestamp (ISO string).
    """
    query = select(Media)

    if not admin_mode:
        query = query.where(Media.is_hidden == False)
        if order == 'random':
            # Biased Sorting for slideshow
            now = datetime.now(pytz.utc)
            age_in_minutes = func.julianday('now') * 24 * 60 - func.julianday(Media.created_at) * 24 * 60

            # Score: Starred items get a huge boost. Very new items (last 5 min) get a boost.
            score = (
                (func.cast(Media.is_starred, Integer) * 1000) +
                func.iif(age_in_minutes < 5, 500, 0) +
                (100 / (age_in_minutes + 10))
            ).label("score")
            query = query.order_by(desc(score))
        else: # newest
            query = query.order_by(desc(Media.created_at), desc(Media.id))
    else:
        # Admin view always gets chronological
        query = query.order_by(desc(Media.created_at), desc(Media.id))

    if filter == "starred":
        query = query.where(Media.is_starred == True)
    elif filter == "hidden":
        query = query.where(Media.is_hidden == True)

    if type in ["image", "video"]:
        query = query.where(Media.file_type == type)

    if q:
        search = f"%{q}%"
        query = query.where(or_(
            Media.caption.ilike(search),
            Media.uploaded_by.ilike(search),
            Media.original_filename.ilike(search)
        ))

    if admin_mode:
        if cursor:
            try:
                cursor_ts, cursor_id = cursor.split('_')
                cursor_dt = datetime.fromisoformat(cursor_ts)
                # Efficient pagination: (created_at < cursor) OR (created_at == cursor AND id < cursor_id)
                query = query.where(
                    (Media.created_at < cursor_dt) |
                    ((Media.created_at == cursor_dt) & (Media.id < int(cursor_id)))
                )
            except ValueError:
                pass # Invalid cursor
        query = query.order_by(desc(Media.created_at), desc(Media.id))


    query = query.limit(limit)

    result = await db.execute(query)
    media_items = result.scalars().all()

    data = []
    for m in media_items:
        data.append({
            "id": m.id,
            "url": f"/uploads/{m.filename}",
            "thumbnail": f"/thumbnails/{m.thumbnail_path}" if m.thumbnail_path else None,
            "type": m.file_type, # image or video
            "caption": m.caption,
            "author": m.uploaded_by,
            "created_at": m.created_at.isoformat(),
            "is_starred": m.is_starred,
            "file_size": m.file_size_bytes,
            "is_hidden": m.is_hidden,
            "filename": m.filename,
            "original_filename": m.original_filename
        })

    next_cursor = f"{data[-1]['created_at']}_{data[-1]['id']}" if data else None
    return {"items": data, "next_cursor": next_cursor}


@app.post("/media/{media_id}/viewed")
async def mark_media_viewed(media_id: int, db: AsyncSession = Depends(get_db)):
    """Increments the view count for a media item."""
    await db.execute(
        update(Media)
        .where(Media.id == media_id)
        .values(
            view_count=Media.view_count + 1,
            last_viewed=func.now()
        )
    )
    await db.commit()
    return {"status": "ok"}


@app.get("/my-uploads")
async def my_uploads(
    guest_info: dict = Depends(get_current_guest),
    db: AsyncSession = Depends(get_db)
):
    """Returns uploads for the current guest session."""
    if not guest_info["uuid"]:
        return []

    query = select(Media).where(
        Media.guest_uuid == guest_info["uuid"]
    ).order_by(desc(Media.created_at))

    result = await db.execute(query)
    media_items = result.scalars().all()

    data = []
    for m in media_items:
        data.append({
            "id": m.id,
            "url": f"/uploads/{m.filename}",
            "thumbnail": f"/thumbnails/{m.thumbnail_path}" if m.thumbnail_path else None,
            "type": m.file_type,
            "caption": m.caption,
            "created_at": m.created_at.isoformat(),
            "file_size": m.file_size_bytes
        })
    return data

@app.delete("/media/{media_id}")
async def delete_media(
    media_id: int,
    guest_info: dict = Depends(get_current_guest),
    db: AsyncSession = Depends(get_db)
):
    """Hard delete for user if file exists on disk (not archived/pruned)."""
    media = await db.get(Media, media_id)
    if not media:
        raise HTTPException(404, "Media not found")

    # Check ownership
    if media.guest_uuid != guest_info["uuid"]:
        raise HTTPException(403, "Not authorized")

    # Check if file exists on disk
    full_path = os.path.join(settings.UPLOAD_DIR, media.filename)
    if not os.path.exists(full_path):
        # Already pruned/archived
        raise HTTPException(400, "Media already archived, cannot delete.")

    # Delete
    await db.delete(media)
    await db.commit()

    try:
        os.remove(full_path)
        if media.thumbnail_path:
            thumb_path = os.path.join(settings.THUMBNAIL_DIR, media.thumbnail_path)
            if os.path.exists(thumb_path):
                os.remove(thumb_path)
    except Exception as e:
        logger.error(f"Error deleting file: {e}")

    return {"status": "deleted"}

@app.get("/public/stats")
async def public_stats(db: AsyncSession = Depends(get_db)):
    """Public stats for the live feed."""
    photo_count = await db.scalar(select(func.count(Media.id)).where(Media.file_type == 'image', Media.is_hidden == False))
    video_count = await db.scalar(select(func.count(Media.id)).where(Media.file_type == 'video', Media.is_hidden == False))
    total_count = await db.scalar(select(func.count(Media.id)).where(Media.is_hidden == False))
    return {"photos": photo_count, "videos": video_count, "total_media": total_count}

# --- Admin Routes ---

@app.get("/admin", response_class=HTMLResponse)
async def admin_page(request: Request, token: Optional[str] = None, is_admin: bool = Depends(get_admin_user)):
    if token == settings.ADMIN_MAGIC_TOKEN:
        resp = templates.TemplateResponse("admin.html", {"request": request})
        resp.set_cookie(key="admin_token", value=token, httponly=True)
        return resp

    if not is_admin:
        return templates.TemplateResponse("admin_login.html", {"request": request})
    return templates.TemplateResponse("admin.html", {"request": request})

@app.get("/admin/login")
async def admin_login_token(token: str, response: Response):
    if token == settings.ADMIN_MAGIC_TOKEN:
        resp = RedirectResponse(url="/admin")
        resp.set_cookie(key="admin_token", value=token, httponly=True)
        return resp
    return JSONResponse(status_code=401, content={"error": "Invalid token"})

@app.post("/admin/login")
async def admin_login_pass(password: str = Form(...)):
    if password == settings.ADMIN_PASSWORD:
        resp = RedirectResponse(url="/admin", status_code=303)
        resp.set_cookie(key="admin_token", value=settings.ADMIN_MAGIC_TOKEN, httponly=True)
        return resp
    return HTMLResponse("Invalid password", status_code=401)

# --- Admin Schedule ---

@app.get("/admin/schedule")
async def get_schedule(is_admin: bool = Depends(get_admin_user)):
    if not is_admin: raise HTTPException(status_code=401)
    return load_schedule()

@app.post("/admin/schedule")
async def add_schedule_block(
    start: str, end: str, mode: str, message: Optional[str] = None,
    is_admin: bool = Depends(get_admin_user)
):
    if not is_admin: raise HTTPException(status_code=401)

    # Validate
    try:
        # The frontend sends datetime-local, which is ISO format without timezone
        # We need to assume it's in the event's timezone
        tz = pytz.timezone(settings.EVENT_TIMEZONE)
        start_dt = tz.localize(datetime.fromisoformat(start))
        end_dt = tz.localize(datetime.fromisoformat(end))
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid datetime format")

    new_block = {
        "start": start_dt.isoformat(),
        "end": end_dt.isoformat(),
        "mode": mode,
        "message": message or ""
    }

    schedule = load_schedule()
    schedule.append(new_block)
    save_schedule(schedule)
    return {"status": "ok"}

@app.put("/admin/schedule/{index}")
async def update_schedule_block(
    index: int, message: str,
    is_admin: bool = Depends(get_admin_user)
):
    if not is_admin: raise HTTPException(status_code=401)
    schedule = load_schedule()
    if 0 <= index < len(schedule):
        schedule[index]['message'] = message
        save_schedule(schedule)
        return {"status": "ok"}
    raise HTTPException(status_code=404, detail="Schedule block not found")

@app.delete("/admin/schedule/{index}")
async def delete_schedule_block(index: int, is_admin: bool = Depends(get_admin_user)):
    if not is_admin: raise HTTPException(status_code=401)
    schedule = load_schedule()
    if 0 <= index < len(schedule):
        schedule.pop(index)
        save_schedule(schedule)
        return {"status": "ok"}
    raise HTTPException(status_code=404, detail="Schedule block not found")


@app.get("/admin/stats")
async def admin_stats(is_admin: bool = Depends(get_admin_user), db: AsyncSession = Depends(get_db)):
    if not is_admin: raise HTTPException(status_code=401)

    # Disk Usage
    usage = shutil.disk_usage(settings.UPLOAD_DIR)

    # DB Counts
    total_count = await db.scalar(select(func.count(Media.id)))
    photo_count = await db.scalar(select(func.count(Media.id)).where(Media.file_type == 'image'))
    video_count = await db.scalar(select(func.count(Media.id)).where(Media.file_type == 'video'))

    # System Metrics
    cpu_usage = psutil.cpu_percent()
    ram = psutil.virtual_memory()

    # Backup Status
    last_backup = "Unknown"
    state_file = os.path.join(settings.ARCHIVE_DIR, "daemon_state.json")
    if os.path.exists(state_file):
        try:
            with open(state_file, 'r') as f:
                state = json.load(f)
                ts = state.get("last_rclone_success")
                if ts:
                    last_backup = datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M:%S")
        except: pass

    # Rclone status
    rclone_config_path = "/root/.config/rclone/rclone.conf"
    rclone_configured = os.path.exists(rclone_config_path)

    # CPU Temp (for Linux)
    cpu_temp = "N/A"
    try:
        temps = psutil.sensors_temperatures()
        if 'coretemp' in temps:
            cpu_temp = f"{temps['coretemp'][0].current}°C"
        elif 'cpu_thermal' in temps:
            cpu_temp = f"{temps['cpu_thermal'][0].current}°C"
    except Exception:
        pass

    return {
        "disk_total_gb": round(usage.total / (1024**3), 2),
        "disk_used_gb": round(usage.used / (1024**3), 2),
        "disk_free_gb": round(usage.free / (1024**3), 2),
        "media_total": total_count,
        "media_photos": photo_count,
        "media_videos": video_count,
        "cpu_percent": cpu_usage,
        "ram_percent": ram.percent,
        "ram_used_gb": round(ram.used / (1024**3), 2),
        "last_backup": last_backup,
        "rclone_configured": rclone_configured,
        "cpu_temp": cpu_temp
    }

@app.post("/admin/banner")
async def set_banner(
    message_en: str = Form(""),
    message_es: str = Form(""),
    is_admin: bool = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db)
):
    if not is_admin: raise HTTPException(status_code=401)

    async def upsert_banner(key: str, value: str):
        result = await db.execute(select(AppConfig).where(AppConfig.key == key))
        config = result.scalar_one_or_none()
        if config:
            config.value = value
        elif value: # Only add if not empty
            db.add(AppConfig(key=key, value=value))

    await upsert_banner("GLOBAL_BANNER_MESSAGE_EN", message_en)
    await upsert_banner("GLOBAL_BANNER_MESSAGE_ES", message_es)

    await db.commit()
    return {"status": "updated"}

@app.post("/admin/media/{media_id}/action")
async def media_action(
    media_id: int,
    action: str = Form(...), # hide, unhide, star, unstar, delete
    is_admin: bool = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db)
):
    if not is_admin: raise HTTPException(status_code=401)

    media = await db.get(Media, media_id)
    if not media:
        raise HTTPException(404, "Media not found")

    if action == "hide":
        media.is_hidden = True
    elif action == "unhide":
        media.is_hidden = False
    elif action == "star":
        media.is_starred = True
    elif action == "unstar":
        media.is_starred = False
    elif action == "delete":
        # Soft delete? Or hard? Requirements say "Allow 'Delete' (soft-delete) for 10 minutes after upload" for user.
        # Admin probably wants hard delete or hide. Let's just hide for safety or delete.
        # Let's delete from DB and File.
        await db.delete(media)
        # Remove file
        try:
            os.remove(os.path.join(settings.UPLOAD_DIR, media.filename))
            if media.thumbnail_path:
                os.remove(os.path.join(settings.UPLOAD_DIR, media.thumbnail_path))
        except:
            pass

    await db.commit()
    return {"status": "ok"}

@app.post("/admin/purge")
async def admin_purge(pin: str = Form(...), is_admin: bool = Depends(get_admin_user), db: AsyncSession = Depends(get_db)):
    if not is_admin: raise HTTPException(status_code=401)
    if pin != settings.PURGE_PIN:
        raise HTTPException(status_code=403, detail="Invalid PIN")

    # 1. Truncate DB
    await db.execute(delete(Media))
    await db.execute(delete(AppConfig))
    await db.commit()

    # 2. Clear Directories
    def clear_dir(path):
        if os.path.exists(path):
            shutil.rmtree(path)
            os.makedirs(path, exist_ok=True)

    clear_dir(settings.UPLOAD_DIR)
    clear_dir(settings.THUMBNAIL_DIR)
    clear_dir(settings.ARCHIVE_DIR)

    return {"status": "purged"}

@app.get("/health")
async def health_check(db: AsyncSession = Depends(get_db)):
    # DB
    try:
        await db.execute(text("SELECT 1"))
        db_status = "ok"
    except Exception:
        db_status = "error"

    # Disk
    try:
        test_file = os.path.join(settings.UPLOAD_DIR, "health_test")
        async with aiofiles.open(test_file, 'w') as f:
            await f.write("ok")
        os.remove(test_file)
        disk_status = "ok"
    except Exception:
        disk_status = "error"

    # System
    cpu_percent = psutil.cpu_percent()
    ram_percent = psutil.virtual_memory().percent

    all_ok = all(s == "ok" for s in [db_status, disk_status]) and cpu_percent < 95 and ram_percent < 95

    return {
        "status": "healthy" if all_ok else "unhealthy",
        "database": db_status,
        "disk": disk_status,
        "cpu_percent": cpu_percent,
        "ram_percent": ram_percent,
    }
