from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, Body
from fastapi.security import OAuth2PasswordBearer
from fastapi.responses import JSONResponse
from typing import List, Optional
from datetime import datetime, timedelta
import secrets
import os
import jwt
from sqlalchemy.orm import Session

from .. import crud, models, schemas  # Make sure to import schemas here
from ..database import get_db
from ..oauth2 import get_current_user
from ..config import settings


router = APIRouter(
    prefix="/collaboration",
    tags=["collaboration"],
    responses={404: {"description": "Not found"}},
)


# Helper functions
def generate_access_token(
    session_id: int, participant_id: int, duration_days: int = 30
) -> str:
    """Generate a secure access token for collaboration session"""
    expiration = datetime.utcnow() + timedelta(days=duration_days)
    payload = {
        "session_id": session_id,
        "participant_id": participant_id,
        "exp": expiration,
    }
    token = jwt.encode(payload, settings.secret_key, algorithm=settings.algorithm)
    return token


def verify_access_token(token: str):
    """Verify the collaboration access token"""
    try:
        payload = jwt.decode(
            token, settings.secret_key, algorithms=[settings.algorithm]
        )
        session_id = payload.get("session_id")
        participant_id = payload.get("participant_id")

        if session_id is None or participant_id is None:
            raise HTTPException(status_code=401, detail="Invalid access token")

        return {"session_id": session_id, "participant_id": participant_id}
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="Invalid or expired access token")


async def get_session_participant(token: str, db: Session = Depends(get_db)):
    """Get session and participant from token"""
    token_data = verify_access_token(token)
    session = crud.get_collaboration_session(db, token_data["session_id"])

    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    participant = crud.get_collaboration_participant(db, token_data["participant_id"])

    if not participant or participant.session_id != session.id:
        raise HTTPException(status_code=401, detail="Invalid participant")

    # Update last viewed timestamp
    participant.last_viewed_at = datetime.utcnow()
    db.commit()

    return {"session": session, "participant": participant}


# Endpoint to create a new collaboration session for an external ticket
@router.post("/sessions", response_model=schemas.SessionResponse)
async def create_collaboration_session(
    session_data: schemas.SessionCreate,
    current_user: schemas.UserOut = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    # Only RYZE developers can create sessions
    if current_user.user_type != "developer":
        raise HTTPException(
            status_code=403, detail="Only developers can create collaboration sessions"
        )

    # Create the session
    session = crud.create_collaboration_session(
        db,
        external_ticket_id=session_data.external_ticket_id,
        source_system=session_data.source_system,
        metadata=session_data.metadata,
    )

    # Add the current user as a participant
    participant = crud.create_collaboration_participant(
        db,
        session_id=session.id,
        user_id=current_user.id,
        email=current_user.email,
        user_name=current_user.full_name or current_user.username,
        user_type="ryze_developer",
    )

    # Refresh session to include participant
    db.refresh(session)

    # Format response
    response_data = schemas.SessionResponse.from_orm(session)

    # Mark current user's participant
    for p in response_data.participants:
        if p.id == participant.id:
            p.is_current_user = True

    return response_data


# Endpoint to generate access token for external users
@router.post("/sessions/{session_id}/access")
async def create_access_token(
    session_id: int,
    request: schemas.AccessRequest,
    current_user: schemas.UserOut = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    # Verify session exists
    session = crud.get_collaboration_session(db, session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    # Check if user has access to this session
    if not crud.user_has_session_access(db, current_user.id, session_id):
        raise HTTPException(
            status_code=403, detail="You don't have access to this session"
        )

    # Check if participant with this email already exists
    existing_participant = crud.get_participant_by_email(
        db, session_id=session_id, email=request.email
    )

    if existing_participant:
        participant_id = existing_participant.id
    else:
        # Create new participant
        participant = crud.create_collaboration_participant(
            db,
            session_id=session_id,
            user_id=None,  # External user
            email=request.email,
            user_name=request.user_name or request.email.split("@")[0],
            user_type=request.user_type,
        )
        participant_id = participant.id

    # Generate access token
    token = generate_access_token(
        session_id=session_id,
        participant_id=participant_id,
        duration_days=request.duration_days,
    )

    # Create access URL that client can use
    access_url = f"{settings.frontend_url}/collaboration/{session_id}/access/{token}"

    return {
        "access_token": token,
        "access_url": access_url,
        "expires_in": request.duration_days * 86400,  # seconds
    }


# Endpoint to validate token and get session info
@router.get("/sessions/{session_id}", response_model=schemas.SessionResponse)
async def get_session(session_id: int, token: str, db: Session = Depends(get_db)):
    # Verify token and get session/participant
    session_data = await get_session_participant(token, db)
    session = session_data["session"]
    current_participant = session_data["participant"]

    # Check that session ID in URL matches token
    if session.id != session_id:
        raise HTTPException(status_code=400, detail="Session ID mismatch")

    # Format response
    response_data = schemas.SessionResponse.from_orm(session)

    # Mark current user's participant
    for p in response_data.participants:
        if p.id == current_participant.id:
            p.is_current_user = True

    return response_data


# Endpoint to update session status
@router.patch("/sessions/{session_id}/status", response_model=schemas.SessionResponse)
async def update_session_status(
    session_id: int,
    status_update: schemas.SessionStatus,
    token: str,
    db: Session = Depends(get_db),
):
    # Verify token and get session/participant
    session_data = await get_session_participant(token, db)
    session = session_data["session"]
    current_participant = session_data["participant"]

    # Check that session ID in URL matches token
    if session.id != session_id:
        raise HTTPException(status_code=400, detail="Session ID mismatch")

    # Only RYZE developers can update status
    if current_participant.user_type != "ryze_developer":
        raise HTTPException(
            status_code=403, detail="Only RYZE developers can update status"
        )

    # Cannot change status from resolved
    if session.status == "resolved" and status_update.status != "resolved":
        raise HTTPException(
            status_code=400, detail="Cannot change status from resolved"
        )

    # Update session status
    updated_session = crud.update_session_status(
        db, session_id=session_id, status=status_update.status
    )

    # Add system message about status change
    crud.create_system_message(
        db,
        session_id=session_id,
        content=f"Status changed to: {status_update.status}",
        metadata={
            "changed_by": current_participant.id,
            "previous_status": session.status,
        },
    )

    # Format response
    response_data = schemas.SessionResponse.from_orm(updated_session)

    # Mark current user's participant
    for p in response_data.participants:
        if p.id == current_participant.id:
            p.is_current_user = True

    return response_data


# Endpoint to get messages
@router.get(
    "/sessions/{session_id}/messages", response_model=List[schemas.MessageResponse]
)
async def get_messages(
    session_id: int,
    token: str,
    after_id: Optional[int] = 0,
    limit: Optional[int] = 100,
    db: Session = Depends(get_db),
):
    # Verify token and get session/participant
    session_data = await get_session_participant(token, db)
    session = session_data["session"]

    # Check that session ID in URL matches token
    if session.id != session_id:
        raise HTTPException(status_code=400, detail="Session ID mismatch")

    # Get messages
    messages = crud.get_session_messages(
        db, session_id=session_id, after_id=after_id, limit=limit
    )

    # Format response with attachments
    response_messages = []
    for message in messages:
        message_data = schemas.MessageResponse.from_orm(message)

        # Add attachments if any
        attachments = crud.get_message_attachments(db, message.id)
        if attachments:
            message_data.attachments = [
                {
                    "id": attachment.id,
                    "file_name": attachment.file_name,
                    "file_path": attachment.file_path,
                    "file_type": attachment.file_type,
                    "file_size": attachment.file_size,
                }
                for attachment in attachments
            ]

        response_messages.append(message_data)

    return response_messages


# Endpoint to create a message
@router.post("/sessions/{session_id}/messages", response_model=schemas.MessageResponse)
async def create_message(
    session_id: int,
    message: schemas.MessageCreate,
    token: str,
    db: Session = Depends(get_db),
):
    # Verify token and get session/participant
    session_data = await get_session_participant(token, db)
    session = session_data["session"]
    participant = session_data["participant"]

    # Check that session ID in URL matches token
    if session.id != session_id:
        raise HTTPException(status_code=400, detail="Session ID mismatch")

    # Cannot send messages to resolved sessions
    if session.status == "resolved":
        raise HTTPException(
            status_code=400, detail="Cannot send messages to resolved sessions"
        )

    # Create the message
    new_message = crud.create_message(
        db,
        session_id=session_id,
        participant_id=participant.id,
        content=message.content,
        message_type=message.message_type,
        metadata=message.metadata,
    )

    # Handle attachments if any
    attachments_data = []
    if message.attachments:
        for attachment_info in message.attachments:
            attachment = crud.create_attachment(
                db,
                message_id=new_message.id,
                file_name=attachment_info["file_name"],
                file_path=attachment_info["file_path"],
                file_type=attachment_info["file_type"],
                file_size=attachment_info["file_size"],
            )
            attachments_data.append(
                {
                    "id": attachment.id,
                    "file_name": attachment.file_name,
                    "file_path": attachment.file_path,
                    "file_type": attachment.file_type,
                    "file_size": attachment.file_size,
                }
            )

    # Format response
    response_data = schemas.MessageResponse.from_orm(new_message)
    response_data.attachments = attachments_data if attachments_data else None

    return response_data


# Endpoint to upload file attachment
@router.post(
    "/sessions/{session_id}/attachments", response_model=schemas.AttachmentResponse
)
async def upload_attachment(
    session_id: int,
    token: str,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    # Verify token and get session/participant
    session_data = await get_session_participant(token, db)
    session = session_data["session"]

    # Check that session ID in URL matches token
    if session.id != session_id:
        raise HTTPException(status_code=400, detail="Session ID mismatch")

    # Cannot upload to resolved sessions
    if session.status == "resolved":
        raise HTTPException(
            status_code=400, detail="Cannot upload files to resolved sessions"
        )

    # Generate a secure filename
    file_ext = os.path.splitext(file.filename)[1]
    secure_filename = f"{secrets.token_hex(8)}{file_ext}"

    # Set up upload directory
    upload_dir = os.path.join(settings.upload_dir, "collaboration", str(session_id))
    os.makedirs(upload_dir, exist_ok=True)

    # Save file
    file_path = os.path.join(upload_dir, secure_filename)
    file_size = 0

    with open(file_path, "wb") as buffer:
        # Read and write in chunks to handle large files
        chunk = await file.read(1024)
        while chunk:
            buffer.write(chunk)
            file_size += len(chunk)
            chunk = await file.read(1024)

    # Create file entry in database
    # Note: In a real implementation, you might want to create a message
    # with this attachment automatically
    attachment = crud.create_attachment(
        db,
        message_id=None,  # Will be linked to a message later
        file_name=file.filename,
        file_path=f"/uploads/collaboration/{session_id}/{secure_filename}",
        file_type=file.content_type,
        file_size=file_size,
    )

    return schemas.AttachmentResponse.from_orm(attachment)
