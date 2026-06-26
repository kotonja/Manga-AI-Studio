from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session, select

from manga_api.commands import CommandInterpreter
from manga_api.db import get_session
from manga_api.models import CommandHistory, Project
from manga_api.schemas import (
    CommandExecuteRequest,
    CommandExecuteResult,
    CommandHistoryRead,
    CommandInterpretRequest,
    CommandInterpretResult,
)
from manga_api.storage import get_object_storage

router = APIRouter(tags=["commands"])


@router.post("/commands/interpret", response_model=CommandInterpretResult, status_code=status.HTTP_201_CREATED)
def interpret_command(
    payload: CommandInterpretRequest,
    session: Session = Depends(get_session),
) -> CommandInterpretResult:
    try:
        return CommandInterpreter(session).interpret(payload, persist=True)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.post("/commands/execute", response_model=CommandExecuteResult, status_code=status.HTTP_202_ACCEPTED)
def execute_command(
    payload: CommandExecuteRequest,
    session: Session = Depends(get_session),
    storage=Depends(get_object_storage),
) -> CommandExecuteResult:
    try:
        result = CommandInterpreter(session, storage).execute(payload)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    if result.status == "failed":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=result.error_message or "Command failed")
    return result


@router.get("/projects/{project_id}/commands", response_model=list[CommandHistoryRead])
def list_project_commands(
    project_id: uuid.UUID,
    session: Session = Depends(get_session),
    limit: int = 20,
) -> list[CommandHistory]:
    project = session.get(Project, project_id)
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
    bounded_limit = max(1, min(100, limit))
    return list(
        session.exec(
            select(CommandHistory)
            .where(CommandHistory.project_id == project_id)
            .order_by(CommandHistory.created_at.desc(), CommandHistory.id.desc())
            .limit(bounded_limit)
        ).all()
    )
