**Role:** Senior Python Backend Engineer & DevOps Specialist (Focus on Data Integrity, Reliability, and UX).

**Task:** Create a complete, production-ready source code structure for a self-hosted Wedding Photo/Video Upload Service.

**Deployment Context:**
* **Infrastructure:** Oracle Cloud Free Tier (ARM64/Ampere).
* **OS:** Oracle Linux / Ubuntu.
* **Containerization:** Docker Compose (Target platform: `linux/arm64`).
* **Resource Policy:** **UNRESTRICTED.** Do not apply `deploy: resources: limits` in Docker. The app must have access to the full 24GB RAM for video processing and caching.
* **Storage:** Local Boot Volume (Docker Volume mapped to host).
* **Proxy:** The app sits behind a reverse proxy (Nginx).
* **DNS Strategy:** Cloudflare Subdomain (A Record) pointing directly to the Oracle VM Public IP. SSL is handled by Nginx Proxy Manager on port 443.

**Tech Stack:**
* **Backend:** Python 3.14 (Use `python:3.14-slim` image) with **FastAPI**.
* **Database:** **SQLite** (via SQLAlchemy). **CRITICAL:** Must use `PRAGMA journal_mode=WAL;` and `PRAGMA synchronous=NORMAL;` to handle concurrent writes without locking.
* **Frontend:** Jinja2 Templates + Vanilla JS (No build step).
* **Media:** `ffmpeg` (installed in Docker) and `pillow-heif`.
* **Backup:** `rclone` (sidecar container).

**1. The "Zero-Code" Configuration Strategy:**

The app must be configured 100% via Environment Variables (`.env`) and a `schedule.json`:

* **Env Variables (`.env`):**
    * `EVENT_TIMEZONE` (e.g., "America/Los_Angeles").
    * `MAX_MEDIA_SIZE_MB` (Default: 500).
    * `MAX_VIDEO_DURATION_SEC` (Default: 60).
    * `MAX_LOCAL_STORAGE_GB` (Default: 40) -> *Trigger for local pruning*.
    * `GENERATE_VIDEO_THUMBNAILS` (Bool, Default: True).
    * `VIDEO_THUMBNAIL_TIMESTAMP` (Float, Default: 2.0).
    * `THROTTLE_DEFAULT_LIMIT` (Int, Default: 5).
    * `THROTTLE_WINDOW_MIN` (Int, Default: 10).
    * `SLIDESHOW_REFRESH_INTERVAL_SEC` (Int, Default: 300).
    * `ADMIN_PASSWORD`.
    * `ADMIN_MAGIC_TOKEN` (String for passwordless login).
    * `DISCORD_WEBHOOK_URL`.
    * `RCLONE_REMOTE_NAME` (Default: "gdrive").
    * `POST_UPLOAD_ACTION_URL` (Optional, e.g., Registry URL).
    * `POST_UPLOAD_ACTION_LABEL` (Optional, e.g., "Visit Registry").
* **Event Schedule (`schedule.json`):**
    * JSON list defining time blocks to auto-switch "Party Mode" (standard/blackout/unlimited).

**2. Core Features & Business Logic:**

* **Authentication & User Tracking:**
    * **Flexible Entry:** Support `/?table=5` (stores table # in session) and `/?auth=xyz`.
    * **Identity:** Check session cookie. If missing, show "Welcome! Name?" form.
    * **Magic Admin Entry:** `/admin/login?token=ADMIN_MAGIC_TOKEN` -> Sets admin cookie instantly.

* **Global Announcement System:**
    * **Backend:** Store a global "Banner Message" string in the database (e.g., "Cake Cutting in 5 Minutes!").
    * **Frontend:** Both the *Upload Page* and the *Slideshow* must poll (or check on load) for this message.
    * **Display:** If set, show a prominent sticky banner at the top of the screen.
    * **Admin:** This is configurable in the admin view

* **Timezone Aware Throttling:**
    * Load `schedule.json`. Check Server Time vs. Schedule in `EVENT_TIMEZONE`.
    * Enforce modes (`blackout` rejects uploads).

* **Frontend Experience (Mobile First, PWA, Resumable):**
    * **Theme Engine:**
        * **Default:** "Battery Saver" Dark Mode (Background: `#000000`, Text: `#E0E0E0`, Accents: Deep Purple/Gold).
        * **Toggle:** "Elegant Light Mode" (Background: Cream/Off-White, Text: Charcoal, Accents: Gold/Sage Green).
        * Use CSS variables for hot-swapping.
    * **PWA Manifest:** Include `manifest.json` + Service Worker for "Install App" and UI caching.
    * **Orientation Fix (Crucial):** Use `blueimp-load-image` to rotate images/canvas *before* upload based on EXIF.
    * **Pre-Upload Validation:** JS checks file size & video duration (hidden `<video>` tag) *before* POST.
    * **Retry Queue:** `localStorage` saves "Failed Uploads". Show "Retry" button on network recovery.
    * **Guestbook:** Add an optional "Note/Caption" text field.
    * **My Uploads View:** A page/modal showing the user's history. Allow "Delete" (soft-delete) for 10 minutes after upload.
    * **UX:** `navigator.wakeLock`, Visual Progress Bar, Confetti.
    * **Post-Upload Action:** Link to `POST_UPLOAD_ACTION_URL` after success.

* **Upload Handling (Zero Data Loss & CPU Aware):**
    * **CPU Watchdog:** If `psutil.cpu_percent() > 90%`, skip thumbnail gen (queue for later).
    * **Streaming:** `aiofiles` for async streaming.
    * **Deduplication:** Check DB for SHA-256 match. If exists, discard but return 200 OK.
    * **Integrity Verify:** Write to disk -> Re-read -> Verify SHA-256 matches stream hash -> Return 200 OK.
    * **Thumbnails:** Generate low-res JPG previews.

* **Slideshow Feed:**
    * **Endpoint:** `/slideshow/feed?cursor=TIMESTAMP&limit=20`.
    * **Moderation:** Filter `hidden=True`. Prioritize `starred=True`.
    * **Caching:** `functools.lru_cache` (TTL 30s).
    * **UI:** Infinite scroll. Auto-refresh logic (configurable).
    * **Display Mode Toggle:** Button for "TV Mode" (Full Bleed) vs "Projector Mode" (5% padding).

* **Admin & Monitoring:**
    * **Health Check Endpoint:** `/health` returning JSON status (DB/Disk/Permissions).
    * **Stats:** Disk Usage (Live), DB Counts, Recent Uploads.
    * **Announcement Controls:** Input field to Set/Clear the "Global Banner Message".
    * **Moderation:** "Hide" and "Star" buttons.
    * **Tools:** QR Code Generator, Manual Overrides, "Download All" (.tar stream).

**3. The Archival & Backup Strategy (Complex):**
* **Container A (App):** Handles uploads to `/data/uploads`.
* **Container B (Daemon):** `archive_daemon.py` runs every 10 mins.
    * **Step 1: Backup DB:** Copy `database.sqlite` to `/data/archives/db_backup_{ts}.sqlite`.
    * **Step 2: Archive Media:** Zip folders older than 30 mins -> `/data/archives/batch_{ts}.zip`.
    * **Step 3: Verify:** Run `zipfile.testzip()`. Fail = Alert Discord & Abort.
    * **Step 4: Rclone Copy:** `rclone copy /data/archives remote:wedding_backup`.
    * **Step 5: Smart Pruning:**
        * Check local disk usage.
        * **IF AND ONLY IF** usage > `MAX_LOCAL_STORAGE_GB`:
            * Identify local ZIPs verified as "on remote" (`rclone lsl`).
            * Delete *oldest* local ZIPs until usage < limit.
            * *Never* delete the active `/data/uploads` folder.

**Deliverables (File Checklist):**

You MUST provide the code for **ALL** of the following files. Do not skip any.

1.  `README.md`: A comprehensive deployment guide including:
    * **Oracle Cloud Setup:** Ingress rules for 80/443/81.
    * **Docker Setup:** Installation steps for ARM64.
    * **Nginx Proxy Manager (NPM):** Detailed `docker-compose` for NPM and setup steps.
    * **Cloudflare & SSL:** Specific instructions on setting a Cloudflare A-Record (DNS Only or Proxied) to the Oracle IP and configuring NPM to issue Let's Encrypt certificates for that subdomain on Port 443.
2.  `docker-compose.yml`: (App + Daemon + External Network for Proxy. **NO** CPU/RAM limits).
3.  `Dockerfile`: (Base `python:3.14-slim`, install `ffmpeg`, `rclone`, `zip`).
4.  `app/main.py`: (FastAPI logic, Routes, Middleware).
5.  `app/database.py`: (Async engine with WAL mode).
6.  `app/models.py`: (SQLAlchemy models).
7.  `app/config.py`: (Pydantic settings).
8.  `app/static/style.css`: (The modern, high-end CSS with Glassmorphism and Gold accents).
9.  `app/static/manifest.json` & `app/static/sw.js`: (PWA settings).
10. `app/templates/index.html`: (The upload UI with Theme Toggle).
11. `app/templates/slideshow.html`: (The view-only feed).
12. `app/templates/admin.html`: (Dashboard).
13. `daemon/archive_daemon.py`: (The backup script).
14. `stress_test.py`: (Script to verify pruning logic).
15. `schedule.json`: (Example data).

**UI Design Instruction:**
The Frontend must look "Expensive." Use a dark mode default with gold accents (#D4AF37). Use `backdrop-filter: blur()` for glass cards. Use the 'Playfair Display' font for headers. Ensure it feels like a modern native app with smooth transitions.
