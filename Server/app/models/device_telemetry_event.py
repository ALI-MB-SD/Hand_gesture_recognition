from sqlalchemy import Column, Integer, String, DateTime, ForeignKey
from sqlalchemy.sql import func
from app.database import Base


class DeviceTelemetryEvent(Base):
    __tablename__ = "device_telemetry_events"

    id = Column(Integer, primary_key=True, index=True)

    device_id = Column(Integer, ForeignKey("devices.id"), nullable=False, index=True)

    wifi_rssi = Column(Integer, nullable=False)
    wifi_quality = Column(String(20), nullable=False)
    uptime_seconds = Column(Integer, nullable=False)

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)