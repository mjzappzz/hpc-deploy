from app.core.audit import write_audit_log
from app.core.auth import require_admin_token
from app.core.ops_command_rich_text import sanitize_ops_command_rich_text
from app.db.database import get_db
from app.models.ops_command import OpsCommand
from app.schemas.ops_command import OpsCommandCreate, OpsCommandRead, OpsCommandUpdate
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session


router = APIRouter(prefix="/ops-commands", tags=["ops-commands"])


def _get_or_404(command_id: int, db: Session) -> OpsCommand:
    command = db.get(OpsCommand, command_id)
    if command is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="ops command not found")
    return command


def _to_read(command: OpsCommand) -> OpsCommandRead:
    result = OpsCommandRead.model_validate(command)
    return result.model_copy(update={"content": sanitize_ops_command_rich_text(result.content)})


@router.get("", response_model=list[OpsCommandRead])
def list_ops_commands(db: Session = Depends(get_db)) -> list[OpsCommandRead]:
    return [_to_read(command) for command in db.query(OpsCommand).order_by(OpsCommand.updated_at.desc(), OpsCommand.id.desc()).all()]


@router.post("", response_model=OpsCommandRead, status_code=status.HTTP_201_CREATED)
def create_ops_command(
    payload: OpsCommandCreate,
    db: Session = Depends(get_db),
    _: str = Depends(require_admin_token),
) -> OpsCommandRead:
    command = OpsCommand(**payload.model_dump())
    db.add(command)
    db.commit()
    db.refresh(command)
    write_audit_log(
        db, action="ops_command.create", target_type="ops_command", status="success",
        actor="admin", target_id=str(command.id), target_name=command.title,
        message="created ops command entry", detail={"command_id": command.id, "title": command.title},
    )
    return _to_read(command)


@router.put("/{command_id}", response_model=OpsCommandRead)
def update_ops_command(
    command_id: int,
    payload: OpsCommandUpdate,
    db: Session = Depends(get_db),
    _: str = Depends(require_admin_token),
) -> OpsCommandRead:
    command = _get_or_404(command_id, db)
    command.title = payload.title
    command.content = payload.content
    db.commit()
    db.refresh(command)
    write_audit_log(
        db, action="ops_command.update", target_type="ops_command", status="success",
        actor="admin", target_id=str(command.id), target_name=command.title,
        message="updated ops command entry", detail={"command_id": command.id, "title": command.title},
    )
    return _to_read(command)


@router.delete("/{command_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_ops_command(
    command_id: int,
    db: Session = Depends(get_db),
    _: str = Depends(require_admin_token),
) -> None:
    command = _get_or_404(command_id, db)
    title = command.title
    db.delete(command)
    db.commit()
    write_audit_log(
        db, action="ops_command.delete", target_type="ops_command", status="success",
        actor="admin", target_id=str(command_id), target_name=title,
        message="deleted ops command entry", detail={"command_id": command_id, "title": title},
    )
