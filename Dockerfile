# Stage 1: Builder (if needed, but we stick to slim and install runtime deps)
FROM python:3.12-slim

# Install system dependencies
# ffmpeg for video processing, curl/unzip for rclone install
RUN apt-get update && apt-get install -y \
    ffmpeg \
    curl \
    unzip \
    && rm -rf /var/lib/apt/lists/*

# Install Rclone
RUN curl https://rclone.org/install.sh | bash

# Set workdir
WORKDIR /app

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy App
COPY . .

# Environment Defaults
ENV UPLOAD_DIR=/data/uploads
ENV ARCHIVE_DIR=/data/archives
ENV DATABASE_URL=sqlite+aiosqlite:////data/database.sqlite

# Create directories
RUN mkdir -p /data/uploads /data/archives

# Expose port
EXPOSE 8000

# Helper script to run app or daemon
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

ENTRYPOINT ["/entrypoint.sh"]
