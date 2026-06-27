from sqlalchemy import Column, Integer, String, Boolean, DateTime, func, UniqueConstraint
from app.database import Base

class GestureDefinition(Base):
    __tablename__ = "gestures"
    __table_args__ = (
        UniqueConstraint("pose_key","motion_key", name="uq_gestures_pose_motion_key"),
    )
    
    id = Column(Integer, primary_key=True, index=True)
    gesture_name = Column(String(100), nullable=True)
    
    pose = Column(String(64), nullable=False)
    motion = Column(String(64), nullable=False)
    
    pose_key = Column(String(64), nullable=False, index=True)
    motion_key = Column(String(64), nullable=False, index=True)
    
    enabled = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())