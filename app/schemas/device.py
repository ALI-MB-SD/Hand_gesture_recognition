from pydantic import BaseModel

class DeviceCreate(BaseModel):
    device_id: str
    name: str | None = None
    device_type: str | None = None
    enabled: bool = True

class DeviceOut(BaseModel):
    id: int
    device_id: str
    name: str | None = None
    device_type: str | None = None
    enabled: bool
    
    class Config:
        from_attributes = True

class DeviceProvisionOut(BaseModel):
    id: int
    device_id: str
    api_key: str

    class Config:
        from_attributes = True
        
class PendingCommandOut(BaseModel):
    event_id: str

    action_id: int

    action_code: str

    class Config:
        from_attributes = True     

class AckPayload(BaseModel):
    event_id: str           