from pydantic import BaseModel
from typing import Any, Optional


class ActionCreate(BaseModel):
    action_code: str
    description: str | None = None
    #payload_template: dict[str, Any] | None = None
    enabled: bool = True


class ActionOut(BaseModel):
    id: int
    action_code: str
    description: str | None = None
    #payload_template: dict[str, Any] | None = None
    enabled: bool

    class Config:
        from_attributes = True