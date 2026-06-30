from datetime import datetime, timezone

from fastapi import FastAPI, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from app.database import Base, engine, get_db, SessionLocal
from app.auth import create_access_token, get_current_user, hash_password, verify_password, verify_command_hmac, verify_replay_window,get_current_device
from app.models import (
    User,
    GestureDefinition,
    Action,
    Device,
    GestureActionMap,
    ActionDeviceMap,
    CommandEvent,
)
from app.schemas.user import UserCreate, UserLogin, UserOut, TokenOut
from app.schemas.gesture import GestureCreate, GestureOut
from app.schemas.action import ActionCreate, ActionOut
from app.schemas.device import DeviceCreate, DeviceOut, DeviceProvisionOut, PendingCommandOut, AckPayload
from app.schemas.mapping import (
    GestureActionMapCreate,
    GestureActionMapOut,
    ActionDeviceMapCreate,
    ActionDeviceMapOut,
)
from app.schemas.command import CommandIngest, CommandOut
from app.services.command_monitor import process_command_timeouts
from app.services.mqtt_service import publish_command

from contextlib import asynccontextmanager

import secrets
import asyncio

Base.metadata.create_all(bind=engine)

async def timeout_worker():
    while True:
        db = SessionLocal()
        try:
            process_command_timeouts(db)
        finally:
            db.close()
        await asyncio.sleep(1)

@asynccontextmanager
async def lifespan(app: FastAPI):
    task = asyncio.create_task(timeout_worker())
    yield
    task.cancel()
    
app = FastAPI(title="Gesture Routing Server",lifespan=lifespan)


def norm_label(text: str) -> str:
    return "".join(ch.lower() for ch in text if ch.isalnum())


def resolve_gesture_to_action_and_device(db: Session, pose: str, motion: str):
    gesture = (
        db.query(GestureDefinition)
        .filter(
            GestureDefinition.pose_key == norm_label(pose),
            GestureDefinition.motion_key == norm_label(motion),
            GestureDefinition.enabled == True,  # noqa: E712
        )
        .first()
    )
    if not gesture:
        raise HTTPException(status_code=404, detail="Gesture not found")

    gesture_map = (
        db.query(GestureActionMap)
        .filter(
            GestureActionMap.gesture_id == gesture.id,
            GestureActionMap.enabled == True,  # noqa: E712
        )
        .first()
    )
    if not gesture_map:
        raise HTTPException(status_code=409, detail="Gesture has no active action mapping")

    action = (
        db.query(Action)
        .filter(
            Action.id == gesture_map.action_id,
            Action.enabled == True,  # noqa: E712
        )
        .first()
    )
    if not action:
        raise HTTPException(status_code=404, detail="Action not found or disabled")

    device_map = (
        db.query(ActionDeviceMap)
        .filter(
            ActionDeviceMap.action_id == action.id,
            ActionDeviceMap.enabled == True,  # noqa: E712
        )
        .first()
    )
    if not device_map:
        raise HTTPException(status_code=409, detail="Action has no active device mapping")

    device = (
        db.query(Device)
        .filter(
            Device.id == device_map.device_id,
            Device.enabled == True,  # noqa: E712
        )
        .first()
    )
    if not device:
        raise HTTPException(status_code=404, detail="Target device not found or disabled")

    return gesture, action, device


@app.get("/")
def root():
    return {"status": "ok", "service": "gesture-routing-server"}


@app.get("/health")
def health():
    return {"status": "healthy"}


@app.post("/users/register", response_model=UserOut)
def register_user(payload: UserCreate, db: Session = Depends(get_db)):
    existing = db.query(User).filter(User.username == payload.username).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Username already exists",
        )

    user = User(
        username=payload.username,
        hashed_password=hash_password(payload.password),
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@app.post("/users/login", response_model=TokenOut)
def login_user(payload: UserLogin, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.username == payload.username).first()
    if not user or not verify_password(payload.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
        )

    token = create_access_token({"sub": str(user.id)})
    return {"access_token": token, "token_type": "bearer"}


@app.get("/users/me", response_model=UserOut)
def get_me(current_user: User = Depends(get_current_user)):
    return current_user


@app.post("/gestures", response_model=GestureOut)
def create_gesture(
    payload: GestureCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    pose_key = norm_label(payload.pose)
    motion_key = norm_label(payload.motion)

    existing = (
        db.query(GestureDefinition)
        .filter(
            GestureDefinition.pose_key == pose_key,
            GestureDefinition.motion_key == motion_key,
        )
        .first()
    )
    if existing:
        return existing

    gesture = GestureDefinition(
        gesture_name=payload.gesture_name,
        pose=payload.pose,
        motion=payload.motion,
        pose_key=pose_key,
        motion_key=motion_key,
        enabled=payload.enabled,
    )
    db.add(gesture)
    db.commit()
    db.refresh(gesture)
    return gesture


@app.get("/gestures", response_model=list[GestureOut])
def list_gestures(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return db.query(GestureDefinition).order_by(GestureDefinition.id.asc()).all()


@app.post("/actions", response_model=ActionOut)
def create_action(
    payload: ActionCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    existing = db.query(Action).filter(Action.action_code == payload.action_code).first()
    if existing:
        return existing

    action = Action(
        action_code=payload.action_code,
        description=payload.description,
        #payload_template=payload.payload_template,
        enabled=payload.enabled,
    )
    db.add(action)
    db.commit()
    db.refresh(action)
    return action


@app.get("/actions", response_model=list[ActionOut])
def list_actions(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return db.query(Action).order_by(Action.id.asc()).all()

@app.post("/devices", response_model=DeviceProvisionOut)
def create_device(
    payload: DeviceCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    existing = db.query(Device).filter(Device.device_id == payload.device_id).first()
    if existing:
        existing.name = payload.name
        existing.device_type = payload.device_type
        existing.enabled = payload.enabled
        existing.last_seen = datetime.utcnow()
        db.commit()
        db.refresh(existing)
        return existing

    api_key = secrets.token_hex(32)
    device = Device(
        device_id=payload.device_id,
        name=payload.name,
        device_type=payload.device_type,
        enabled=payload.enabled,
        api_key=api_key,
        last_seen=datetime.utcnow(),
    )
    db.add(device)
    db.commit()
    db.refresh(device)
    return device


@app.get("/devices", response_model=list[DeviceOut])
def list_devices(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return db.query(Device).order_by(Device.id.asc()).all()


@app.post("/gesture-action-maps", response_model=GestureActionMapOut)
def create_gesture_action_map(
    payload: GestureActionMapCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    existing = db.query(GestureActionMap).filter(GestureActionMap.gesture_id == payload.gesture_id).first()
    if existing:
        existing.action_id = payload.action_id
        existing.enabled = payload.enabled
        db.commit()
        db.refresh(existing)
        return existing

    mapping = GestureActionMap(
        gesture_id=payload.gesture_id,
        action_id=payload.action_id,
        enabled=payload.enabled,
    )
    db.add(mapping)
    db.commit()
    db.refresh(mapping)
    return mapping


@app.get("/gesture-action-maps", response_model=list[GestureActionMapOut])
def list_gesture_action_maps(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return db.query(GestureActionMap).order_by(GestureActionMap.id.asc()).all()


@app.post("/action-device-maps", response_model=ActionDeviceMapOut)
def create_action_device_map(
    payload: ActionDeviceMapCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    existing = db.query(ActionDeviceMap).filter(ActionDeviceMap.action_id == payload.action_id).first()
    if existing:
        existing.device_id = payload.device_id
        existing.enabled = payload.enabled
        db.commit()
        db.refresh(existing)
        return existing

    mapping = ActionDeviceMap(
        action_id=payload.action_id,
        device_id=payload.device_id,
        enabled=payload.enabled,
    )
    db.add(mapping)
    db.commit()
    db.refresh(mapping)
    return mapping


@app.get("/action-device-maps", response_model=list[ActionDeviceMapOut])
def list_action_device_maps(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return db.query(ActionDeviceMap).order_by(ActionDeviceMap.id.asc()).all()


@app.post("/commands/ingest")
def ingest_command(
    payload: CommandIngest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    verify_replay_window(payload.timestamp_ms)
    command_data = {
        "event_id": payload.event_id,
        "session_id": payload.session_id,
        "pose": payload.pose,
        "motion": payload.motion,
        "motion_source": payload.motion_source,
        "support": payload.support,
        "pose_score": payload.pose_score,
        "motion_score": payload.motion_score,
        "quality": payload.quality,
        "timestamp_ms": payload.timestamp_ms,
        "nonce": payload.nonce,
    }
    verify_command_hmac(command_data, payload.signature)

    if db.query(CommandEvent).filter(CommandEvent.event_id == payload.event_id).first():
        return {
            "success": True,
            "duplicate": True,
            "reason": "event_id already exists",
        }

    if db.query(CommandEvent).filter(CommandEvent.nonce == payload.nonce).first():
        return {
            "success": False,
            "reason": "replay detected: nonce already used",
        }

    gesture, action, device = resolve_gesture_to_action_and_device(
        db=db,
        pose=payload.pose,
        motion=payload.motion,
    )

    command = CommandEvent(
        event_id=payload.event_id,
        session_id=payload.session_id,
        user_id=current_user.id,
        gesture_id=gesture.id,
        action_id=action.id,
        target_device_id=device.id,
        pose=payload.pose,
        motion=payload.motion,
        motion_source=payload.motion_source,
        support=payload.support,
        pose_score=payload.pose_score,
        motion_score=payload.motion_score,
        quality=payload.quality,
        timestamp_ms=payload.timestamp_ms,
        nonce=payload.nonce,
        signature=payload.signature,
        status="pending",
    )

    db.add(command)
    try:
        db.commit()
        db.refresh(command)
    except IntegrityError:
        db.rollback()
        existing = db.query(CommandEvent).filter(CommandEvent.event_id == payload.event_id).first()
        return {
            "success": False,
            "reason": "duplicate replay or unique constraint violation",
        }

    publish_command(
        device_id=device.device_id,
        event_id=command.event_id,
        action_code=action.action_code
    )
    
    command.status = "sent"
    command.sent_at = datetime.now(timezone.utc)
    
    db.commit()
    db.refresh(command)
    
    return {
        "success": True,
        "duplicate": False,
        "db_id": command.id,
        "event_id": command.event_id,
        "gesture": gesture.pose + " + " + gesture.motion,
        "action": action.action_code,
        "target_device": device.device_id,
        "status": command.status,
    }

'''@app.get("/commands/pending", response_model=list[PendingCommandOut])
def get_pending_commands(
    db: Session = Depends(get_db),
    current_device: Device = Depends(get_current_device),
):
    commands = (
        db.query(CommandEvent)
        .filter(
            CommandEvent.target_device_id == current_device.id,
            CommandEvent.status == "pending"
        )
        .order_by(CommandEvent.id.asc())
        .all()
    )
    result = []

    for cmd in commands:
        action = (
            db.query(Action)
            .filter(Action.id == cmd.action_id)
            .first()
        )
        result.append(
            {
                "event_id": cmd.event_id,
                "action_id": cmd.action_id,
                "action_code": action.action_code,
            }
        )
        cmd.status = "sent"
        cmd.sent_at = datetime.now(timezone.utc)
    
    db.commit()
    return result '''

@app.get("/commands", response_model=list[CommandOut])
def get_all_commands(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return db.query(CommandEvent).order_by(CommandEvent.id.asc()).all()

@app.get("/commands/{event_id}", response_model=CommandOut)
def get_command_by_event_id(
    event_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    command = db.query(CommandEvent).filter(CommandEvent.event_id == event_id).first()
    if not command:
        raise HTTPException(status_code=404, detail="Command not found")
    return command

@app.post("/commands/ack")
def acknowledge_command(
    payload: AckPayload,
    db: Session = Depends(get_db),
    current_device: Device = Depends(get_current_device),
):
    command = (
        db.query(CommandEvent)
        .filter(
            CommandEvent.event_id == payload.event_id,
            CommandEvent.target_device_id == current_device.id
        )
        .first()
    )

    if not command:
        raise HTTPException(
            status_code=404,
            detail="Command not found"
        )
    command.status = "acked"
    command.acked_at = datetime.now(timezone.utc)
    
    db.commit()
    return {
        "success": True,
        "event_id": payload.event_id,
        "status": "acked"
    }
    
@app.post("/mqtt-test")
def mqtt_test():

    publish_command(
        "esp32_light_2",
        {
            "action": "LIGHT_ON",
            "event_id": "test123"
        }
    )
    return {"success": True}