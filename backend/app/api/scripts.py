from app.core.param_validator import validate_script_params
from app.core.script_library import (
    delete_library_file,
    list_library_files,
    normalize_library_path,
    read_library_preview,
    resolve_library_path,
    save_library_file,
)
from app.core.audit import write_audit_log
from app.core.script_validator import ScriptValidationError, normalize_script_path, resolve_script_path
from app.db.database import get_db
from app.models.script import Script
from app.schemas.param_validation import ParamValidateRequest, ParamValidateResponse
from app.schemas.script import ScriptCreate, ScriptRead, ScriptUpdate
from app.schemas.script_file import ScriptFilePreviewRead, ScriptFileRead
from app.schemas.script_validation import ScriptValidateResponse
from fastapi import APIRouter, Body, Depends, HTTPException, Query, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

router = APIRouter(prefix="/scripts", tags=["scripts"])


def _get_script_or_404(db: Session, script_id: int) -> Script:
    script = db.get(Script, script_id)
    if script is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="script not found")
    return script


@router.get("", response_model=list[ScriptRead])
def list_scripts(db: Session = Depends(get_db)) -> list[Script]:
    return db.query(Script).order_by(Script.id.desc()).all()


@router.get("/files", response_model=list[ScriptFileRead])
def list_files() -> list[dict[str, object]]:
    return list_library_files()


@router.get("/files/preview", response_model=ScriptFilePreviewRead)
def preview_file(path: str = Query(..., min_length=1)) -> dict[str, object]:
    try:
        normalized = normalize_library_path(path)
        return read_library_preview(normalized)
    except ScriptValidationError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.get("/files/download")
def download_file(path: str = Query(..., min_length=1)) -> FileResponse:
    try:
        normalized = normalize_library_path(path)
        resolved = resolve_library_path(normalized)
    except ScriptValidationError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return FileResponse(resolved, filename=resolved.name)


@router.post("/files/upload", response_model=ScriptFileRead, status_code=status.HTTP_201_CREATED)
def upload_file(
    category: str = Query(..., min_length=1),
    filename: str = Query(..., min_length=1),
    content: bytes = Body(...),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    try:
        result = save_library_file(category.strip(), filename.strip(), content)
        write_audit_log(
            db, action="script.upload", target_type="script", status="success",
            target_name=filename.strip(),
            message=f"uploaded script {category}/{filename}",
            detail={"category": category.strip(), "filename": filename.strip()},
        )
        return result
    except ScriptValidationError as exc:
        write_audit_log(
            db, action="script.upload", target_type="script", status="failed",
            target_name=filename.strip(),
            message=f"upload failed: {exc}",
        )
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.delete("/files", response_model=ScriptFileRead)
def remove_file(
    path: str = Query(..., min_length=1),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    try:
        normalized = normalize_library_path(path)
        deleted = delete_library_file(normalized)
        write_audit_log(
            db, action="script.delete", target_type="script", status="success",
            target_name=path,
            message=f"deleted script {path}",
        )
    except ScriptValidationError as exc:
        write_audit_log(
            db, action="script.delete", target_type="script", status="failed",
            target_name=path,
            message=f"delete failed: {exc}",
        )
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    if str(deleted["path"]).startswith("scripts/"):
        relative_path = str(deleted["path"]).removeprefix("scripts/")
        db.query(Script).filter(Script.file_path == relative_path).delete()
        db.commit()
    return deleted


@router.post("", response_model=ScriptRead, status_code=status.HTTP_201_CREATED)
def create_script(payload: ScriptCreate, db: Session = Depends(get_db)) -> Script:
    data = payload.model_dump()
    data["file_path"] = _normalize_or_400(data["file_path"])
    data["params_schema"] = data.get("params_schema") or {}
    script = Script(**data)
    db.add(script)
    db.commit()
    db.refresh(script)
    return script


@router.get("/{script_id}", response_model=ScriptRead)
def get_script(script_id: int, db: Session = Depends(get_db)) -> Script:
    return _get_script_or_404(db, script_id)


@router.put("/{script_id}", response_model=ScriptRead)
def update_script(
    script_id: int,
    payload: ScriptUpdate,
    db: Session = Depends(get_db),
) -> Script:
    script = _get_script_or_404(db, script_id)
    data = payload.model_dump(exclude_unset=True)
    if "file_path" in data:
        data["file_path"] = _normalize_or_400(data["file_path"])
    if data.get("params_schema") is None and "params_schema" in data:
        data["params_schema"] = {}
    for key, value in data.items():
        setattr(script, key, value)
    db.commit()
    db.refresh(script)
    return script


@router.delete("/{script_id}")
def delete_script(script_id: int, db: Session = Depends(get_db)) -> dict[str, bool]:
    script = _get_script_or_404(db, script_id)
    db.delete(script)
    db.commit()
    return {"deleted": True}


@router.post("/{script_id}/validate", response_model=ScriptValidateResponse)
def validate_script(script_id: int, db: Session = Depends(get_db)) -> ScriptValidateResponse:
    script = _get_script_or_404(db, script_id)
    try:
        resolved = resolve_script_path(script.file_path)
    except ScriptValidationError as exc:
        return ScriptValidateResponse(
            success=False,
            enabled=script.enabled,
            dangerous=script.dangerous,
            file_path=script.file_path,
            params_schema_valid=True,
            error=str(exc),
        )

    if not script.enabled:
        return ScriptValidateResponse(
            success=False,
            enabled=False,
            dangerous=script.dangerous,
            file_path=script.file_path,
            resolved_path=str(resolved),
            params_schema_valid=True,
            error="script is disabled",
        )

    return ScriptValidateResponse(
        success=True,
        enabled=script.enabled,
        dangerous=script.dangerous,
        file_path=script.file_path,
        resolved_path=str(resolved),
        params_schema_valid=True,
    )


@router.post("/{script_id}/validate-params", response_model=ParamValidateResponse)
def validate_params(
    script_id: int,
    payload: ParamValidateRequest,
    db: Session = Depends(get_db),
) -> ParamValidateResponse:
    script = _get_script_or_404(db, script_id)
    errors = validate_script_params(script.params_schema or {}, payload.params)
    return ParamValidateResponse(success=not errors, errors=errors)


def _normalize_or_400(file_path: str) -> str:
    try:
        return normalize_script_path(file_path)
    except ScriptValidationError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
