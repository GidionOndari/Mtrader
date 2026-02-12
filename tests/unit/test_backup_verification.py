from pathlib import Path


def test_dr_drill_report_exists() -> None:
    assert any(Path("docs/operations").glob("dr-drill-*.md"))


def test_backup_recovery_runbook_exists() -> None:
    assert Path("docs/runbooks/database-recovery.md").exists()
