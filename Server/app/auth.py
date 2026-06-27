from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from fastapi import Depends, HTTPException, Header, status
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy.orm import Session

from app.database import settings, get_db
from app.models.user import User
from app.models.device import Device

import hashlib,hmac,json

pwd_context = CryptContext(schemes=["argon2"], deprecated="auto")

def hash_password(password: str) -> str:
    return pwd_context.hash(password)

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)

def create_access_token(data: dict[str, Any], expires_minutes: Optional[int] = None) -> str:
    payload = data.copy()
    expire_minutes = expires_minutes or settings.ACCESS_TOKEN_EXPIRE_MINUTES
    expire = datetime.now(timezone.utc) + timedelta(minutes=expire_minutes)
    payload.update({"exp": expire})
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)

def decode_access_token(token: str) -> dict[str, Any]:
    try:
        return jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        )

def get_current_user(
    authorization: str = Header(...),
    db: Session = Depends(get_db),
) -> User:
    if not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing Bearer token",
        )
    token = authorization.split(" ", 1)[1].strip()
    payload = decode_access_token(token)

    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload",
        )

    user = db.query(User).filter(User.id == int(user_id)).first()
    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive",
        )
    return user


def build_command_hmac_message(command_data: dict[str, Any]) -> str:
    canonical = {
        "event_id": command_data["event_id"],
        "session_id": command_data["session_id"],
        "pose": command_data["pose"],
        "motion": command_data["motion"],
        "motion_source": command_data.get("motion_source") or "",
        "support": command_data.get("support"),
        "pose_score": command_data.get("pose_score"),
        "motion_score": command_data.get("motion_score"),
        "quality": command_data.get("quality"),
        "timestamp_ms": int(command_data["timestamp_ms"]),
        "nonce": command_data["nonce"],
    }
    return json.dumps(canonical, sort_keys=True, separators=(",", ":"), ensure_ascii=False)

def sign_command_hmac(command_data: dict[str, Any]) -> str:
    message = build_command_hmac_message(command_data)
    return hmac.new(
        settings.HMAC_SECRET_KEY.encode("utf-8"),
        message.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()

def verify_command_hmac(command_data: dict[str, Any], signature: str) -> None:
    expected = sign_command_hmac(command_data)
    if not hmac.compare_digest(expected, signature):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid command signature",
        )

def verify_replay_window(timestamp_ms: int) -> None:
    now_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
    window_ms = settings.COMMAND_REPLAY_WINDOW_SECONDS * 1000
    if abs(now_ms - timestamp_ms) > window_ms:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Command timestamp outside replay window",
        )
        
def get_current_device(
    x_api_key: str = Header(...),
    db: Session = Depends(get_db),
) -> Device:

    device = (
        db.query(Device)
        .filter(
            Device.api_key == x_api_key,
            Device.enabled == True
        )
        .first()
    )

    if not device:
        raise HTTPException(
            status_code=401,
            detail="Invalid API Key"
        )
    return device        