"""Check the saved final memberships against independent export summaries."""

import json
import re
from collections import Counter
from collections.abc import Mapping
from math import isclose, isfinite
from typing import Any

from stmdomains.core.domain_results import FrameResult, MoleculeAssignment, ResultClass
from stmdomains.io.v04_package import V04ImportError


def integer(value: object) -> int:
    if type(value) is int and value >= 0:
        return value
    if isinstance(value, str) and value.isascii() and value.isdecimal():
        return int(value)
    raise V04ImportError("Oczekiwano nieujemnej całkowitej liczby w wyniku.")


def boolean(value: object) -> bool:
    if type(value) is bool:
        return value
    if value in ("True", "False"):
        return value == "True"
    raise V04ImportError("Niepoprawna flaga logiczna w wyniku.")


def read_classes(summary: dict[str, Any], config: dict[str, Any]) -> tuple[ResultClass, ...]:
    if (summary.get("prototype_version") != "0.4-discovery"
            or config.get("prototype_version") != "0.4"
            or config.get("schema") != "stm-domain-prototype-run-v1"):
        raise V04ImportError("Nieobsługiwana wersja zapisanego wyniku lub konfiguracji.")
    classes = tuple(ResultClass(item["id"], item["color"]) for item in summary["classes"])
    if (not classes or len({item.class_id for item in classes}) != len(classes)
            or any(not isinstance(item.class_id, str) or not item.class_id.strip()
                   or not isinstance(item.color, str) or re.fullmatch(r"#[0-9a-fA-F]{6}", item.color) is None
                   for item in classes)
            or integer(summary["selected_k"]) != len(classes)
            or integer(config["selected_classes"]) != len(classes)):
        raise V04ImportError("Niespójny katalog klas zapisanego wyniku.")
    return classes


def read_assignment(row: dict[str, str], classes: tuple[ResultClass, ...]) -> MoleculeAssignment:
    known = {item.class_id for item in classes}
    domain = integer(row["domain_local_id"])
    final, provisional = row["class_id"], row["provisional_class_id"]
    status, reason = row["status"], row["unassigned_reason"]
    supported = boolean(row["order_supported"])
    sufficient = boolean(row["order_support_sufficient"])
    reliable = boolean(row["class_reliable"])
    if status == "suppressed_duplicate":
        valid = (domain == 0 and not final and not provisional and reason == "suppressed_duplicate"
                 and not supported and not sufficient and not reliable)
    elif domain:
        valid = (status == "domain" and final in known and provisional == final
                 and not reason and supported and sufficient and reliable)
    else:
        expected_reason = ("insufficient_local_support" if not sufficient else
                           "periodicity_not_confirmed" if not supported else
                           "class_ambiguous" if not reliable else "small_or_fragmented_component")
        valid = (status == "uncertain_or_small" and not final and provisional in known
                 and reason == expected_reason)
    if not valid:
        raise V04ImportError(f"Sprzeczne przypisanie klasy/domeny albo odmowa: {row['detection_id']}.")
    return MoleculeAssignment(row["detection_id"], domain, final, provisional, status, reason, row)


def validate_counts(
    frames: Mapping[int, FrameResult], sources: list[int], source_to_working: dict[int, int],
    metadata: dict[str, Any], summary: dict[str, Any],
    frame_rows: list[dict[str, str]], domain_rows: list[dict[str, str]],
) -> None:
    if summary["source_frame_numbers"] != [index + 1 for index in sources]:
        raise V04ImportError("Zakres podsumowania nie odpowiada zakresowi danych wejściowych wyniku.")
    for records in (summary["frame_summary"], frame_rows):
        _frame_counts(records, frames, sources, source_to_working)
    for records in (summary["domains"], domain_rows):
        _domain_counts(records, frames, sources, source_to_working)
    original = sum(frame.total_count for frame in frames.values())
    used = sum(frame.active_count for frame in frames.values())
    assigned = sum(frame.assigned_count for frame in frames.values())
    if (integer(summary["n_original_detections"]) != original
            or integer(metadata["n_detections"]) != original
            or integer(summary["n_unique_used"]) != used
            or integer(summary["n_assigned"]) != assigned):
        raise V04ImportError("Globalne liczniki nie odpowiadają zapisanym przypisaniom molekuł.")
    _fraction(summary["assigned_fraction"], assigned, used)
    details = metadata["frame_details"]
    if not isinstance(details, list) or len(details) != len(sources):
        raise V04ImportError("Niespójna lista klatek w metadanych wejścia wyniku.")
    seen = set()
    for record in details:
        local = integer(record["local_frame_index"])
        if (local >= len(sources) or local in seen
                or integer(record["source_frame_index"]) != sources[local]
                or integer(record["frame_number"]) != sources[local] + 1
                or integer(record["detection_count"]) != frames[source_to_working[sources[local]]].total_count):
            raise V04ImportError("Niespójna klatka w metadanych wejścia wyniku.")
        seen.add(local)


def _record_source(record: Mapping[str, Any], sources: list[int]) -> int:
    local, source = integer(record["local_frame_index"]), integer(record["frame_index"])
    if local >= len(sources) or sources[local] != source or integer(record["frame_number"]) != source + 1:
        raise V04ImportError("Niespójny indeks klatki w tabeli wyniku.")
    return source


def _frame_counts(
    rows: list[dict[str, Any]], frames: Mapping[int, FrameResult], sources: list[int],
    source_to_working: dict[int, int],
) -> None:
    seen = set()
    for record in rows:
        source = _record_source(record, sources)
        if source in seen:
            raise V04ImportError("Powtórzona klatka w podsumowaniu wyniku.")
        seen.add(source)
        frame = frames[source_to_working[source]]
        expected = {"detections_original": frame.total_count, "molecules_used": frame.active_count,
                    "assigned_to_domains": frame.assigned_count, "total_domains": frame.domain_count,
                    "uncertain_or_small": frame.active_count - frame.assigned_count,
                    "order_supported": sum(boolean(item.metadata["order_supported"])
                                           for item in frame.assignments.values()),
                    "class_gate_accepted": sum(boolean(item.metadata["order_supported"])
                                               and boolean(item.metadata["class_reliable"])
                                               for item in frame.assignments.values())}
        if any(integer(record[key]) != value for key, value in expected.items()):
            raise V04ImportError(f"Liczniki klatki źródłowej {source + 1} nie odpowiadają przypisaniom.")
        _fraction(record["assigned_fraction"], frame.assigned_count, frame.active_count)
        by_domain = {item.domain_local_id: item.class_id for item in frame.assignments.values()
                     if item.domain_local_id > 0}
        expected_classes = Counter(by_domain.values())
        counts = record["class_counts"]
        if isinstance(counts, str):
            counts = json.loads(counts)
        if (not isinstance(counts, dict) or counts.keys() != {item.class_id for item in frame.classes}
                or any(integer(value) != expected_classes[key] for key, value in counts.items())):
            raise V04ImportError("Liczby domen klas w podsumowaniu są sprzeczne z przypisaniami.")
    if seen != set(sources):
        raise V04ImportError("Podsumowanie nie obejmuje wszystkich analizowanych klatek.")


def _domain_counts(
    rows: list[dict[str, Any]], frames: Mapping[int, FrameResult], sources: list[int],
    source_to_working: dict[int, int],
) -> None:
    expected: dict[tuple[int, int], tuple[str, int]] = {}
    for source in sources:
        frame = frames[source_to_working[source]]
        for item in frame.assignments.values():
            if item.domain_local_id > 0:
                key = (source, item.domain_local_id)
                clazz, count = expected.get(key, (item.class_id, 0))
                if clazz != item.class_id:
                    raise V04ImportError("Jedna końcowa domena zawiera sprzeczne klasy molekuł.")
                expected[key] = (clazz, count + 1)
    seen = set()
    display_ids = set()
    for record in rows:
        source = _record_source(record, sources)
        identifier = integer(record["domain_local_id"])
        key = (source, identifier)
        display = (source, record["display_id"])
        classes = frames[source_to_working[source]].classes
        class_index = integer(record["class_index"])
        if (key in seen or key not in expected or class_index >= len(classes)
                or classes[class_index].class_id != record["class_id"]
                or (record["class_id"], integer(record["n_molecules"])) != expected[key]
                or not isinstance(record["display_id"], str) or not record["display_id"]
                or display in display_ids):
            raise V04ImportError("Tabela domen nie odpowiada końcowym przypisaniom molekuł.")
        seen.add(key)
        display_ids.add(display)
    if seen != expected.keys():
        raise V04ImportError("Tabela domen jest niepełna.")


def _fraction(value: object, assigned: int, active: int) -> None:
    if not isinstance(value, (str, int, float)) or isinstance(value, bool):
        raise V04ImportError("Niepoprawny udział przypisań.")
    number = float(value)
    if not isfinite(number) or not isclose(number, assigned / active if active else 0., abs_tol=1e-12):
        raise V04ImportError("Udział przypisań nie odpowiada licznikom molekuł.")
