"""Read actual v0.4 export files and bind them to the loaded image series."""

import shutil
import json
import csv
import hashlib
import io
from zipfile import ZipFile
from dataclasses import replace

import numpy as np
import pytest

from stmdomains.io.moltrack_import import ImportCancelled, prepare_import
from stmdomains.io.v04_import import V04ImportError, load_v04_result

from stmdomains.tools.result_demo import create_result_demo, refresh_package, write_csv


def test_result_matches_ids_and_distinguishes_final_class_domain_and_absence(tmp_path):
    paths = create_result_demo(tmp_path)
    series = prepare_import(paths["session"]).series
    result = load_v04_result(paths["manifest"], series)
    assert result.series_id == series.identity
    assert result.frame_count == 2
    frame = result.frame(0)
    assert (frame.total_count, frame.active_count, frame.suppressed_count) == (5, 4, 1)
    assert (frame.assigned_count, frame.domain_count) == (3, 2)
    assert frame.class_counts == {"q": 3, "w": 0}
    assert frame.assignments["a"].domain_local_id == 1
    assert frame.assignments["c"].domain_local_id == 2
    assert frame.assignments["a"].class_id == frame.assignments["c"].class_id == "q"
    assert frame.assignments["d"].class_id == ""
    assert frame.assignments["d"].provisional_class_id == "w"
    assert frame.assignments["d"].rejection_reason == "class_ambiguous"
    assert frame.assignments["duplicate"].status == "suppressed_duplicate"
    assert not result.frame(1).analyzed
    assert result.frame(2).analyzed and result.frame(2).domain_count == 0


def test_zip_reads_only_data_without_extracting_or_loading_model(tmp_path):
    paths = create_result_demo(tmp_path / "input")
    root = paths["manifest"].parent
    (root / "unused-model.pkl").write_bytes(b"This is deliberately not a pickle model")
    refresh_package(paths)
    target = tmp_path / "zip-only"
    target.mkdir()
    archive = target / "package.zip"
    shutil.copyfile(paths["zip"], archive)
    series = prepare_import(paths["session"]).series
    result = load_v04_result(archive, series)
    assert result.frame(0).assigned_count == 3
    assert result.package_path == archive
    assert list(target.iterdir()) == [archive]
    assert load_v04_result(root, series).frame(0) == result.frame(0)


@pytest.mark.parametrize("source", ["mpp", "session"])
def test_result_rejects_a_different_source_identity(tmp_path, source):
    paths = create_result_demo(tmp_path)
    series = prepare_import(paths["session"]).series
    metadata_path = paths["manifest"].parent / "work/expanded/metadata.json"
    metadata = json.loads(metadata_path.read_text())
    metadata["sources"][source]["sha256"] = "0" * 64
    metadata_path.write_text(json.dumps(metadata))
    refresh_package(paths)
    with pytest.raises(V04ImportError, match="źród|sesj"):
        load_v04_result(paths["zip"], series)


def test_result_checks_images_already_loaded_in_memory(tmp_path):
    paths = create_result_demo(tmp_path)
    series = prepare_import(paths["session"]).series
    changed = series.raw_frames.copy()
    changed[0, 2, 2] += 1
    series = replace(series, raw_frames=changed)
    with pytest.raises(V04ImportError, match="obraz"):
        load_v04_result(paths["manifest"], series)


@pytest.mark.parametrize("fault", ["coordinate", "unknown_id", "duplicate_id", "missing_id"])
def test_result_requires_exact_annotation_ids_and_positions(tmp_path, fault):
    paths = create_result_demo(tmp_path)
    series = prepare_import(paths["session"]).series
    path = paths["manifest"].parent / "results_discovery/detections_with_domains.csv"
    with path.open() as stream:
        rows = list(csv.DictReader(stream))
    if fault == "coordinate":
        rows[0]["x_px"] = "5"
    elif fault == "unknown_id":
        rows[0]["detection_id"] = "unrelated"
    elif fault == "duplicate_id":
        rows[1]["detection_id"] = rows[0]["detection_id"]
    else:
        rows.pop()
    write_csv(path, rows)
    refresh_package(paths)
    with pytest.raises(V04ImportError):
        load_v04_result(paths["zip"], series)


@pytest.mark.parametrize("fault", ["metadata_map", "csv_local", "csv_number", "npz_float_indices"])
def test_result_requires_consistent_local_source_and_working_maps(tmp_path, fault):
    paths = create_result_demo(tmp_path)
    series = prepare_import(paths["session"]).series
    root = paths["manifest"].parent
    if fault == "metadata_map":
        path = root / "work/expanded/metadata.json"
        value = json.loads(path.read_text())
        value["source_frame_indices"] = [2, 0]
        path.write_text(json.dumps(value))
    elif fault.startswith("csv"):
        path = root / "results_discovery/detections_with_domains.csv"
        with path.open() as stream:
            rows = list(csv.DictReader(stream))
        rows[0]["local_frame_index" if fault == "csv_local" else "frame_number"] = "1" if fault == "csv_local" else "3"
        write_csv(path, rows)
    else:
        path = root / "work/expanded/input_selected.npz"
        with np.load(path) as arrays:
            images = arrays["images"]
        np.savez_compressed(path, images=images, source_frame_indices=np.array([0., 2.]))
    refresh_package(paths)
    with pytest.raises(V04ImportError):
        load_v04_result(paths["zip"], series)


@pytest.mark.parametrize("fault", ["changed", "missing", "version"])
def test_manifest_rejects_incomplete_or_altered_package(tmp_path, fault):
    paths = create_result_demo(tmp_path)
    series = prepare_import(paths["session"]).series
    if fault == "version":
        manifest = json.loads(paths["manifest"].read_text())
        manifest["prototype_version"] = "0.3"
        paths["manifest"].write_text(json.dumps(manifest))
    else:
        target = paths["manifest"].parent / "results_discovery/frame_summary.csv"
        if fault == "missing":
            target.unlink()
        else:
            target.write_text(target.read_text() + "\n")
    with pytest.raises(V04ImportError):
        load_v04_result(paths["manifest"], series)


@pytest.mark.parametrize("fault", ["status", "final_class", "reason", "negative_domain",
                                   "domain_count", "frame_count", "total_count"])
def test_result_refuses_contradictory_assignments_and_counts(tmp_path, fault):
    paths = create_result_demo(tmp_path)
    series = prepare_import(paths["session"]).series
    root = paths["manifest"].parent
    if fault == "total_count":
        path = root / "results_discovery/analysis_summary.json"
        summary = json.loads(path.read_text())
        summary["n_assigned"] = 4
        path.write_text(json.dumps(summary))
    else:
        filename = ("domains.csv" if fault == "domain_count" else
                    "frame_summary.csv" if fault == "frame_count" else "detections_with_domains.csv")
        path = root / "results_discovery" / filename
        with path.open() as stream:
            rows = list(csv.DictReader(stream))
        key, value = {"status": ("status", "uncertain_or_small"),
                      "final_class": ("class_id", "w"), "reason": ("unassigned_reason", "class_ambiguous"),
                      "negative_domain": ("domain_local_id", "-1"), "domain_count": ("n_molecules", "3"),
                      "frame_count": ("assigned_to_domains", "4")}[fault]
        rows[0][key] = value
        write_csv(path, rows)
    refresh_package(paths)
    with pytest.raises(V04ImportError):
        load_v04_result(paths["manifest"], series)


def test_result_requires_known_input_metadata_schema(tmp_path):
    paths = create_result_demo(tmp_path)
    series = prepare_import(paths["session"]).series
    path = paths["manifest"].parent / "work/expanded/metadata.json"
    value = json.loads(path.read_text())
    value["schema"] = "unrelated-input-schema"
    path.write_text(json.dumps(value))
    refresh_package(paths)
    with pytest.raises(V04ImportError, match="metadanych"):
        load_v04_result(paths["manifest"], series)


def test_result_uses_working_index_after_reordering_moltrack_series(tmp_path):
    paths = create_result_demo(tmp_path)
    payload = json.loads(paths["session"].read_text())
    payload["working_series"]["source_frame_indices"] = [2, 1, 0]
    for point in payload["molecular_detections"]["detections"]:
        point["frame_index"] = 2 - point["frame_index"]
    paths["session"].write_text(json.dumps(payload))
    metadata_path = paths["manifest"].parent / "work/expanded/metadata.json"
    metadata = json.loads(metadata_path.read_text())
    session = paths["session"].read_bytes()
    metadata["sources"]["session"].update(size_bytes=len(session), sha256=hashlib.sha256(session).hexdigest())
    metadata_path.write_text(json.dumps(metadata))
    refresh_package(paths)
    series = prepare_import(paths["session"]).series
    result = load_v04_result(paths["zip"], series)
    assert series.source_frame_indices == (2, 1, 0)
    assert result.frame(0).analyzed and result.frame(0).domain_count == 0
    assert not result.frame(1).analyzed
    assert result.frame(2).domain_count == 2
    assert result.frame(2).assignments["a"].class_id == "q"


def test_result_metadata_and_memberships_are_immutable(tmp_path):
    paths = create_result_demo(tmp_path)
    series = prepare_import(paths["session"]).series
    result = load_v04_result(paths["manifest"], series)
    with pytest.raises(TypeError):
        result.frames[0] = result.frame(1)
    with pytest.raises(TypeError):
        result.frame(0).assignments["a"] = result.frame(0).assignments["b"]
    with pytest.raises(TypeError):
        result.metadata["parameters"]["min_molecules_per_domain"] = 999
    with pytest.raises(TypeError):
        result.frame(0).assignments["a"].metadata["domain_local_id"] = "99"


def test_import_can_be_cancelled_while_validating_source(tmp_path):
    paths = create_result_demo(tmp_path)
    series = prepare_import(paths["session"]).series
    abort = False

    def progress(message):
        nonlocal abort
        if "tożsamości" in message:
            abort = True

    with pytest.raises(ImportCancelled):
        load_v04_result(paths["zip"], series, progress=progress, cancelled=lambda: abort)


def test_npz_geometry_is_rejected_from_header_before_allocating_images(tmp_path):
    paths = create_result_demo(tmp_path)
    series = prepare_import(paths["session"]).series
    header = io.BytesIO()
    np.lib.format.write_array_header_1_0(header, {"shape": (7, 16, 24),
                                                "fortran_order": False, "descr": "<f8"})
    indices = io.BytesIO()
    np.save(indices, np.array([0, 2], dtype=np.int32))
    with ZipFile(paths["manifest"].parent / "work/expanded/input_selected.npz", "w") as archive:
        archive.writestr("images.npy", header.getvalue())
        archive.writestr("source_frame_indices.npy", indices.getvalue())
    refresh_package(paths)
    with pytest.raises(V04ImportError, match="geometria|Geometria"):
        load_v04_result(paths["zip"], series)
