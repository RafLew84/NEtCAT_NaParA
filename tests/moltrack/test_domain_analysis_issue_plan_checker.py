from __future__ import annotations

from pathlib import Path

import pytest

from scripts.check_domain_analysis_issue_plan import validate_issue_plan


PROJECT_ROOT = Path(__file__).resolve().parents[2]
ISSUES_DIR = (
    PROJECT_ROOT
    / ".scratch"
    / "manual-domain-orientation-calibration-implementation"
    / "issues"
)
QUALITY_GATES = PROJECT_ROOT / "docs" / "moltrack" / "QUALITY_GATES.md"
QUALITY_WORKFLOW = PROJECT_ROOT / ".github" / "workflows" / "moltrack-quality.yml"
PUBLIC_COMMAND = (
    "conda run -n netcat python scripts\\check_domain_analysis_issue_plan.py"
)


def test_issue_plan_accepts_only_consistent_canonical_statuses(
    tmp_path: Path,
) -> None:
    _write_issue(
        tmp_path,
        "01-pending.md",
        status="pending",
        checklist=("[x] finished slice", "[ ] remaining slice"),
    )
    _write_issue(
        tmp_path,
        "02-completed.md",
        status="completed",
        checklist=("[x] acceptance criterion",),
    )

    assert validate_issue_plan(tmp_path) == 2


def test_issue_plan_reports_both_files_with_a_duplicate_ticket_number(
    tmp_path: Path,
) -> None:
    _write_issue(
        tmp_path,
        "07-first.md",
        status="completed",
        checklist=("[x] accepted",),
    )
    _write_issue(
        tmp_path,
        "07-second.md",
        status="pending",
        checklist=("[ ] remaining",),
    )

    with pytest.raises(ValueError) as raised:
        validate_issue_plan(tmp_path)

    message = str(raised.value)
    assert "duplicate ticket number 07" in message
    assert "07-first.md" in message
    assert "07-second.md" in message


@pytest.mark.parametrize(
    ("name", "body", "rule"),
    (
        (
            "03-unknown.md",
            "# Ticket\n\n**Status:** done\n\n- [x] accepted\n",
            "unknown status 'done'",
        ),
        (
            "04-missing.md",
            "# Ticket\n\n- [ ] acceptance criterion\n",
            "must declare exactly one status",
        ),
        (
            "05-incomplete.md",
            "# Ticket\n\n**Status:** completed\n\n- [ ] remaining\n",
            "completed ticket has an unchecked acceptance criterion",
        ),
        (
            "06-transition.md",
            "# Ticket\n\n**Status:** pending\n\n- [x] accepted\n",
            "transition it to completed",
        ),
        (
            "07-empty-checklist.md",
            "# Ticket\n\n**Status:** completed\n",
            "must declare at least one acceptance criterion",
        ),
        (
            "08-star-checklist.md",
            "# Ticket\n\n**Status:** completed\n\n* [ ] remaining\n",
            "completed ticket has an unchecked acceptance criterion",
        ),
    ),
)
def test_issue_plan_error_names_the_file_and_violated_rule(
    tmp_path: Path,
    name: str,
    body: str,
    rule: str,
) -> None:
    path = tmp_path / name
    path.write_text(body, encoding="utf-8")

    with pytest.raises(ValueError) as raised:
        validate_issue_plan(tmp_path)

    message = str(raised.value)
    assert name in message
    assert rule in message


def test_repository_issue_plan_contains_41_valid_tickets() -> None:
    assert validate_issue_plan(ISSUES_DIR) == 41


def test_issue_plan_validator_is_the_same_local_and_ci_quality_gate() -> None:
    documentation = QUALITY_GATES.read_text(encoding="utf-8")
    workflow = QUALITY_WORKFLOW.read_text(encoding="utf-8")

    assert PUBLIC_COMMAND in documentation
    assert PUBLIC_COMMAND in workflow
    assert "scripts/check_domain_analysis_issue_plan.py" in workflow
    assert (
        ".scratch/manual-domain-orientation-calibration-implementation/issues/**"
        in workflow
    )


def _write_issue(
    issues_dir: Path,
    name: str,
    *,
    status: str,
    checklist: tuple[str, ...],
) -> None:
    criteria = "\n".join(f"- {value}" for value in checklist)
    (issues_dir / name).write_text(
        f"# Ticket\n\n**Status:** {status}\n\n{criteria}\n",
        encoding="utf-8",
    )
