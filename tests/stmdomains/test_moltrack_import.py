"""Public import/model contract, using real small MPP files."""

import json
import os
from pathlib import Path
from threading import Event

import numpy as np
import pytest

from stmdomains.io.moltrack_import import (
    ImportCancelled, ImportCandidate, MolTrackImportError, SourceRequest, prepare_import,
)
from stmdomains.tools.demo_inputs import create_demo_inputs, write_mpp, write_session


def test_import_preserves_source_map_and_normalized_orientation(tmp_path: Path) -> None:
    frames = np.array([
        [[1, 2, 3], [4, 5, 6]],
        [[11, 12, 13], [14, 15, 16]],
        [[21, 22, 23], [24, 25, 26]],
    ], dtype=float)
    source = write_mpp(tmp_path / "movie.mpp", frames)
    session = write_session(tmp_path / "movie.json", source, [2, 0], reverse=True)

    result = prepare_import(session)

    assert isinstance(result, ImportCandidate)
    assert result.confirmation_reasons == ()
    assert result.series.source_frame_indices == (2, 0)
    assert result.series.frame_count == 2
    assert result.series.frame_shape == (2, 3)
    assert result.series.frame(0).source_index == 2
    np.testing.assert_array_equal(result.series.frame(0).image, [[26, 25, 24], [23, 22, 21]])
    np.testing.assert_array_equal(result.series.frame(1).image, [[6, 5, 4], [3, 2, 1]])


@pytest.mark.parametrize("change", [
    {"schema_version": 4}, {"schema_version": True}, {"schema_version": "1"},
    {"source": []}, {"working_series": None},
    {"working_series": {"source_frame_indices": []}},
    {"working_series": {"source_frame_indices": [0, 0]}},
    {"working_series": {"source_frame_indices": [True]}},
    {"working_series": {"source_frame_indices": [-1]}},
    {"working_series": {"source_frame_indices": [0.0]}},
])
def test_malformed_required_session_data_has_a_public_error(tmp_path: Path, change: dict) -> None:
    source = write_mpp(tmp_path / "movie.mpp", [[[1, 2]]])
    session = write_session(tmp_path / "movie.json", source, [0])
    payload = json.loads(session.read_text())
    payload.update(change)
    session.write_text(json.dumps(payload))

    with pytest.raises(MolTrackImportError):
        prepare_import(session)


def test_relocated_source_search_skips_incompatible_file_and_supports_windows_name(tmp_path: Path) -> None:
    source = write_mpp(tmp_path / "good.mpp", [[[1, 2], [3, 4]]])
    bad = tmp_path / "bad.mpp"
    bad.write_text("not an MPP")
    session = write_session(tmp_path / "movie.json", source, [0])
    payload = json.loads(session.read_text())
    payload["source"]["path"] = str(bad)
    session.write_text(json.dumps(payload))
    result = prepare_import(session)
    assert isinstance(result, ImportCandidate)
    assert result.series.source_path == source

    payload["source"]["path"] = r"C:\measurements\good.mpp"
    payload["source"].pop("path_relative_to_session")
    session.write_text(json.dumps(payload))
    assert isinstance(prepare_import(session), ImportCandidate)


def test_manual_source_with_changed_mtime_requires_confirmation_without_modifying_input(tmp_path: Path) -> None:
    source = write_mpp(tmp_path / "good.mpp", [[[1, 2]]])
    session = write_session(tmp_path / "movie.json", source, [0])
    source.rename(tmp_path / "relocated.mpp")
    relocated = tmp_path / "relocated.mpp"
    before = session.read_bytes()
    saved_stat = relocated.stat()
    os.utime(relocated, ns=(saved_stat.st_atime_ns, saved_stat.st_mtime_ns + 10_000_000))
    assert isinstance(prepare_import(session), SourceRequest)

    result = prepare_import(session, relocated)

    assert isinstance(result, ImportCandidate)
    assert result.series.source_path == relocated
    assert any("modyfikacji" in reason for reason in result.confirmation_reasons)
    assert session.read_bytes() == before
    assert relocated.stat().st_mtime_ns == saved_stat.st_mtime_ns + 10_000_000


@pytest.mark.parametrize("change", ["size", "missing_frame", "shape"])
def test_incompatible_source_is_not_an_import_candidate(tmp_path: Path, change: str) -> None:
    source = write_mpp(tmp_path / "good.mpp", [[[1, 2]]])
    session = write_session(tmp_path / "movie.json", source, [0])
    payload = json.loads(session.read_text())
    if change == "size":
        payload["source"]["size_bytes"] += 1
    elif change == "missing_frame":
        payload["working_series"]["source_frame_indices"] = [1]
    else:
        payload["source"]["frame_shape_hw"] = [2, 1]
    session.write_text(json.dumps(payload))
    result = prepare_import(session)
    assert isinstance(result, SourceRequest)
    assert result.message


@pytest.mark.parametrize("version", [1, 2, 3])
def test_supported_schema_preserves_annotations_without_decoding_them(tmp_path: Path, version: int) -> None:
    source = write_mpp(tmp_path / "movie.mpp", [[[1, 2]], [[3, 4]]])
    session = write_session(tmp_path / "movie.json", source, [1], schema_version=version)
    payload = json.loads(session.read_text())
    payload["working_series"].pop("active_frame_index")
    payload["source"].pop("size_bytes")
    payload["source"].pop("mtime_ns")
    payload["molecular_segmentations"] = {"segmentations": [{"mask": "invalid optional mask"}]}
    session.write_text(json.dumps(payload))

    result = prepare_import(session)

    assert isinstance(result, ImportCandidate)
    assert result.series.active_frame_index == 0
    assert result.series.frame_count == 1
    assert result.series.frame(0).time_s is None
    assert result.series.raw_payload["molecular_segmentations"] == payload["molecular_segmentations"]
    assert any("weryfikacja" in reason for reason in result.series.diagnostics)
    assert any("aktywnej klatki" in reason for reason in result.series.diagnostics)
    assert not result.series.frame(0).image.flags.writeable
    with pytest.raises(IndexError):
        result.series.frame(-1)


def test_times_use_source_mapping_and_all_zero_times_stay_unknown(tmp_path: Path) -> None:
    frames = [[[1, 2]], [[3, 4]], [[5, 6]]]
    source = write_mpp(tmp_path / "movie.mpp", frames, times=[10.0, 20.0, 30.0])
    session = write_session(tmp_path / "movie.json", source, [2, 0])
    result = prepare_import(session)
    assert isinstance(result, ImportCandidate)
    assert result.series.frame(0).time_s == 30.0
    assert result.series.frame(1).time_s == 10.0

    write_mpp(source, frames, times=[0.0, 0.0, 0.0])
    write_session(session, source, [2, 0])
    result = prepare_import(session)
    assert isinstance(result, ImportCandidate)
    assert result.series.frame(0).time_s is None
    assert any("czas" in reason.lower() for reason in result.series.diagnostics)


def test_cancellation_during_import_produces_no_candidate(tmp_path: Path) -> None:
    source = write_mpp(tmp_path / "movie.mpp", [[[1, 2]]])
    session = write_session(tmp_path / "movie.json", source, [0])
    cancel = Event()
    messages = []

    def progress(message: str) -> None:
        messages.append(message)
        cancel.set()

    with pytest.raises(ImportCancelled):
        prepare_import(session, cancelled=cancel.is_set, progress=progress)
    assert messages


@pytest.mark.parametrize("contents", ["[]", "null", "{invalid", "{\"schema_version\": 1}"])
def test_invalid_json_reports_import_error(tmp_path: Path, contents: str) -> None:
    session = tmp_path / "bad.json"
    session.write_text(contents)
    with pytest.raises(MolTrackImportError):
        prepare_import(session)


def test_manual_demo_inputs_exercise_one_frame_reordered_and_recovery(tmp_path: Path) -> None:
    paths = create_demo_inputs(tmp_path)
    single = prepare_import(paths["single"])
    reordered = prepare_import(paths["reordered"])
    changed = prepare_import(paths["changed_mtime"])
    bad = prepare_import(paths["bad_source"])

    assert isinstance(single, ImportCandidate) and single.series.frame_count == 1
    assert isinstance(reordered, ImportCandidate)
    assert reordered.series.source_frame_indices == (3, 1)
    assert isinstance(changed, ImportCandidate) and changed.confirmation_reasons
    assert isinstance(bad, SourceRequest)
