from sqlalchemy import Column, Integer, String, DateTime, ForeignKey
from sqlalchemy.sql import func
from app.database import Base

class DeviceStatusEvent(Base):
    __tablename__ = "device_status_events"

    id = Column(Integer, primary_key=True, index=True)

    device_id = Column(Integer, ForeignKey("devices.id"), nullable=False, index=True)

    status = Column(String, nullable=False)   # online / offline
    source = Column(String, nullable=False)   # boot / lwt / manual / etc.

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)