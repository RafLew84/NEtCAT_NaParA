"""Real NanoTrack GUI scenarios; numeric truth comes from the known input or saved data."""
from __future__ import annotations

from copy import deepcopy
from dataclasses import fields, is_dataclass
import hashlib
from pathlib import Path
from typing import Any

import numpy as np
from PyQt6.QtWidgets import QApplication

from nanotrack.core import BBoxXYXY, ParticleMetrics, ParticleTrack, TrackFrameAnnotation
from nanotrack.ui.main_window import NanoTrackMainWindow
from scripts.nanotrack_acceptance.reporting import AcceptanceReport


def assert_same(expected: Any, actual: Any, location: str = "snapshot") -> None:
    """Compare persisted scientific data exactly, including dtype and missing samples."""
    if isinstance(expected, np.ndarray):
        assert isinstance(actual, np.ndarray), location
        assert expected.dtype == actual.dtype, location
        np.testing.assert_array_equal(actual, expected, err_msg=location)
    elif is_dataclass(expected) and not isinstance(expected, type):
        assert type(actual) is type(expected), location
        for field in fields(expected):
            assert_same(getattr(expected, field.name), getattr(actual, field.name), f"{location}.{field.name}")
    elif isinstance(expected, dict):
        assert expected.keys() == actual.keys(), location
        for key in expected:
            assert_same(expected[key], actual[key], f"{location}[{key}]")
    elif isinstance(expected, (list, tuple)):
        assert len(expected) == len(actual), location
        for index, value in enumerate(expected):
            assert_same(value, actual[index], f"{location}[{index}]")
    else:
        np.testing.assert_equal(actual, expected, err_msg=location)


def sample(path: Path) -> np.ndarray:
    """Known scale/NaN sample; no application processing function constructs the expected values."""
    rng = np.random.default_rng(2)
    y, x = np.mgrid[:64, :96]
    pattern = 100 + .08*x + .05*y + 4*np.exp(-((x-21)**2+(y-43)**2)/80)
    frames = np.stack([
        np.full((64, 96), 17.123456789), pattern + rng.normal(0, .2, (64, 96)),
        -250 + 2*pattern + rng.normal(0, .4, (64, 96)),
        1e8 + (pattern-100)*1e-5, np.full((64, 96), np.nan),
    ])
    frames[1, 25, 30:40] += 8
    frames[2, 12:15, 20:24] = np.nan
    header = ("[General Info]\nNumber of columns: 96\nNumber of rows: 64\nNumber of Frames: 5\n"
              "Acquisition channel: Topography\nZ unit: nm\n[Control]\nX Amplitude: 192 nm\n"
              "Y Amplitude: 64 nm\n[Frames Synchronization]\n"
              + "".join(f"Frame {i:04d}: {i*.5} s\n" for i in range(5)) + "[Header end]\n")
    path.write_bytes(header.encode("ascii") + frames[:, ::-1, ::-1].astype("<f8").tobytes())
    return frames


class Scenarios:
    def __init__(self, window: NanoTrackMainWindow, report: AcceptanceReport):
        self.window = window
        self.report = report

    def check_dialogs(self) -> None:
        assert not self.report.data.get("dialogs"), self.report.data.get("dialogs")

    def capture(self, name: str) -> None:
        QApplication.processEvents()
        self.check_dialogs()
        path = self.report.directory / f"{name}.png"
        assert self.window.grab().save(str(path)), f"Could not save {path}"
        self.report.data["artifacts"].append(path.name)

    def identify(self, path: Path) -> None:
        with path.open("rb") as stream:
            digest = hashlib.file_digest(stream, "sha256").hexdigest()
        self.report.data["input"] = {"path": str(path), "sha256": digest, "bytes": path.stat().st_size}

    def process(self) -> None:
        with self.report.stage("repair") as stage:
            self.window.preprocessing_panel.btn_repair_apply_all.click()
            self.check_dialogs()
            assert self.window.current_repair_frames() is not None, "Repair produced no result"
            stage["parameters"] = self.window.preprocessing_panel.repair_parameters()
        with self.report.stage("bm3d") as stage:
            self.window.preprocessing_panel.btn_apply_all.click()
            self.check_dialogs()
            assert self.window.current_denoised_frames() is not None, "BM3D produced no result"
            stage["sigma_factor"] = self.window.preprocessing_panel.bm3d_sigma_factor()
            self.window.cmb_preview_source.setCurrentIndex(1)

    def roundtrip(self) -> None:
        with self.report.stage("save_open"):
            before = self.window.current_session_snapshot()
            assert before is not None
            path = self.report.directory / "result.nanotrack"
            self.window.save_session_to_path(str(path))
            self.window.load_session_from_path(str(path))
            self.check_dialogs()
            assert_same(before, self.window.current_session_snapshot())
            self.report.data["artifacts"].append(path.name)

    def views(self) -> None:
        with self.report.stage("views"):
            before = self.window.current_session_snapshot()
            assert before is not None
            aligned = self.window.action_show_aligned_registration
            expanded = self.window.action_show_expanded_aligned_registration
            assert aligned is not None and expanded is not None
            expanded.setChecked(False)
            aligned.setChecked(False)
            self.window.cmb_preview_source.setCurrentIndex(0)
            sequence = self.window.current_sequence()
            assert sequence is not None
            np.testing.assert_array_equal(self.window.viewer.viewer.image_item.image, sequence.active_frame)
            self.capture("original")
            processed = self.window.current_denoised_frames()
            if processed is None:
                processed = self.window.current_repair_frames()
            if processed is not None:
                self.window.cmb_preview_source.setCurrentIndex(1)
                np.testing.assert_array_equal(self.window.viewer.viewer.image_item.image, processed[sequence.active_frame_index])
                self.capture("processed")
            if self.window.current_registration_results() is not None:
                aligned.setChecked(True)
                self.capture("aligned")
            aligned.setChecked(before.show_aligned_in_viewer)
            expanded.setChecked(before.show_expanded_aligned_in_viewer)
            self.window.cmb_preview_source.setCurrentIndex(1 if before.preview_source == "processed" else 0)

    def quick(self) -> None:
        path = self.report.directory / "S1.MPP"
        expected = sample(path)
        with self.report.stage("load"):
            self.window.load_sequence_from_path(str(path))
            self.identify(path)
            sequence = self.window.current_sequence()
            assert sequence is not None
            assert_same(expected, sequence.raw_frames)
            assert sequence.metadata.value_unit == "nm"
        self.process()
        with self.report.stage("calibration") as stage:
            output = self.window.current_denoised_frames()
            assert output is not None
            assert output.dtype == np.float64
            np.testing.assert_array_equal(np.isfinite(output), np.isfinite(expected))
            assert np.all(output[0] == 17.123456789)
            assert 95 < float(np.nanmedian(output[1])) < 115
            assert -55 < float(np.nanmedian(output[2])) < -20
            assert np.max(np.abs(output[3] - 1e8)) < 1e-3
            assert np.isnan(output[4]).all()
            assert_same(expected, sequence.raw_frames)
            stage.update(constant=17.123456789, unit="nm", dtype=str(output.dtype),
                         valid_counts=np.isfinite(output).sum(axis=(1, 2)).tolist())
            self.window.slider_frame.setValue(4)
            assert "0/6144" in self.window.lbl_preview_source.text()
            self.capture("all_missing")
            self.window.slider_frame.setValue(0)
        self.roundtrip()
        self.views()

    def full(self, path: Path) -> None:
        with self.report.stage("load"):
            self.window.load_sequence_from_path(str(path))
            self.identify(path)
            sequence = self.window.current_sequence()
            assert sequence is not None
            original = sequence.raw_frames.copy()
        with self.report.stage("registration"):
            self.window.cmb_registration_backend.setCurrentIndex(self.window.cmb_registration_backend.findData("ecc_translation"))
            registration_action = self.window.action_run_registration
            assert registration_action is not None
            registration_action.trigger()
            self.check_dialogs()
            result = self.window.current_registration_results()
            assert result is not None
            shifts = result.shifts_xy_array().copy()
            np.save(self.report.directory / "shifts-before.npy", shifts)
            index = min(9, sequence.frame_count - 1)
            box = BBoxXYXY(1, 1, min(8, sequence.frame_shape[1]-1), min(8, sequence.frame_shape[0]-1))
            marker = ParticleTrack(1, index, box, label="Acceptance persistence marker")
            marker.add_annotation(TrackFrameAnnotation(index, bbox=box, metrics=ParticleMetrics(area_px=49), source_view="raw"))
            self.window.set_tracks([marker], selected_track_id=1)
            expected_tracks = deepcopy(self.window.current_tracks())
        self.process()
        with self.report.stage("preservation") as stage:
            result = self.window.current_registration_results()
            assert result is not None
            assert_same(shifts, result.shifts_xy_array())
            assert_same(original, sequence.raw_frames)
            processed = self.window.current_denoised_frames()
            assert processed is not None
            np.testing.assert_array_equal(np.isfinite(processed), np.isfinite(original))
            assert_same(expected_tracks, self.window.current_tracks())
            self.window.slider_frame.setValue(index)
            stage.update(frames=sequence.frame_count, dxdy_max_difference=0.0,
                         marker_note="Synthetic persistence marker; not a scientific measurement")
        self.roundtrip()
        self.views()

    def session(self, path: Path) -> None:
        with self.report.stage("load"):
            self.window.load_session_from_path(str(path))
            self.identify(path)
        self.roundtrip()
        self.views()
