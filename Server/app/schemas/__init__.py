from app.schemas.user import UserCreate, UserLogin, UserOut, TokenOut
from app.schemas.gesture import GestureCreate, GestureOut
from app.schemas.action import ActionCreate, ActionOut
from app.schemas.device import DeviceCreate, DeviceOut
from app.schemas.mapping import (
    GestureActionMapCreate,
    GestureActionMapOut,
    ActionDeviceMapCreate,
    ActionDeviceMapOut,
)
from app.schemas.command import CommandIngest, CommandOut