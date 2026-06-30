from datetime import datetime, timezone, timedelta
from sqlalchemy.orm import Session
from app.models.command import CommandEvent

PENDING_TIMEOUT_SECONDS = 50
SENT_TIMEOUT_SECONDS = 50

def process_command_timeouts(db: Session):

    now = datetime.now(timezone.utc)
    
    pending_cutoff = (now - timedelta(seconds=PENDING_TIMEOUT_SECONDS))
    sent_cutoff = ( now - timedelta(seconds=SENT_TIMEOUT_SECONDS))

    pending_commands = (
        db.query(CommandEvent)
        .filter(
            CommandEvent.status == "pending",
            CommandEvent.created_at < pending_cutoff
        )
        .all()
    )

    for cmd in pending_commands:
        cmd.status = "failed"

    sent_commands = (
        db.query(CommandEvent)
        .filter(
            CommandEvent.status == "sent",
            CommandEvent.sent_at.is_not(None),
            CommandEvent.sent_at < sent_cutoff
        )
        .all()
    )

    for cmd in sent_commands:
        cmd.status = "failed"

    db.commit()