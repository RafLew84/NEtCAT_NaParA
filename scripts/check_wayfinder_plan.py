"""Validate a local Markdown Wayfinder plan without third-party dependencies."""

from __future__ import annotations

import argparse
from collections import Counter, deque
from dataclasses import dataclass
from html import unescape
import os
from pathlib import Path
import re
import sys
from urllib.parse import unquote, urlsplit


TICKET_STATUSES = {"open", "claimed", "resolved"}
MAP_STATUSES = {"open", "resolved"}
NUMBER = re.compile(r"[0-9]{2,}")
TICKET_NAME = re.compile(r"([0-9]{2,})-[^\s/\\]+\.md")
HEADING = re.compile(r"^ {0,3}(#{1,6})[ \t]+(.+?)[ \t]*#*[ \t]*$", re.MULTILINE)
REFERENCE = re.compile(r"^ {0,3}\[([^\]\n]+)\]:[ \t]*(<[^>\n]*>|\S+)(?:[^\n]*)$", re.MULTILINE)


class PlanError(ValueError):
    def __init__(self, path: Path, message: str):
        super().__init__(f"{path}: {message}")


def _blank(match: re.Match) -> str:
    return re.sub(r"[^\n]", " ", match.group())


def _without_comments(text: str) -> str:
    return re.sub(r"<!--.*?(?:-->|\Z)", _blank, text, flags=re.DOTALL)


def _without_code(text: str) -> str:
    """Keep line positions while ignoring examples in fences and code spans."""
    lines = []
    fence = None
    for line in _without_comments(text).splitlines(keepends=True):
        marker = re.match(r"^ {0,3}(`{3,}|~{3,})(.*)$", line.rstrip("\r\n"))
        if fence:
            lines.append(re.sub(r"[^\n]", " ", line))
            if marker and marker[1][0] == fence[0] and len(marker[1]) >= len(fence) and not marker[2].strip():
                fence = None
        elif marker:
            fence = marker[1]
            lines.append(re.sub(r"[^\n]", " ", line))
        else:
            lines.append(line)
    return re.sub(r"(`+)(.*?)\1", _blank, "".join(lines), flags=re.DOTALL)


def _reference_key(label: str) -> str:
    return " ".join(label.split()).casefold()


@dataclass(frozen=True)
class Document:
    path: Path
    text: str

    @classmethod
    def read(cls, path: Path) -> Document:
        try:
            return cls(path, path.read_text(encoding="utf-8-sig"))
        except (OSError, UnicodeError) as error:
            raise PlanError(path, f"cannot read UTF-8 Markdown ({error})") from error

    def field(self, name: str) -> str:
        visible = _without_code(self.text)
        body = re.search(r"^ {0,3}##[ \t]", visible, re.MULTILINE)
        header = visible[:body.start()] if body else visible
        values = re.findall(rf"^{re.escape(name)}:[ \t]*(.*)$", header, re.MULTILINE)
        if len(values) != 1 or not values[0].strip():
            raise PlanError(self.path, f"expected exactly one nonempty {name}: field before the sections")
        return values[0].strip()

    def status(self, allowed: set[str]) -> str:
        value = self.field("Status")
        if value not in allowed:
            raise PlanError(self.path, f"invalid Status {value!r}; expected {', '.join(sorted(allowed))}")
        return value

    def sections(self, title: str) -> list[str]:
        headings = list(HEADING.finditer(_without_code(self.text)))
        sections = []
        for i, heading in enumerate(headings):
            if heading[1] != "##" or heading[2] != title:
                continue
            end = next((h.start() for h in headings[i + 1:] if len(h[1]) <= 2), len(self.text))
            sections.append(self.text[heading.end():end])
        return sections

    def section(self, title: str) -> str:
        sections = self.sections(title)
        if len(sections) != 1:
            raise PlanError(self.path, f"expected exactly one ## {title} section")
        return sections[0]

    def links(self, text: str | None = None) -> list[str]:
        visible = _without_code(self.text)
        definitions = {
            _reference_key(match[1]): match[2].removeprefix("<").removesuffix(">")
            for match in REFERENCE.finditer(visible)
        }
        source = visible if text is None else _without_code(text)
        # Definitions themselves are checked, including unused ones.
        destinations = (
            [m[2].removeprefix("<").removesuffix(">") for m in REFERENCE.finditer(source)]
            if text is None else []
        )
        source = REFERENCE.sub(_blank, source)
        pattern = re.compile(r"(?<!\\)\[|<(?i:file):[^>\n]+>")
        pos = 0
        while match := pattern.search(source, pos):
            pos = match.end()
            if match[0].startswith("<"):
                destinations.append(match[0][1:-1])
                continue
            end, depth = pos, 1
            while end < len(source) and depth:
                if source[end] == "\\":
                    end += 2
                    continue
                if source[end] == "[":
                    depth += 1
                elif source[end] == "]":
                    depth -= 1
                if depth:
                    end += 1
            if depth:
                continue
            label = source[pos:end]
            if "[" in label:
                destinations.extend(self.links(label))
            pos = end + 1
            if source[pos:pos + 1] == "(":
                destination, pos = _inline_destination(source, pos + 1, self.path)
                destinations.append(destination)
            elif source[pos:pos + 1] == "[":
                end = source.find("]", pos + 1)
                if end == -1:
                    raise PlanError(self.path, "unclosed Markdown reference link")
                key = _reference_key(source[pos + 1:end] or label)
                if key not in definitions:
                    raise PlanError(self.path, f"undefined link reference [{key}]")
                destinations.append(definitions[key])
                pos = end + 1
            elif _reference_key(label) in definitions:
                destinations.append(definitions[_reference_key(label)])
        return destinations


def _inline_destination(source: str, start: int, path: Path) -> tuple[str, int]:
    """Read a destination with balanced parentheses, then an optional title."""
    start += len(source[start:]) - len(source[start:].lstrip())
    if source[start:start + 1] == "<":
        end = source.find(">", start + 1)
        if end == -1:
            raise PlanError(path, "unclosed <...> link destination")
        destination = source[start + 1:end]
        pos = end + 1
    else:
        pos, depth = start, 0
        while pos < len(source):
            char = source[pos]
            if char == "\\" and pos + 1 < len(source) and source[pos + 1] in "()":
                pos += 2
                continue
            if depth == 0 and (char.isspace() or char == ")"):
                break
            if char == "(":
                depth += 1
            elif char == ")":
                depth -= 1
            pos += 1
        destination = source[start:pos]
    pos += len(source[pos:]) - len(source[pos:].lstrip())
    if source[pos:pos + 1] in ('"', "'", "("):
        closing = ")" if source[pos] == "(" else source[pos]
        pos += 1
        while pos < len(source) and source[pos] != closing:
            pos += 2 if source[pos] == "\\" else 1
        pos += 1
        pos += len(source[pos:]) - len(source[pos:].lstrip())
    if source[pos:pos + 1] != ")":
        raise PlanError(path, "malformed Markdown link; wrap paths with spaces in <...>")
    return destination, pos + 1


def local_target(source: Path, destination: str) -> Path | None:
    """Resolve local paths only; remote URLs are never requested."""
    value = unescape(re.sub(r"\\([()\[\] <>#])", r"\1", destination)).strip()
    if not value or value.startswith("#"):
        return source
    if "://" not in value:
        value = re.sub(r":\d+(?::\d+)?(?=[?#]|$)", "", value)
    windows_path = re.match(r"^/?[A-Za-z]:[/\\]", value)
    if not windows_path and not value.startswith("\\\\"):
        try:
            parts = urlsplit(value)
        except ValueError as error:
            raise PlanError(source, f"invalid link destination: {destination}") from error
        if parts.scheme and parts.scheme.lower() != "file":
            return None
        if value.startswith("//") and not parts.scheme:
            return None
        if parts.scheme.lower() == "file":
            value = (f"//{parts.netloc}" if parts.netloc and parts.netloc != "localhost" else "") + parts.path
        else:
            value = parts.path
    else:
        value = re.split(r"[?#]", value, maxsplit=1)[0]
    value = unquote(value).replace("\\", "/")
    value = re.sub(r":\d+(?::\d+)?$", "", value)  # editor file:line[:column] links
    if re.match(r"^/[A-Za-z]:/", value):
        value = value[1:]
    if os.name != "nt" and re.match(r"^[A-Za-z]:/", value):
        raise PlanError(source, f"Windows path cannot be checked on this platform: {destination}")
    target = Path(value)
    return (target if target.is_absolute() else source.parent / target).resolve()


@dataclass(frozen=True)
class Ticket:
    document: Document
    number: int
    status: str
    dependencies: tuple[int, ...]


def _number(value: str, path: Path) -> int:
    if not NUMBER.fullmatch(value) or int(value) < 1 or f"{int(value):02d}" != value:
        raise PlanError(path, f"invalid ticket number {value!r}; use 01, 02, ...")
    return int(value)


def _ticket(document: Document, number: int) -> Ticket:
    status = document.status(TICKET_STATUSES)
    blocked = document.field("Blocked by")
    dependencies = () if blocked == "none" else tuple(_number(n.strip(), document.path) for n in blocked.split(","))
    if len(set(dependencies)) != len(dependencies):
        raise PlanError(document.path, "duplicate Blocked by dependency")
    if status == "resolved":
        answer = _without_comments(document.section("Answer"))
        answer = re.sub(r"(?m)^\s*(?:#{1,6}[ \t].*|`{3,}.*|~{3,}.*|[-*_]{3,})$", "", answer)
        if not answer.strip():
            raise PlanError(document.path, "resolved ticket has an empty ## Answer section")
    return Ticket(document, number, status, dependencies)


def _check_dependencies(tickets: dict[int, Ticket]) -> None:
    for ticket in tickets.values():
        for dependency in ticket.dependencies:
            if dependency not in tickets:
                raise PlanError(ticket.document.path, f"unknown Blocked by ticket {dependency:02d}")
    # Iterative DFS avoids recursion limits for long plans and shows the cycle.
    done = set()
    for number in tickets:
        stack = [(number, False)]
        active: list[int] = []
        while stack:
            current, leaving = stack.pop()
            if leaving:
                active.pop()
                done.add(current)
            elif current in active:
                cycle = active[active.index(current):] + [current]
                raise PlanError(tickets[current].document.path, "dependency cycle: " + " -> ".join(f"{n:02d}" for n in cycle))
            elif current not in done:
                active.append(current)
                stack.append((current, True))
                stack.extend((dep, False) for dep in reversed(tickets[current].dependencies))
    for ticket in tickets.values():
        if ticket.status == "resolved":
            unresolved = [n for n in ticket.dependencies if tickets[n].status != "resolved"]
            if unresolved:
                raise PlanError(ticket.document.path, f"resolved ticket depends on unresolved ticket {unresolved[0]:02d}")


def validate_plan(plan_dir: Path) -> int:
    """Return the number of tickets, or raise PlanError with the first defect."""
    root = plan_dir.resolve()
    mapping = Document.read(root / "map.md")
    map_status = mapping.status(MAP_STATUSES)
    paths = sorted((root / "issues").glob("*.md"))
    if not paths:
        raise PlanError(root / "issues", "no Markdown tickets found")
    tickets: dict[int, Ticket] = {}
    for path in paths:
        match = TICKET_NAME.fullmatch(path.name)
        if match is None:
            raise PlanError(path, "expected ticket filename NN-slug.md")
        number = _number(match[1], path)
        if number in tickets:
            raise PlanError(path, f"duplicate ticket number {number:02d} (also {tickets[number].document.path.name})")
        tickets[number] = _ticket(Document.read(path), number)
    _check_dependencies(tickets)

    by_path = {ticket.document.path.resolve(): ticket for ticket in tickets.values()}
    indexed: set[int] = set()
    for section in ("Decisions so far", "Out of scope"):
        body = mapping.section(section)
        targets = [local_target(mapping.path, link) for link in mapping.links(body)]
        counts = Counter(target for target in targets if target in by_path)
        for target, count in counts.items():
            ticket = by_path[target]
            if ticket.status != "resolved":
                raise PlanError(mapping.path, f"{section} indexes {ticket.status} ticket {ticket.document.path.name}")
            if count > 1:
                raise PlanError(mapping.path, f"duplicate {section} entry for {ticket.document.path.name}")
            indexed.add(ticket.number)
    for ticket in tickets.values():
        if ticket.status == "resolved" and ticket.number not in indexed:
            raise PlanError(mapping.path, f"resolved ticket missing from map index: {ticket.document.path.name}")
        if map_status == "resolved" and ticket.status != "resolved":
            raise PlanError(mapping.path, f"resolved map contains {ticket.status} ticket {ticket.document.path.name}")

    # Follow linked Markdown inside this plan, not unrelated worktrees/vendor docs.
    queue = deque([mapping, *(ticket.document for ticket in tickets.values())])
    if (root / "spec.md").is_file():
        queue.append(Document.read(root / "spec.md"))
    visited: set[Path] = set()
    while queue:
        document = queue.popleft()
        if document.path in visited:
            continue
        visited.add(document.path)
        for link in document.links():
            target = local_target(document.path, link)
            if target is None:
                continue
            if not target.exists():
                raise PlanError(document.path, f"local link target does not exist: {link}")
            if target.suffix.lower() == ".md" and target.is_file() and target.is_relative_to(root) and target not in visited:
                queue.append(Document.read(target))
    return len(tickets)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("plan_dir", type=Path, help="Directory containing map.md and issues/NN-slug.md")
    args = parser.parse_args(argv)
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="backslashreplace")
    try:
        count = validate_plan(args.plan_dir)
    except (PlanError, OSError, ValueError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 1
    print(f"OK: {args.plan_dir}: {count} tickets")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
