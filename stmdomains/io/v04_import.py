"""Read saved v0.4 molecule memberships without executing the prototype."""

from collections.abc import Callable
from pathlib import Path
from zipfile import BadZipFile

from stmdomains.core.domain_results import DomainResult, FrameResult, MoleculeAssignment
from stmdomains.core.series import Series
from stmdomains.io.moltrack_import import ImportCancelled
from stmdomains.io.v04_package import ResultPackage, V04ImportError
from stmdomains.io.v04_source import validate_annotations, validate_images, validate_sources
from stmdomains.io.v04_records import read_assignment, read_classes, validate_counts


def load_v04_result(
    path: Path, series: Series, *, cancelled: Callable[[], bool] = lambda: False,
    progress: Callable[[str], None] = lambda text: None,
) -> DomainResult:
    """Validate a saved result against the exact sources, images and annotations."""
    try:
        return _load(path, series, cancelled, progress)
    except (V04ImportError, ImportCancelled):
        raise
    except (OSError, ValueError, TypeError, KeyError, IndexError, BadZipFile, RuntimeError) as exc:
        raise V04ImportError(f"Niepoprawna lub niepełna paczka wyniku: {exc}") from exc


def _load(
    path: Path, series: Series, cancelled: Callable[[], bool], progress: Callable[[str], None],
) -> DomainResult:
    if cancelled():
        raise ImportCancelled()
    with ResultPackage(path, cancelled=cancelled, image_limit=series.raw_frames.nbytes + 64 * 1024**2) as package:
        progress("Sprawdzanie kompletności paczki wyniku…")
        package.verify_manifest()
        metadata = package.json("work/expanded/metadata.json")
        progress("Sprawdzanie tożsamości plików źródłowych…")
        validate_sources(metadata, series, cancelled)
        progress("Sprawdzanie obrazów wczytanej serii…")
        source_to_working = validate_images(package, metadata, series, cancelled)
        summary = package.json("results_discovery/analysis_summary.json")
        config = package.json("analysis_config.json")
        rows = package.csv("results_discovery/detections_with_domains.csv")
        frame_rows = package.csv("results_discovery/frame_summary.csv")
        domain_rows = package.csv("results_discovery/domains.csv")
    progress("Sprawdzanie ID i współrzędnych molekuł…")
    validate_annotations(rows, metadata["source_frame_indices"], series, source_to_working, cancelled)
    classes = read_classes(summary, config)
    members: dict[int, dict[str, MoleculeAssignment]] = {
        source_to_working[number-1]: {} for number in summary["source_frame_numbers"]
    }
    for row in rows:
        index = source_to_working[int(row["frame_index"])]
        identifier = row["detection_id"]
        members[index][identifier] = read_assignment(row, classes)
    frames = {
        index: FrameResult(True, assignments, classes) for index, assignments in members.items()
    }
    validate_counts(frames, metadata["source_frame_indices"], source_to_working,
                    metadata, summary, frame_rows, domain_rows)
    return DomainResult(series.identity, path, frames, classes,
                        dict(summary, input_metadata=metadata, run_config=config))
