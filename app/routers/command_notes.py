# app/routers/command_notes.py
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Optional
import logging
from app.database import get_db
from app.schemas import CommandNoteResponse, CommandNoteCreate, CommandExecutionResponse,CommandExecutionResult
from app import oauth2, models
from app.models import User
import subprocess
from datetime import datetime
import os

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/command_notes",
    tags=["Command Notes"]
)

@router.post("/", status_code=status.HTTP_201_CREATED, response_model=CommandNoteResponse)
async def create_command_note(
    note: CommandNoteCreate,
    current_user: User = Depends(oauth2.get_current_user),
    db: Session = Depends(get_db)
):
    """Create a new command note"""
    logger.info(f"Creating command note for user {current_user.id}")
    try:
        # Create new command note
        new_note = models.CommandNote(
            title=note.title,
            description=note.description,
            commands=note.commands,
            tags=note.tags,
            user_id=current_user.id
        )
        
        db.add(new_note)
        db.commit()
        db.refresh(new_note)
        
        logger.info(f"Created note with ID {new_note.id}")
        return new_note
        
    except Exception as e:
        logger.error(f"Error creating note: {str(e)}")
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/", response_model=List[CommandNoteResponse])
async def get_command_notes(
    current_user: User = Depends(oauth2.get_current_user),
    tag: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """Get all command notes for the current user"""
    try:
        query = db.query(models.CommandNote).filter(
            models.CommandNote.user_id == current_user.id
        )
        
        if tag:
            # Use PostgreSQL array operator @> for contains
            query = query.filter(models.CommandNote.tags.any(tag))
            
        return query.all()
        
    except Exception as e:
        logger.error(f"Error getting notes: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
    


@router.post("/{note_id}/execute", response_model=CommandExecutionResponse)
async def execute_command_note(
    note_id: int,
    dry_run: bool = False,
    current_user: User = Depends(oauth2.get_current_user),
    db: Session = Depends(get_db)
):
    """Execute commands in a note"""
    logger.info(f"Executing note {note_id} (dry_run: {dry_run})")
    
    try:
        # Get the note and verify ownership
        note = db.query(models.CommandNote).filter(
            models.CommandNote.id == note_id,
            models.CommandNote.user_id == current_user.id
        ).first()
        
        if not note:
            logger.error(f"Note {note_id} not found or access denied")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Command note not found or access denied"
            )
        
        results = []
        
        for cmd in note.commands:
            if dry_run:
                result = CommandExecutionResult(
                    command=cmd,
                    success=True,
                    output=f"[DRY RUN] Would execute: {cmd}",
                    executed_at=datetime.now()
                )
            else:
                try:
                    if "cd" in cmd:
                        # Handle directory changes in Python
                        directory = cmd.split("cd ")[1].strip()
                        os.chdir(directory)
                        result = CommandExecutionResult(
                            command=cmd,
                            success=True,
                            output=f"Changed directory to {directory}",
                            executed_at=datetime.now()
                        )
                    else:
                        # Run command in subprocess for non-'cd' commands
                        process = subprocess.run(
                            cmd,
                            shell=True,
                            capture_output=True,
                            text=True,
                            timeout=30
                        )
                        result = CommandExecutionResult(
                            command=cmd,
                            success=process.returncode == 0,
                            output=process.stdout if process.returncode == 0 else process.stderr,
                            executed_at=datetime.now()
                        )
                except subprocess.TimeoutExpired:
                    result = CommandExecutionResult(
                        command=cmd,
                        success=False,
                        output="Command execution timed out",
                        executed_at=datetime.now()
                    )
                except Exception as e:
                    result = CommandExecutionResult(
                        command=cmd,
                        success=False,
                        output=str(e),
                        executed_at=datetime.now()
                    )
            
            results.append(result)
            logger.info(
                f"Command executed: note_id={note_id}, "
                f"command='{cmd}', success={result.success}"
            )
        
        return CommandExecutionResponse(
            note_id=note_id,
            title=note.title,
            results=results
        )
        
    except Exception as e:
        logger.error(f"Error executing commands: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to execute commands: {str(e)}"
        )
