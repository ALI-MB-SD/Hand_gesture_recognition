from sqlalchemy import Column, Integer,Float, String, Boolean, DateTime, func
from app.database import Base


class Device(Base):
    __tablename__ = "devices"

    id = Column(Integer, primary_key=True, index=True)
    
    device_id = Column(String(64), unique=True, index=True, nullable=False)
    name = Column(String(100), nullable=True)
    device_type = Column(String(100), nullable=True)
    enabled = Column(Boolean, default=True, nullable=False)
    
    api_key = Column(String(128), unique=True, nullable=False)
    
    status = Column(String, nullable=False, default="unknown")
    status_changed_at = Column(DateTime(timezone=True), nullable=True)
    online_since = Column(DateTime(timezone=True), nullable=True)
    offline_at = Column(DateTime(timezone=True), nullable=True)

    current_wifi_rssi = Column(Integer, nullable=True)
    current_wifi_quality = Column(String(20), nullable=True)
    current_uptime_seconds = Column(Integer, nullable=True)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())