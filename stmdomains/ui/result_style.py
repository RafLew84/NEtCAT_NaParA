"""Pure display rules for final molecule assignments, shared by image and legend."""

from colorsys import hsv_to_rgb
from collections import Counter
from dataclasses import dataclass

from stmdomains.core.domain_results import FrameResult

INPUT_COLOR = "#46e6be"
UNASSIGNED_COLOR = "#969696"
DOMAIN_COLORS = (
    "#5cb8ff", "#ff9a53", "#69d67a", "#e985db", "#f2d85c", "#bc91f5",
    "#4ed9d0", "#ff6e80", "#b8d855", "#f4ade3", "#8dc6ac", "#e6b585",
)


def domain_color(domain_id: int) -> str:
    """Domain IDs and their colours are local to the displayed frame."""
    if domain_id <= 0:
        return UNASSIGNED_COLOR
    if domain_id <= len(DOMAIN_COLORS):
        return DOMAIN_COLORS[domain_id - 1]
    rgb = hsv_to_rgb((domain_id * 0.61803398875) % 1, 0.65, 0.95)
    return "#" + "".join(f"{round(channel * 255):02x}" for channel in rgb)


def assignment_color(result: FrameResult | None, detection_id: str, mode: str) -> str:
    if mode not in ("domains", "classes", "input"):
        raise ValueError("Unknown assignment display mode")
    if result is None or mode == "input":
        return INPUT_COLOR
    assignment = result.assignments.get(detection_id)
    if not result.analyzed or assignment is None or assignment.status != "domain":
        return UNASSIGNED_COLOR
    if mode == "domains":
        return domain_color(assignment.domain_local_id)
    return next((item.color for item in result.classes if item.class_id == assignment.class_id),
                UNASSIGNED_COLOR)


def assignment_description(result: FrameResult | None, detection_id: str) -> str:
    if result is None:
        return "Brak dołączonego wyniku"
    if not result.analyzed:
        return "Brak analizy tej klatki"
    assignment = result.assignments.get(detection_id)
    if assignment is None:
        return "Brak rekordu przypisania dla tego ID"
    if assignment.status == "suppressed_duplicate":
        return "Pominięty duplikat · poza mianownikiem analizy"
    if assignment.status == "domain":
        return f"Klasa: {assignment.class_id} · domena lokalna: {assignment.domain_local_id}"
    reasons = {
        "insufficient_local_support": "niewystarczające otoczenie molekuły",
        "periodicity_not_confirmed": "niepotwierdzona periodyczność",
        "class_ambiguous": "niejednoznaczna klasa",
        "small_or_fragmented_component": "zbyt mała lub rozdrobniona składowa",
    }
    reason = reasons.get(assignment.rejection_reason, assignment.rejection_reason or "brak zapisanej przyczyny")
    description = f"Nieprzypisana · {reason}"
    if assignment.provisional_class_id:
        description += f" · etykieta wstępna: {assignment.provisional_class_id} (nie jest przypisaniem)"
    return description


@dataclass(frozen=True)
class LegendEntry:
    label: str
    color: str
    count: int


@dataclass(frozen=True)
class ResultPresentation:
    summary: str
    legend: tuple[LegendEntry, ...]
    note: str


def describe_result(result: FrameResult | None, mode: str) -> ResultPresentation:
    if mode not in ("domains", "classes", "input"):
        raise ValueError("Unknown assignment display mode")
    if result is None:
        return ResultPresentation("Brak dołączonego wyniku", (), "Otwórz wynik, aby zobaczyć przypisania molekuł.")
    if not result.analyzed:
        return ResultPresentation("Brak analizy tej klatki", (), "Brak wyniku nie oznacza zerowej liczby domen.")
    if mode == "input":
        return ResultPresentation(
            "Oznaczenia wejściowe · kolory wyniku wyłączone",
            (LegendEntry("Oznaczenia", INPUT_COLOR, result.total_count),),
            "Pokazano zapisane molekuły, bez kolorowania wyniku analizy.",
        )
    if mode == "domains":
        counts = Counter(item.domain_local_id for item in result.assignments.values()
                         if item.domain_local_id > 0)
        entries = [LegendEntry(f"Domena {identity}", domain_color(identity), count)
                   for identity, count in sorted(counts.items())]
        title = f"Domeny: {result.domain_count}"
        note = "Domeny lokalne dla klatki; kolory nie oznaczają śledzenia w czasie."
    else:
        counts_by_class = result.class_counts
        entries = [LegendEntry(f"Klasa {item.class_id}", item.color, counts_by_class[item.class_id])
                   for item in result.classes]
        title = f"Klasy w klatce: {sum(count > 0 for count in counts_by_class.values())}"
        note = "Końcowe klasy molekuł; wstępne etykiety nie są przypisaniami."
    unassigned = result.active_count - result.assigned_count
    if unassigned:
        entries.append(LegendEntry("Nieprzypisane", UNASSIGNED_COLOR, unassigned))
    if result.suppressed_count:
        entries.append(LegendEntry("Pominięte duplikaty", UNASSIGNED_COLOR, result.suppressed_count))
    return ResultPresentation(
        f"{title} · przypisano {result.assigned_count} / {result.active_count}"
        f" · pominięte duplikaty: {result.suppressed_count}", tuple(entries), note,
    )
