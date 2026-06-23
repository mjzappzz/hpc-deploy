from pydantic import BaseModel, field_validator, model_validator

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
    "remote_apptainer_dir",
    "remote_task_root",
    "ssh_key_dir",
    "ssh_key_dir_absolute",
})

# ── Defaults ──

DEFAULT_SETTINGS: dict[str, str] = {
    "default_ssh_key_name": "",
    "remote_task_root": "$HOME/hpcdeploy/tasks",
    "remote_apptainer_dir": "$HOME/hpcdeploy/apptainer",
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

class SettingsResponse(BaseModel):
    default_ssh_key_name: str = ""
    remote_task_root: str = "$HOME/hpcdeploy/tasks"
    remote_apptainer_dir: str = "$HOME/hpcdeploy/apptainer"
    ssh_key_dir: str = "backend/keys"
    ssh_key_dir_absolute: str = ""


class SettingsUpdate(BaseModel):
    """Only fields that can be updated via PUT."""
    model_config = {"extra": "forbid"}

    default_ssh_key_name: str | None = None

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
