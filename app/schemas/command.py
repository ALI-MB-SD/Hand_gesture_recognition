from pydantic import BaseModel, field_validator
from typing import Any, Optional
from datetime import datetime

class CommandIngest(BaseModel):
    event_id: str
    session_id: str

    pose: str
    motion: str
    motion_source: str | None = None

    support: float | None = None
    pose_score: float | None = None
    motion_score: float | None = None
    quality: float | None = None

    timestamp_ms: int
    nonce: str
    signature: str

    @field_validator("nonce")
    @classmethod
    def nonce_not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("nonce cannot be empty")
        return v

    @field_validator("signature")
    @classmethod
    def signature_not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("signature cannot be empty")
        return v

class CommandOut(BaseModel):
    id: int
    event_id: str
    session_id: str
    user_id: int
    gesture_id: int
    action_id: int
    target_device_id: int
    
    pose: str
    motion: str
    motion_source: str | None = None
    
    support: float | None = None
    pose_score: float| None = None
    motion_score: float| None = None
    quality: float| None = None

    timestamp_ms: int
    nonce: str
    signature: str
    
    status: str

    sent_at: datetime | None
    acked_at: datetime | None
    
    class Config:
        from_attributes = True