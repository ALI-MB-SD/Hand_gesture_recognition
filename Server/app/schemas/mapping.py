from pydantic import BaseModel

class GestureActionMapCreate(BaseModel):
    gesture_id: int
    action_id: int
    enabled: bool = True

class GestureActionMapOut(BaseModel):
    id: int
    gesture_id: int
    action_id: int
    enabled: bool

    class Config:
        from_attributes = True

class ActionDeviceMapCreate(BaseModel):
    action_id: int
    device_id: int
    enabled: bool = True

class ActionDeviceMapOut(BaseModel):
    id: int
    action_id: int
    device_id: int
    enabled: bool
    
    class Config:
        from_attributes = True