from sqlalchemy import Column, Integer, String, Boolean, DateTime, Float, Text
from sqlalchemy.sql import func
from app.database import Base
import datetime

class Media(Base):
    __tablename__ = "media"

    id = Column(Integer, primary_key=True, index=True)
    filename = Column(String, unique=True, index=True)
    original_filename = Column(String)
    file_type = Column(String) # 'image' or 'video'
    mime_type = Column(String)
    file_size_bytes = Column(Integer)
    sha256_hash = Column(String, index=True)

    # Guest info
    guest_uuid = Column(String, index=True, nullable=True)
    uploaded_by = Column(String, nullable=True) # Name if provided
    table_number = Column(String, nullable=True)
    caption = Column(Text, nullable=True)

    # Metadata
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    duration_sec = Column(Float, nullable=True) # For videos

    # Moderation / Display
    is_hidden = Column(Boolean, default=False)
    is_starred = Column(Boolean, default=False)
    view_count = Column(Integer, default=0)
    last_viewed = Column(DateTime(timezone=True), nullable=True)

    # Flags
    thumbnail_path = Column(String, nullable=True)

class AppConfig(Base):
    __tablename__ = "app_config"

    key = Column(String, primary_key=True, index=True)
    value = Column(String)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

# Keys for AppConfig:
# - GLOBAL_BANNER_MESSAGE
