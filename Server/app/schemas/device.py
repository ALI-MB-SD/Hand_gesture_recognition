from pydantic import BaseModel
from datetime import datetime

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
    
    api_key: str

    status: str | None = None
    status_changed_at: datetime | None = None
    online_since: datetime | None = None
    offline_at: datetime | None = None
    
    current_wifi_rssi: int | None = None
    current_wifi_quality: str | None = None
    current_uptime_seconds: int | None = None
    
    class Config:
        from_attributes = True

class DeviceStatusEventOut(BaseModel):
    id: int
    device_id: int
    status: str
    source: str
    created_at: datetime

    class Config:
        from_attributes = True

class DeviceTelemetryEventOut(BaseModel):
    id: int
    device_id: int
    
    wifi_rssi: int
    wifi_quality: str
    
    uptime_seconds: int
    created_at: datetime

    class Config:
        from_attributes = True
        
class DeviceProvisionOut(BaseModel):
    id: int
    device_id: str
    api_key: str

    class Config:
        from_attributes = True
    
class AckPayload(BaseModel):
    event_id: str           