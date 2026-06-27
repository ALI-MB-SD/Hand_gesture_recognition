from pydantic import BaseModel

class GestureCreate(BaseModel):
    gesture_name: str | None = None
    pose: str
    motion: str 
    enabled : bool = True
    
class GestureOut(BaseModel):
    id: int
    gesture_name: str | None = None
    pose: str
    motion: str
    pose_key: str
    motion_key: str
    enabled: bool
    
    class Config:
        from_attributes = True