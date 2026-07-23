from datetime import datetime
from pydantic import BaseModel, Field

class BrokerStatusOut(BaseModel):
    connected: bool
    host: str
    port: int
    tls_enabled: bool = True
    client_connected: bool = False

    last_connected_at: datetime | None = None
    last_disconnected_at: datetime | None = None

    subscriptions: list[str] = Field(default_factory=list)

    class Config:
        from_attributes = True


class BrokerStatusEventOut(BaseModel):
    id: int
    connected: bool
    source: str
    reason: str | None = None
    host: str
    port: int
    created_at: datetime

    class Config:
        from_attributes = True