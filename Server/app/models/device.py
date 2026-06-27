from sqlalchemy import Column, Integer, String, Boolean, DateTime, func
from app.database import Base


class Device(Base):
    __tablename__ = "devices"

    id = Column(Integer, primary_key=True, index=True)
    device_id = Column(String(64), unique=True, index=True, nullable=False)
    name = Column(String(100), nullable=True)
    device_type = Column(String(100), nullable=True)
    enabled = Column(Boolean, default=True, nullable=False)
    api_key = Column(String(128), unique=True, nullable=False)
    last_seen = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())