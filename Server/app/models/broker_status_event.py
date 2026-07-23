from sqlalchemy import Column, Integer, String, Boolean, DateTime
from sqlalchemy.sql import func

from app.database import Base

class BrokerStatusEvent(Base):
    __tablename__ = "broker_status_events"

    id = Column(Integer, primary_key=True, index=True)

    connected = Column(Boolean, nullable=False, index=True)
    source = Column(String(50), nullable=False, default="mqtt_callback")
    reason = Column(String(255), nullable=True)

    host = Column(String(255), nullable=False)
    port = Column(Integer, nullable=False)

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)