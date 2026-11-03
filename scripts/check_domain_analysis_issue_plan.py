from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class TicketStatusRule:
    requires_complete_checklist: bool
    allowed_next_statuses: tuple[str, ...]


TICKET_STATUS_RULES = {
    "pending": TicketStatusRule(
        requires_complete_checklist=False,
        allowed_next_statuses=("completed",),
    ),
    "completed": TicketStatusRule(
        requires_complete_checklist=True,
        allowed_next_statuses=(),
    ),
}

_STATUS_PATTERN = re.compile(r"^\*\*Status:\*\*\s+(\S+)\s*$", re.MULTILINE)
_CHECKLIST_PATTERN = re.compile(
    r"^[ \t]*[-*+][ \t]+\[([ xX])\][ \t]+\S",
    re.MULTILINE,
)
_TICKET_NUMBER_PATTERN = re.compile(r"^(\d+)-")


def validate_issue_plan(issues_dir: Path) -> int:
    """Validate canonical statuses for every Markdown ticket in a plan."""

    paths = tuple(sorted(issues_dir.glob("*.md")))
    if not paths:
        raise ValueError(f"{issues_dir}: issues directory contains no Markdown tickets.")
    _validate_unique_numbers(paths)
    for path in paths:
        _validate_status(path)
    return len(paths)


def _validate_unique_numbers(paths: tuple[Path, ...]) -> None:
    paths_by_number: dict[int, list[Path]] = {}
    for path in paths:
        match = _TICKET_NUMBER_PATTERN.match(path.name)
        if match is None:
            raise ValueError(
                f"{path}: ticket filename must start with a numeric ticket number."
            )
        paths_by_number.setdefault(int(match.group(1)), []).append(path)
    for number, matching_paths in paths_by_number.items():
        if len(matching_paths) > 1:
            names = ", ".join(path.name for path in matching_paths)
            raise ValueError(
                f"{matching_paths[0]}: duplicate ticket number {number:02d}: {names}."
            )


def _validate_status(path: Path) -> None:
    text = path.read_text(encoding="utf-8")
    statuses = _STATUS_PATTERN.findall(text)
    if len(statuses) != 1:
        raise ValueError(f"{path}: ticket must declare exactly one status.")
    status = statuses[0]
    rule = TICKET_STATUS_RULES.get(status)
    if rule is None:
        expected = ", ".join(TICKET_STATUS_RULES)
        raise ValueError(
            f"{path}: unknown status {status!r}; expected one of: {expected}."
        )
    checklist = _CHECKLIST_PATTERN.findall(text)
    if not checklist:
        raise ValueError(
            f"{path}: ticket must declare at least one acceptance criterion."
        )
    if rule.requires_complete_checklist and any(mark == " " for mark in checklist):
        raise ValueError(
            f"{path}: completed ticket has an unchecked acceptance criterion."
        )
    if not rule.requires_complete_checklist and all(
        mark.lower() == "x" for mark in checklist
    ):
        next_status = ", ".join(rule.allowed_next_statuses)
        raise ValueError(
            f"{path}: pending ticket has a completed checklist; transition it to "
            f"{next_status}."
        )


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    issues_dir = (
        root
        / ".scratch"
        / "manual-domain-orientation-calibration-implementation"
        / "issues"
    )
    count = validate_issue_plan(issues_dir)
    print(f"Domain Analysis issue plan passed: {count} tickets.")


if __name__ == "__main__":
    main()
