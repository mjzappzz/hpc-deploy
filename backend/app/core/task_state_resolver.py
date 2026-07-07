"""Unified task state resolution — FINAL_STATE rules.

Priority:
  1. report_status == "FAIL"  → FINAL_STATE = "FAILED"
  2. report_status == "PASS"  → FINAL_STATE = "SUCCESS"
  3. execution_status == "FAILED" → FINAL_STATE = "FAILED"
  4. else                     → FINAL_STATE = "UNKNOWN"

This module is the single source of truth for task state display.
"""

REPORT_STATUS_VALUES = {"PASS", "FAILED", "UNKNOWN"}


def resolve_final_status(
    execution_status: str,
    report_status: str | None,
) -> str:
    """Compute the unified final status for display.

    Args:
        execution_status: Task.status from the tasks table (SUCCESS / FAILED / …).
        report_status: TaskReportSummary.report_status (PASS / FAIL / UNKNOWN / None).

    Returns:
        One of "FAILED", "SUCCESS", "UNKNOWN".
    """
    normalized_report = (report_status or "UNKNOWN").upper()
    normalized_exec = execution_status.upper() if execution_status else "UNKNOWN"

    # Rule 1: report FAIL wins everything — mapped to FAILED for consistency
    if normalized_report == "FAIL":
        return "FAILED"
    # Rule 2: report PASS overrides execution — mapped to SUCCESS for consistency
    if normalized_report == "PASS":
        return "SUCCESS"
    # Rule 3: no useful report — fall back to execution status
    if normalized_exec == "FAILED":
        return "FAILED"
    # Rule 4: everything else
    return "UNKNOWN"


def batch_final_status_label(final_status: str) -> str:
    """Map final_status to a human-readable Chinese label for batch views."""
    labels = {
        "FAILED": "失败",
        "SUCCESS": "通过",
        "UNKNOWN": "未知",
    }
    return labels.get(final_status, final_status)


def batch_final_status_tag_type(final_status: str) -> str:
    """Map final_status to an Element Plus tag type."""
    types = {
        "FAILED": "danger",
        "SUCCESS": "success",
        "UNKNOWN": "info",
    }
    return types.get(final_status, "info")
