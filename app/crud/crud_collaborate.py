from datetime import datetime
import secrets
from typing import Optional, List, Dict, Any, Union
from sqlalchemy.orm import Session
from .. import models


# Collaboration Session CRUD
def create_collaboration_session(
    db: Session,
    external_ticket_id: int,
    source_system: str,
    metadata: Optional[Dict[str, Any]] = None,
) -> models.CollaborationSession:
    """Create a new collaboration session"""
    session = models.CollaborationSession(
        external_ticket_id=external_ticket_id,
        source_system=source_system,
        status="open",
        metadata=metadata,
        access_token=secrets.token_urlsafe(32),
    )
    db.add(session)
    db.commit()
    db.refresh(session)
    return session


def get_collaboration_session(
    db: Session, session_id: int
) -> Optional[models.CollaborationSession]:
    """Get a collaboration session by ID"""
    return (
        db.query(models.CollaborationSession)
        .filter(models.CollaborationSession.id == session_id)
        .first()
    )


def update_session_status(
    db: Session, session_id: int, status: str
) -> Optional[models.CollaborationSession]:
    """Update a collaboration session status"""
    session = get_collaboration_session(db, session_id)
    if not session:
        return None

    session.status = status
    session.updated_at = datetime.utcnow()

    if status == "resolved":
        session.resolved_at = datetime.utcnow()

    db.commit()
    db.refresh(session)
    return session


def user_has_session_access(db: Session, user_id: int, session_id: int) -> bool:
    """Check if a user has access to a session"""
    participant = (
        db.query(models.CollaborationParticipant)
        .filter(
            models.CollaborationParticipant.session_id == session_id,
            models.CollaborationParticipant.user_id == user_id,
        )
        .first()
    )

    return participant is not None


# Collaboration Participant CRUD
def create_collaboration_participant(
    db: Session,
    session_id: int,
    email: str,
    user_name: str,
    user_type: str,
    user_id: Optional[int] = None,
    external_user_id: Optional[str] = None,
    notification_settings: Optional[Dict[str, Any]] = None,
) -> models.CollaborationParticipant:
    """Create a new collaboration participant"""
    participant = models.CollaborationParticipant(
        session_id=session_id,
        user_id=user_id,
        email=email,
        user_name=user_name,
        user_type=user_type,
        external_user_id=external_user_id,
        notification_settings=notification_settings,
        last_viewed_at=datetime.utcnow(),
    )
    db.add(participant)
    db.commit()
    db.refresh(participant)
    return participant


def get_collaboration_participant(
    db: Session, participant_id: int
) -> Optional[models.CollaborationParticipant]:
    """Get a collaboration participant by ID"""
    return (
        db.query(models.CollaborationParticipant)
        .filter(models.CollaborationParticipant.id == participant_id)
        .first()
    )


def get_participant_by_email(
    db: Session, session_id: int, email: str
) -> Optional[models.CollaborationParticipant]:
    """Get a participant by email for a specific session"""
    return (
        db.query(models.CollaborationParticipant)
        .filter(
            models.CollaborationParticipant.session_id == session_id,
            models.CollaborationParticipant.email == email,
        )
        .first()
    )


# Collaboration Message CRUD
def create_message(
    db: Session,
    session_id: int,
    participant_id: int,
    content: str,
    message_type: str = "text",
    metadata: Optional[Dict[str, Any]] = None,
) -> models.CollaborationMessage:
    """Create a new message"""
    message = models.CollaborationMessage(
        session_id=session_id,
        participant_id=participant_id,
        content=content,
        message_type=message_type,
        metadata=metadata,
    )
    db.add(message)
    db.commit()
    db.refresh(message)
    return message


def create_system_message(
    db: Session,
    session_id: int,
    content: str,
    metadata: Optional[Dict[str, Any]] = None,
) -> models.CollaborationMessage:
    """Create a system message (no participant)"""
    message = models.CollaborationMessage(
        session_id=session_id,
        participant_id=None,
        content=content,
        message_type="system",
        metadata=metadata,
        is_system=True,
    )
    db.add(message)
    db.commit()
    db.refresh(message)
    return message


def get_session_messages(
    db: Session, session_id: int, after_id: int = 0, limit: int = 100
) -> List[models.CollaborationMessage]:
    """Get messages for a session, optionally after a specific ID"""
    return (
        db.query(models.CollaborationMessage)
        .filter(
            models.CollaborationMessage.session_id == session_id,
            models.CollaborationMessage.id > after_id,
        )
        .order_by(models.CollaborationMessage.created_at)
        .limit(limit)
        .all()
    )


# Attachment CRUD
def create_attachment(
    db: Session,
    message_id: Optional[int],
    file_name: str,
    file_path: str,
    file_type: str,
    file_size: int,
) -> models.CollaborationAttachment:
    """Create a new file attachment"""
    attachment = models.CollaborationAttachment(
        message_id=message_id,
        file_name=file_name,
        file_path=file_path,
        file_type=file_type,
        file_size=file_size,
    )
    db.add(attachment)
    db.commit()
    db.refresh(attachment)
    return attachment


def get_message_attachments(
    db: Session, message_id: int
) -> List[models.CollaborationAttachment]:
    """Get attachments for a message"""
    return (
        db.query(models.CollaborationAttachment)
        .filter(models.CollaborationAttachment.message_id == message_id)
        .all()
    )
