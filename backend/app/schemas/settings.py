import re

from pydantic import BaseModel, Field, field_validator, model_validator

# ── Remote task root validation ──

REMOTE_TASK_ROOT_ALLOWED_PREFIXES = frozenset({
    "$HOME/",
    "/home/",
    "/root/",
    "/data/",
    "/mnt/",
    "/opt/hpcdeploy/",
})

# Paths that equal these exact values are always rejected
REMOTE_TASK_ROOT_BLOCKED_EXACT = frozenset({
    "/",
    "/root",
    "/home",
    "/opt",
    "/tmp",
    "/usr",
    "/etc",
})

# Prefixes that are always rejected (longest first for correct matching)
REMOTE_TASK_ROOT_BLOCKED_PREFIXES = frozenset({
    "/etc/",
    "/usr/",
    "/bin/",
    "/sbin/",
    # /var/ is not explicitly allowed — reject unless listed in allowed prefixes
    "/var/",
    "/tmp/",
})

# Substrings that are always rejected
REMOTE_TASK_ROOT_FORBIDDEN_SUBSTRINGS = frozenset({
    "..",
    ";",
    "&&",
    "|",
    "`",
    "$(",
    "\n",
    "\r",
})

FORBIDDEN_KEYS = frozenset({
    "command",
    "raw_shell",
    "raw_args",
    "remote_path",
    "local_path",
    "delete_path",
    "target_dir",
    "system_dir",
    "script_content",
    "private_key_content",
    "probe_timeout_seconds",
    "probe_all_skip_offline_default",
    "task_history_page_size",
    "cleanup_artifacts_table_height",
    "auto_cleanup_last_run_at",
    "auto_cleanup_last_deleted_dirs",
    "auto_cleanup_last_freed_bytes",
    "auto_cleanup_last_failed_count",
    "auto_cleanup_last_status",
    "auto_cleanup_last_message",
    "auto_cleanup_last_run_date",
    "remote_apptainer_dir",
    "remote_task_root",
    "ssh_key_dir",
    "ssh_key_dir_absolute",
    "admin_password",
})

# ── Defaults ──

DEFAULT_SETTINGS: dict[str, str] = {
    "default_ssh_key_name": "",
    "remote_task_root": "$HOME/hpcdeploy/tasks",
    "remote_apptainer_dir": "$HOME/hpcdeploy/apptainer",
    "auto_cleanup_enabled": "false",
    "local_artifact_retention_days": "30",
    "auto_cleanup_time": "03:00",
}


# ── Validators ──

def validate_remote_task_root(v: str) -> str:
    """Validate remote_task_root is a safe path."""
    stripped = v.strip()
    if not stripped:
        raise ValueError("remote_task_root must not be empty")

    # Reject forbidden substrings
    for forbidden in REMOTE_TASK_ROOT_FORBIDDEN_SUBSTRINGS:
        if forbidden in stripped:
            raise ValueError(f"invalid remote_task_root: contains '{forbidden}'")

    # Reject blocked exact matches
    if stripped in REMOTE_TASK_ROOT_BLOCKED_EXACT:
        raise ValueError(f"invalid remote_task_root: '{stripped}' is not allowed")

    # Reject blocked prefixes
    for prefix in REMOTE_TASK_ROOT_BLOCKED_PREFIXES:
        if stripped.startswith(prefix):
            raise ValueError(f"invalid remote_task_root: cannot start with '{prefix}'")

    # Must start with an allowed prefix
    if not any(stripped.startswith(prefix) for prefix in REMOTE_TASK_ROOT_ALLOWED_PREFIXES):
        raise ValueError(
            f"invalid remote_task_root: must start with one of "
            f"{sorted(REMOTE_TASK_ROOT_ALLOWED_PREFIXES)}, got '{stripped}'"
        )

    return stripped


# ── Schemas ──

class RuntimePathInfo(BaseModel):
    key: str
    label: str
    path: str
    kind: str
    description: str
    exists: bool = False
    size_bytes: int | None = None
    file_count: int | None = None
    attention: bool = False


class SettingsResponse(BaseModel):
    default_ssh_key_name: str = ""
    remote_task_root: str = "$HOME/hpcdeploy/tasks"
    remote_apptainer_dir: str = "$HOME/hpcdeploy/apptainer"
    ssh_key_dir: str = "backend/keys"
    ssh_key_dir_absolute: str = ""
    auto_cleanup_enabled: bool = False
    local_artifact_retention_days: int = 30
    auto_cleanup_time: str = "03:00"
    auto_cleanup_last_run_at: str = ""
    auto_cleanup_last_deleted_dirs: int = 0
    auto_cleanup_last_freed_bytes: int = 0
    auto_cleanup_last_failed_count: int = 0
    auto_cleanup_last_status: str = ""
    auto_cleanup_last_message: str = ""
    admin_password_configured: bool = False
    runtime_paths: list[RuntimePathInfo] = []


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str = Field(min_length=6, max_length=128)


class ChangePasswordResponse(BaseModel):
    success: bool
    message: str


class SettingsUpdate(BaseModel):
    """Only fields that can be updated via PUT."""
    model_config = {"extra": "forbid"}

    default_ssh_key_name: str | None = None
    auto_cleanup_enabled: bool | None = None
    local_artifact_retention_days: int | None = Field(default=None, ge=1, le=3650)
    auto_cleanup_time: str | None = None

    @model_validator(mode="after")
    def _check_no_forbidden(self) -> "SettingsUpdate":
        for key in self.model_dump(exclude_none=True):
            if key in FORBIDDEN_KEYS:
                raise ValueError(f"field not allowed: {key}")
        return self

    @field_validator("default_ssh_key_name")
    @classmethod
    def _validate_key_name(cls, v: str | None) -> str | None:
        if v is not None and v.strip():
            # Key name should be just a filename, no path separators
            if "/" in v or "\\" in v:
                raise ValueError("default_ssh_key_name must be a filename, not a path")
        return v

    @field_validator("auto_cleanup_time")
    @classmethod
    def _validate_cleanup_time(cls, v: str | None) -> str | None:
        if v is None:
            return v
        stripped = v.strip()
        if not re.fullmatch(r"([01]\d|2[0-3]):[0-5]\d", stripped):
            raise ValueError("auto_cleanup_time must use HH:mm format")
        return stripped
