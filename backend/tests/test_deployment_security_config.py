from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
INSTALL_SCRIPT = PROJECT_ROOT / "deploy" / "scripts" / "install_hpcdeploy_service.sh"
COMMON_RUNTIME_SCRIPT = PROJECT_ROOT / "deploy" / "scripts" / "common_runtime.sh"
RESET_SCRIPT = PROJECT_ROOT / "deploy" / "scripts" / "reset_admin_password.sh"
REDEPLOY_SCRIPT = PROJECT_ROOT / "deploy" / "scripts" / "redeploy_hpcdeploy.sh"
SERVICE_TEMPLATE = PROJECT_ROOT / "deploy" / "systemd" / "hpcdeploy-backend.service"


def test_install_creates_protected_environment_file_and_loads_it() -> None:
    script = INSTALL_SCRIPT.read_text(encoding="utf-8")

    assert 'HPCDEPLOY_ENV_FILE="/etc/hpcdeploy/hpcdeploy.env"' in script
    assert "SECRET_KEY=" in script
    assert "HPCDEPLOY_ADMIN_PASSWORD=" in script
    assert 'chmod 600 "$HPCDEPLOY_ENV_FILE"' in script
    assert "EnvironmentFile=/etc/hpcdeploy/hpcdeploy.env" in script


def test_install_preserves_existing_security_configuration() -> None:
    script = INSTALL_SCRIPT.read_text(encoding="utf-8")

    assert 'if [[ -f "$HPCDEPLOY_ENV_FILE" ]]' in script
    assert "保留现有安全配置" in script


def test_install_rebuilds_an_incomplete_python_virtual_environment() -> None:
    script = INSTALL_SCRIPT.read_text(encoding="utf-8")

    assert '[[ ! -x "$BACKEND_DIR/.deps/bin/python" || ! -x "$BACKEND_DIR/.deps/bin/pip" ]]' in script
    assert 'rm -rf "$BACKEND_DIR/.deps"' in script
    assert "检测到不完整的 Python 虚拟环境，正在重新创建" in script


def test_backend_health_retries_do_not_print_transient_connection_errors() -> None:
    script = COMMON_RUNTIME_SCRIPT.read_text(encoding="utf-8")

    assert 'curl --noproxy \'*\' --fail --silent "$health_url" >/dev/null' in script


def test_service_template_loads_production_environment_file() -> None:
    service = SERVICE_TEMPLATE.read_text(encoding="utf-8")

    assert "EnvironmentFile=/etc/hpcdeploy/hpcdeploy.env" in service


def test_redeploy_refuses_to_restart_backend_with_active_tasks() -> None:
    script = REDEPLOY_SCRIPT.read_text(encoding="utf-8")

    assert "assert_no_active_tasks" in script
    assert "/api/tasks?active_only=true&limit=1" in script
    assert "检测到活动任务，拒绝重启后端" in script
    assert script.count("assert_no_active_tasks") >= 3


def test_root_only_password_reset_rotates_sessions_and_clears_db_override() -> None:
    script = RESET_SCRIPT.read_text(encoding="utf-8")

    assert "EUID" in script
    assert "pre_admin_reset_" in script
    assert "DELETE FROM system_settings WHERE key = 'admin_password'" in script
    assert "SECRET_KEY" in script
    assert "systemctl restart hpcdeploy-backend" in script
    assert "wait_for_backend_health" in script
