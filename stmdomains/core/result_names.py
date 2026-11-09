"""Presentation names; fitted class IDs and local domain IDs remain unchanged."""

from collections import Counter
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from stmdomains.core.analysis_result import FrameAnalysis


def class_letter(index: int) -> str:
    """Zero-based catalogue order: A … Z, AA … AZ, BA …"""
    if index < 0:
        raise ValueError('Class index must be nonnegative')
    name = ''
    number = index + 1
    while number:
        number, remainder = divmod(number - 1, 26)
        name = chr(ord('A') + remainder) + name
    return name


def class_names(result: 'FrameAnalysis') -> dict[str, str]:
    # Include absent classes: letters must not shift when a frame lacks a class.
    if result.class_list is not None:
        return {c.class_id: c.name for c in result.class_list.classes}
    return {c.class_id: class_letter(i) for i, c in enumerate(result.classes)}


def class_name(result: 'FrameAnalysis', class_id: str) -> str:
    return class_names(result).get(class_id, '?')


def domain_names(result: 'FrameAnalysis', mode: str = 'domains') -> dict[int, str]:
    """Number regions within their class, by local ID, independently per frame.

    Unknown/mixed classes have the explicit prefix '?'. Names do not imply
    tracking across frames; reassigning or deleting a region can change them.
    """
    if mode == 'input':
        return {}
    if mode not in ('classes', 'domains'):
        raise ValueError('Unknown assignment display mode')
    names = class_names(result)
    members: dict[int, set[str]] = {}
    for assignment in result.assignments.values():
        if assignment.domain_local_id > 0:
            members.setdefault(assignment.domain_local_id, set()).add(assignment.class_id)
    counts: Counter[str] = Counter()
    labels = {}
    for identity, classes in sorted(members.items()):
        class_id = next(iter(classes)) if len(classes) == 1 else ''
        name = names.get(class_id, '?')
        counts[class_id] += 1
        # Keep arbitrary manual names readable and separate a trailing digit.
        separator = '' if name == '?' or (name.isascii() and name.isalpha() and name.isupper()) else ' · '
        labels[identity] = name if mode == 'classes' else f'{name}{separator}{counts[class_id]}'
    return labels


def domain_name(result: 'FrameAnalysis', domain_id: int) -> str:
    return domain_names(result).get(domain_id, 'brak')
