from sqlalchemy import Column, Integer,BigInteger, String, Float, DateTime,ForeignKey, JSON, func
from app.database import Base


class CommandEvent(Base):
    __tablename__ = "command_events"

    id = Column(Integer, primary_key=True, index=True)
    
    event_id = Column(String(64), unique=True, index=True, nullable=False)
    session_id = Column(String(64), index=True, nullable=False)
    
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    gesture_id = Column(Integer, ForeignKey("gestures.id"), nullable=False, index=True)
    action_id = Column(Integer, ForeignKey("actions.id"), nullable=False, index=True)
    target_device_id = Column(Integer, ForeignKey("devices.id"), nullable=False, index=True)
    
    pose = Column(String(64), nullable=True)
    motion = Column(String(64), nullable=True)
    motion_source = Column(String(32), nullable=True)
    
    support = Column(Float, nullable=True)
    pose_score = Column(Float, nullable=True)
    motion_score = Column(Float, nullable=True)
    quality = Column(Float, nullable=True)
    
    timestamp_ms = Column(BigInteger, nullable=False, index=True)
    nonce = Column(String(128), unique=True, index=True, nullable=False)
    signature = Column(String(128), nullable=False)
    
    status = Column(String(32), default="pending", nullable=False)
    sent_at = Column(DateTime(timezone=True), nullable=True)
    acked_at = Column(DateTime(timezone=True),nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
