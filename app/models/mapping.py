from sqlalchemy import Column, Integer, Boolean, DateTime, ForeignKey, func, UniqueConstraint
from app.database import Base

class GestureActionMap(Base):
    __tablename__ = "gesture_action_maps"

    id = Column(Integer, primary_key=True, index=True)
    gesture_id = Column(Integer, ForeignKey("gestures.id"), unique=True, nullable=False, index=True)
    action_id = Column(Integer, ForeignKey("actions.id"), nullable=False, index=True)
    enabled = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class ActionDeviceMap(Base):
    __tablename__ = "action_device_maps"
    __table_args__ = (
        UniqueConstraint("action_id", name="uq_action_device_map_action_id"),
    )

    id = Column(Integer, primary_key=True, index=True)
    action_id = Column(Integer, ForeignKey("actions.id"), nullable=False, index=True)
    device_id = Column(Integer, ForeignKey("devices.id"), nullable=False, index=True)
    enabled = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())