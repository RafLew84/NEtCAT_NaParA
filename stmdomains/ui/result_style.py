"""Display rules for computed memberships, shared by image and legend."""

from colorsys import hsv_to_rgb
from collections import Counter
from dataclasses import dataclass

from stmdomains.core.analysis_result import FrameAnalysis
from stmdomains.analysis.geometry_domain_settings import METHOD
from stmdomains.analysis.freud_settings import METHOD as FREUD_METHOD

INPUT_COLOR = "#46e6be"
UNASSIGNED_COLOR = "#969696"
DOMAIN_COLORS = (
    "#5cb8ff", "#ff9a53", "#69d67a", "#e985db", "#f2d85c", "#bc91f5",
    "#4ed9d0", "#ff6e80", "#b8d855", "#f4ade3", "#8dc6ac", "#e6b585",
)


def domain_color(domain_id: int) -> str:
    """Domain identifiers and colours are local to one frame."""
    if domain_id <= 0:
        return UNASSIGNED_COLOR
    if domain_id <= len(DOMAIN_COLORS):
        return DOMAIN_COLORS[domain_id - 1]
    rgb = hsv_to_rgb((domain_id * 0.61803398875) % 1, 0.65, 0.95)
    return "#" + "".join(f"{round(channel * 255):02x}" for channel in rgb)


def assignment_color(result: FrameAnalysis | None, detection_id: str, mode: str) -> str:
    if mode not in ("domains", "classes", "input"):
        raise ValueError("Unknown assignment display mode")
    if result is None or mode == "input":
        return INPUT_COLOR
    assignment = result.assignments.get(detection_id)
    if (mode == 'classes' and result.status == 'complete' and assignment is not None
            and result.parameters.get('domain_method') == FREUD_METHOD):
        return next((item.color for item in result.classes if item.class_id == assignment.provisional_class_id),
                    UNASSIGNED_COLOR)
    if result.status != "complete" or assignment is None or assignment.status != "domain":
        return UNASSIGNED_COLOR
    if mode == "domains":
        return domain_color(assignment.domain_local_id)
    return next((item.color for item in result.classes if item.class_id == assignment.class_id),
                UNASSIGNED_COLOR)


def assignment_description(result: FrameAnalysis | None, detection_id: str) -> str:
    if result is None:
        return "Brak analizy tej klatki"
    assignment = result.assignments.get(detection_id)
    if assignment is not None and assignment.status == "suppressed_duplicate":
        return "Pominięty duplikat · poza mianownikiem analizy"
    if assignment is not None and assignment.status == "outside_field":
        return "Oznaczenie poza polem · poza mianownikiem analizy"
    if result.status != "complete":
        return result.message or "Nie wykonano dopasowania klas dla tej klatki"
    if assignment is None:
        return "Brak rekordu przypisania dla tego ID"
    if assignment.status == "domain":
        if result.parameters.get('domain_method') == METHOD:
            return f'Domena lokalna: {assignment.domain_local_id} · typ nieznany · zgodność fazy niesprawdzona'
        scope = "wspólna" if result.catalogue is not None and result.catalogue.scope != "current_frame" else "lokalna"
        description = f"Klasa {scope}: {assignment.class_id} · domena lokalna: {assignment.domain_local_id}"
        return description + (f" · katalog {result.catalogue.identifier[:8]}" if result.catalogue else "")
    reasons = {
        'freud_incomplete': 'za mało sąsiadów w dozwolonym zasięgu',
        'freud_edge': 'otoczenie ucięte przez brzeg pola',
        'freud_ambiguous_shell': 'remis odległości na granicy wyboru sąsiadów',
        'geometry_not_2d': 'brak dwóch stabilnych kierunków geometrii',
        'geometry_invalid': 'niepoprawny pomiar geometrii',
        'geometry_low_support': 'za mało punktów lokalnego pomiaru',
        'geometry_low_quality': 'koherencja poniżej ustawionego minimum',
        "insufficient_local_support": "niewystarczające otoczenie molekuły",
        "periodicity_not_confirmed": "niepotwierdzona periodyczność",
        "class_ambiguous": "niejednoznaczna klasa",
        "class_low_margin": "zbyt mała przewaga najlepszej klasy nad drugą",
        "class_outside_radius": "otoczenie poza promieniem klasy",
        "invalid_descriptor": "brak wystarczającego opisu otoczenia",
        "small_or_fragmented_component": "zbyt mała lub rozdrobniona składowa",
        "insufficient_training_samples": "za mało próbek do dopasowania klas",
        "no_scale": "nie można wyznaczyć skali otoczenia",
    }
    reason = reasons.get(assignment.rejection_reason, assignment.rejection_reason or "brak przyczyny")
    description = f"Nieprzypisana · {reason}"
    if assignment.provisional_class_id:
        description += (f' · klasa otoczenia: {assignment.provisional_class_id} (bez domeny)'
                        if result.parameters.get('domain_method') == FREUD_METHOD else
                        f" · etykieta wstępna: {assignment.provisional_class_id} (nie jest przypisaniem)")
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


def describe_result(result: FrameAnalysis | None, mode: str) -> ResultPresentation:
    if mode not in ("domains", "classes", "input"):
        raise ValueError("Unknown assignment display mode")
    if result is None:
        return ResultPresentation("Brak analizy tej klatki", (), "Kliknij Analizuj klatkę, aby obliczyć wynik.")
    if mode == "input":
        return ResultPresentation("Oznaczenia wejściowe", (
            LegendEntry("Oznaczenia", INPUT_COLOR, result.total_count),
        ), "Kolory wyniku wyłączone; molekuły pochodzą z zapisu wejściowego. " + result.message)
    if result.status == "no_annotations":
        return ResultPresentation("Brak oznaczeń do analizy", (), result.message or
                                  "Brak zapisanych oznaczeń nie dowodzi braku molekuł.")
    if result.status == "insufficient_data":
        entries = [LegendEntry("Bez dopasowania", UNASSIGNED_COLOR, result.active_count)]
        entries.extend(_excluded_entries(result))
        return ResultPresentation("Brak dopasowania klas", tuple(entries), result.message)
    if mode == 'classes' and result.parameters.get('domain_method') == METHOD:
        return ResultPresentation('Typ nieznany', (LegendEntry('Bez typu', UNASSIGNED_COLOR, result.active_count),),
                                  'Metoda geometryczna nie dopasowuje klas; wybierz widok Domeny.')
    if mode == 'classes' and result.parameters.get('domain_method') == FREUD_METHOD:
        environment_counts = Counter(m.provisional_class_id for m in result.assignments.values() if m.provisional_class_id)
        entries = [LegendEntry(f'Klasa {item.class_id}', item.color, environment_counts[item.class_id]) for item in result.classes]
        compared = sum(environment_counts.values())
        if result.active_count > compared:
            entries.append(LegendEntry('Nieporównane otoczenia', UNASSIGNED_COLOR, result.active_count-compared))
        entries.extend(_excluded_entries(result))
        return ResultPresentation(f'Klasy otoczeń: {len(environment_counts)} · porównano {compared}/{result.active_count}',
            tuple(entries), 'freud: podobieństwo otoczeń, nie typ struktury. Klasy lokalne dla wyniku. '
            'Obszary pokazują wyłącznie końcowe domeny. Kliknij molekułę, aby zobaczyć sąsiadów.')
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
        title = f"Klasy: {sum(count > 0 for count in counts_by_class.values())}"
        note = "Końcowe klasy lokalne dla klatki; wstępne etykiety nie są przypisaniami."
        if result.catalogue is not None and result.catalogue.scope != "current_frame":
            note = f"Końcowe klasy wspólnego katalogu {result.catalogue.identifier[:8]}; numery klas są porównywalne tylko w tym katalogu."
    if result.unassigned_count:
        entries.append(LegendEntry("Nieprzypisane", UNASSIGNED_COLOR, result.unassigned_count))
    entries.extend(_excluded_entries(result))
    note += " Mianownik: aktywne oznaczenia, bez duplikatów i punktów poza polem."
    return ResultPresentation(
        f"{title} · przypisano {result.assigned_count} / {result.active_count}", tuple(entries), note,
    )


def _excluded_entries(result: FrameAnalysis) -> list[LegendEntry]:
    return [LegendEntry(label, UNASSIGNED_COLOR, count)
            for label, count in (("Duplikaty", result.suppressed_count),
                                 ("Poza polem", result.outside_count)) if count]
