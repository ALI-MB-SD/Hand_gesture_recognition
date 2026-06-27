from sqlalchemy import Column, Integer, String, Boolean, DateTime, JSON, func
from app.database import Base


class Action(Base):
    __tablename__ = "actions"

    id = Column(Integer, primary_key=True, index=True)
    action_code = Column(String(64), unique=True, index=True, nullable=False)
    description = Column(String(255), nullable=True)
    #payload_template = Column(JSON, nullable=True)
    enabled = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())