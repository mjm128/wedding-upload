# Wedding Photo/Video Upload Service

A self-hosted, high-performance wedding media upload service designed for reliability, speed, and elegance. Built with FastAPI, SQLite (WAL), and Vanilla JS.

## Features

*   **Zero-Code Configuration:** Fully configurable via Environment Variables and `schedule.json`.
*   **High-End UI:** "Expensive" dark/gold theme with glassmorphism and smooth transitions.
*   **Resumable Uploads:** Mobile-first design with wake lock, progress bars, and retry logic.
*   **Live Slideshow:** Real-time feed of uploads with auto-refresh and moderation.
*   **Robust Archival:** Automated backups to local zip and Cloud Storage (Rclone) with smart pruning.
*   **Privacy & Moderation:** Admin dashboard to hide/star media, set global banners, and monitor stats.

## Deployment Guide

### 1. Oracle Cloud Infrastructure (OCI) Setup

1.  **Create Instance:**
    *   Image: Oracle Linux 8 or Ubuntu Minimal.
    *   Shape: VM.Standard.A1.Flex (ARM64/Ampere).
    *   OCPU: 4, RAM: 24GB.
    *   Boot Volume: 50GB+ (Recommended).

2.  **Network Security Groups (Ingress Rules):**
    *   Open Ports: `80` (HTTP), `443` (HTTPS), `81` (Nginx Proxy Manager Admin), `22` (SSH).
    *   Source: `0.0.0.0/0` (or restricted to your IP for port 81/22).

### 2. Docker Installation (ARM64)

```bash
# Update and install dependencies
sudo apt-get update && sudo apt-get install -y docker.io docker-compose

# Start Docker
sudo systemctl enable --now docker

# Verify ARM64 architecture
docker version
```

### 3. Application Setup

1.  **Clone the Repository:**
    ```bash
    git clone <repo_url> wedding-app
    cd wedding-app
    ```

2.  **Configure Environment:**
    Create a `.env` file (or rely on defaults in `docker-compose.yml`):
    ```ini
    EVENT_TIMEZONE=America/Los_Angeles
    ADMIN_PASSWORD=MySecurePassword
    ADMIN_MAGIC_TOKEN=magic123
    RCLONE_REMOTE_NAME=gdrive
    DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/...
    ```

3.  **Configure Rclone:**
    You need an `rclone.conf` file for the backup daemon.
    Run this locally to generate the config, then copy it to the server:
    ```bash
    rclone config
    # Follow steps to auth with Google Drive / S3
    ```
    Place `rclone.conf` in the project root.

4.  **Configure Schedule:**
    Edit `schedule.json` to define event blocks (e.g., blackout times during vows).

### 4. Build and Run

```bash
# Build the image
docker-compose build

# Start services (detached)
docker-compose up -d
```

### 5. Nginx Proxy Manager (NPM) Setup

To handle SSL and easy proxying, use NPM.

1.  **Create NPM Compose File (`npm-compose.yml`):**
    ```yaml
    version: '3'
    services:
      app:
        image: 'jc21/nginx-proxy-manager:latest'
        restart: unless-stopped
        ports:
          - '80:80'
          - '81:81'
          - '443:443'
        volumes:
          - ./data:/data
          - ./letsencrypt:/etc/letsencrypt
    ```

2.  **Start NPM:**
    ```bash
    docker-compose -f npm-compose.yml up -d
    ```

3.  **Configure Proxy Host:**
    *   Go to `http://<ORACLE_IP>:81`.
    *   Default Login: `admin@example.com` / `changeme`.
    *   **Add Proxy Host:**
        *   Domain Names: `wedding.yourdomain.com`
        *   Scheme: `http`
        *   Forward Host: `<ORACLE_PRIVATE_IP>` or `wedding_app` (if on same network).
        *   Forward Port: `8000`.
        *   **SSL Tab:** Request a new Let's Encrypt Certificate. Force SSL.

### 6. Cloudflare DNS Setup

1.  **A Record:**
    *   Name: `wedding`
    *   IPv4 Address: `<ORACLE_PUBLIC_IP>`
    *   Proxy Status: **DNS Only** (Grey Cloud) recommended initially to ensure Let's Encrypt works via HTTP-01 challenge. Once SSL is issued in NPM, you can switch to **Proxied** (Orange Cloud) for DDoS protection (ensure SSL setting in Cloudflare is "Full").

## Architecture

*   **App Container (`app`):** Runs FastAPI via Uvicorn. Handles uploads, serves UI, and streams media.
*   **Daemon Container (`daemon`):** Runs `archive_daemon.py`.
    *   Checks for new files every 10 minutes.
    *   Creates ZIP archives.
    *   Uploads to Cloud Storage via Rclone.
    *   Prunes local archives if disk usage > 40GB.
*   **Storage:**
    *   `/data/uploads`: Raw media files.
    *   `/data/archives`: ZIP backups and DB snapshots.
    *   `/data/database.sqlite`: SQLite WAL database.

## Testing

Run the pruning stress test:
```bash
python3 stress_test.py
```
(Requires mocking dependencies or running inside the container).

## Admin Access

*   URL: `/admin`
*   Login: Use the password configured in `.env` or the magic link `/admin/login?token=MAGIC_TOKEN`.
