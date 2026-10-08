"""Working settings, kept separate from parameters that produced saved results."""
from __future__ import annotations

from typing import TYPE_CHECKING
from PyQt6.QtWidgets import QCheckBox, QComboBox, QDoubleSpinBox, QSlider, QSpinBox

if TYPE_CHECKING:
    from nanotrack.ui.main_window import NanoTrackMainWindow

Control = QCheckBox | QComboBox | QDoubleSpinBox | QSlider | QSpinBox


def _controls(window: NanoTrackMainWindow) -> dict[str, Control]:
    particle, edge = window.track_list_panel, window.polygon_tools_panel
    preprocessing, yolo, bbox = window.preprocessing_panel, window.yolo_panel, window.bbox_tools_panel
    controls: dict[str, Control] = {
        "registration.backend": window.cmb_registration_backend,
        "viewer.gamma_percent": window.viewer.viewer.slider_gamma,
        "particle.frame_limit": particle.sp_run_frame_limit,
        "particle.probability_threshold": particle.sp_mask_probability_threshold,
        "bbox.width": bbox.sp_width, "bbox.height": bbox.sp_height,
        "edge.end_frame": edge.sp_run_end_frame, "edge.stitch": edge.chk_stitch_active,
        "edge.backend": edge.cmb_edge_backend, "edge.threshold": edge.sp_dexined_threshold,
        "edge.components": edge.sp_edge_components, "edge.resolution": edge.cmb_inference_resolution,
        "edge.muge_granularity": edge.sp_muge_granularity, "edge.polyline_method": edge.cmb_polyline_method,
        "edge.refine_score": edge.cmb_refine_score_mode, "edge.refine_radius": edge.sp_refine_radius,
        "point_tracker.backend": edge.cmb_tracker, "point_tracker.points": edge.sp_tracker_points,
        "repair.threshold": preprocessing.sp_repair_threshold,
        "repair.min_width": preprocessing.sp_repair_min_width, "repair.max_width": preprocessing.sp_repair_max_width,
        "repair.thickness": preprocessing.sp_repair_thickness, "repair.gap": preprocessing.sp_repair_gap,
        "repair.mode": preprocessing.cmb_repair_mode, "bm3d.sigma": preprocessing.sp_bm3d_sigma,
        "yolo.model": yolo.cmb_model, "yolo.confidence": yolo.sp_confidence,
        "yolo.iou": yolo.sp_iou, "yolo.scale_multiplier": yolo.sp_scale_multiplier,
    }
    results = window.current_results_dialog()
    if results is not None:
        controls.update({"results.units": results.cmb_units,
                         "results.boundary_correction": results.chk_exclude_boundary_pixels,
                         "results.boundary_weight": results.spn_boundary_pixel_weight})
    edges = window.current_edge_results_dialog()
    if edges is not None:
        controls.update({"edge_results.units": edges.cmb_units, "edge_results.trend": edges.cmb_trend})
    return controls


def _json_value(value: object) -> object:
    return list(value) if isinstance(value, tuple) else value


def capture_settings(window: NanoTrackMainWindow) -> dict[str, object]:
    result: dict[str, object] = {}
    for name, control in _controls(window).items():
        if isinstance(control, QComboBox):
            result[name] = _json_value(control.currentData())
        elif isinstance(control, QCheckBox):
            result[name] = control.isChecked()
        else:
            result[name] = control.value()
    levels = window.viewer.viewer.hist.getLevels()
    if levels is not None:
        result["viewer.levels"] = [float(levels[0]), float(levels[1])]
    return result


def restore_settings(window: NanoTrackMainWindow, settings: dict[str, object]) -> None:
    for name, control in _controls(window).items():
        if name not in settings:
            continue
        value = settings[name]
        if isinstance(control, QComboBox):
            for index in range(control.count()):
                if _json_value(control.itemData(index)) == value:
                    control.setCurrentIndex(index)
                    break
        elif isinstance(control, QCheckBox) and isinstance(value, bool):
            control.setChecked(value)
        elif isinstance(control, (QSpinBox, QSlider)) and isinstance(value, int):
            control.setValue(value)
        elif isinstance(control, QDoubleSpinBox) and isinstance(value, (int, float)):
            control.setValue(value)
    levels = settings.get("viewer.levels")
    if isinstance(levels, list) and len(levels) == 2 and all(isinstance(item, (int, float)) for item in levels):
        window.viewer.viewer.hist.setLevels(*levels)
