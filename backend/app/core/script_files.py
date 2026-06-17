from pathlib import Path

from app.core.script_validator import SCRIPTS_ROOT


ALLOWED_SCRIPT_SUFFIXES = {".sh", ".py"}


def list_script_files() -> list[dict[str, object]]:
    root = SCRIPTS_ROOT.resolve()
    files: list[dict[str, object]] = []

    if not root.exists():
        return files

    for path in sorted(root.rglob("*")):
        relative_parts = path.relative_to(root).parts
        if any(part.startswith(".") for part in relative_parts):
            continue
        if not path.is_file() or path.suffix not in ALLOWED_SCRIPT_SUFFIXES:
            continue

        resolved = path.resolve(strict=True)
        try:
            relative_path = resolved.relative_to(root)
        except ValueError:
            continue

        if ".." in relative_path.parts:
            continue

        relative = relative_path.as_posix()
        files.append(
            {
                "path": relative,
                "name": Path(relative).name,
                "category": relative_path.parts[0] if len(relative_path.parts) > 1 else "",
                "size": resolved.stat().st_size,
                "executable": bool(resolved.stat().st_mode & 0o111),
            }
        )

    return files
