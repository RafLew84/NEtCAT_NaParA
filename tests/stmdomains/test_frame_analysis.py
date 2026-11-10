"""Public single-frame calculations, using generated inputs rather than saved models."""

import numpy as np
import pytest
from dataclasses import replace

from stmdomains.analysis import analyze_frame
from stmdomains.core.analysis_result import AnalysisCancelled, AnalysisInput
from stmdomains.core.annotations import Detection, FrameAnnotations
from stmdomains.core.series import FrameData
from stmdomains.tools.analysis_demo import lattice_patches, molecule_image


def analysis_input(points=(), *, image=None, state="available", names=None):
    image = np.zeros((256, 256), dtype=float) if image is None else image
    names = names or [f"m-{i:04d}" for i in range(len(points))]
    detections = tuple(Detection(name, 3, (x-1, y-1, x+1, y+1),
                                (x-1, y-1, x+1, y+1), None, "raw", False, {})
                       for name, (x, y) in zip(names, points))
    annotations = FrameAnnotations(detections, (), (), state, "missing", "", "")
    return AnalysisInput("session-A", FrameData(3, 19, image), annotations)


def test_no_annotations_are_reported_as_unavailable_analysis_not_zero_domains():
    result = analyze_frame(analysis_input())
    assert result.status == "no_annotations"
    assert result.series_id == "session-A"
    assert (result.working_index, result.source_index) == (3, 19)
    assert result.total_count == 0 and result.classes == ()
    assert result.message


def five_lattices():
    points = []
    for (cx, cy), angle in zip(((64, 64), (192, 64), (320, 64), (128, 192), (256, 192)),
                               (0, 18, 36, 54, 72)):
        theta = np.deg2rad(angle)
        rotation = np.array([[np.cos(theta), -np.sin(theta)], [np.sin(theta), np.cos(theta)]])
        lattice = np.array([(x * 8., y * 9.) for x in range(-3, 4) for y in range(-3, 4)])
        points.extend(lattice @ rotation.T + (cx, cy))
    return np.asarray(points)


def test_calculation_fits_five_classes_and_keeps_separated_lattices_separate():
    data = analysis_input(five_lattices(), image=np.zeros((256, 384)))
    result = analyze_frame(data)
    assert result.status == "complete", result.message
    assert len(result.classes) == 5
    assert result.assigned_count > 0 and result.domain_count >= 3
    assert set(result.assignments) == {item.detection_id for item in data.annotations.detections}
    domains = {}
    for i, item in enumerate(data.annotations.detections):
        member = result.assignments[item.detection_id]
        if member.domain_local_id:
            domains.setdefault(member.domain_local_id, set()).add(i // 49)
    assert all(len(source_patches) == 1 for source_patches in domains.values())
    assert result.metadata["model_state"]["centers"]


def test_missing_and_partial_annotations_do_not_become_a_complete_empty_result():
    for state in ("missing", "partial", "invalid"):
        result = analyze_frame(analysis_input(state=state))
        assert result.status == "insufficient_data"
        assert result.message


def test_too_few_centres_preserve_k5_and_return_explanation():
    result = analyze_frame(analysis_input([(10, 10), (20, 10), (10, 20), (20, 20)]))
    assert result.status == "insufficient_data"
    assert result.parameters["k"] == 5
    assert result.active_count == 4 and result.assigned_count == 0
    assert all(item.rejection_reason == "insufficient_samples" for item in result.assignments.values())


def test_cancel_during_null_generation_does_not_return_a_partial_model():
    cancelled = False

    def progress(text):
        nonlocal cancelled
        if "Kalibracja" in text:
            cancelled = True

    with pytest.raises(AnalysisCancelled):
        analyze_frame(analysis_input(five_lattices(), image=np.zeros((256, 384))),
                      cancelled=lambda: cancelled, progress=progress)


def test_source_fingerprint_records_duplicate_priority_used_by_calculation():
    points = [(10, 10), (20, 10), (10, 20), (20, 20), (10.1, 10)]
    data = analysis_input(points)
    records = data.annotations.detections
    preferred = replace(records[-1], metadata={"origin": "manual", "confidence": 1.})
    changed = replace(data, annotations=replace(data.annotations, detections=records[:-1] + (preferred,)))
    first, second = analyze_frame(data), analyze_frame(changed)
    assert first.suppressed_count == second.suppressed_count == 1
    assert first.assignments["m-0004"].status == "suppressed_duplicate"
    assert second.assignments["m-0000"].status == "suppressed_duplicate"
    assert first.metadata["input_sha256"] != second.metadata["input_sha256"]


def memberships(result):
    return {key: (member.domain_local_id, member.class_id, member.provisional_class_id,
                  member.status, member.rejection_reason) for key, member in result.assignments.items()}


def test_repeated_and_reordered_inputs_preserve_memberships_and_do_not_mutate_data():
    data = analysis_input(five_lattices(), image=np.zeros((256, 384)))
    before = data.frame.image.copy()
    first = analyze_frame(data)
    reversed_data = replace(data, annotations=replace(data.annotations,
                                                    detections=tuple(reversed(data.annotations.detections))))
    second = analyze_frame(reversed_data)
    assert memberships(first) == memberships(second)
    assert first.metadata["model_id"] == second.metadata["model_id"]
    assert first.metadata["input_sha256"] == second.metadata["input_sha256"]
    np.testing.assert_array_equal(data.frame.image, before)
    with pytest.raises(TypeError):
        first.parameters["k"] = 99


def test_pixel_scale_is_inferred_from_the_input_and_preserves_memberships():
    points = five_lattices()
    normal = analyze_frame(analysis_input(points, image=np.zeros((256, 384))))
    doubled = analyze_frame(analysis_input(points * 2, image=np.zeros((512, 768))))
    assert doubled.parameters["spacing_px"] == pytest.approx(2 * normal.parameters["spacing_px"])
    assert memberships(doubled) == memberships(normal)
    assert doubled.metadata["order_calibration"] == normal.metadata["order_calibration"]


def test_mismatched_frame_and_duplicate_identifiers_are_refused():
    data = analysis_input([(10, 10), (20, 10), (10, 20), (20, 20), (30, 30)])
    wrong_frame = replace(data.annotations.detections[0], frame_index=7)
    with pytest.raises(ValueError, match="innej klatki"):
        analyze_frame(replace(data, annotations=replace(data.annotations,
                      detections=(wrong_frame,) + data.annotations.detections[1:])))
    duplicated = replace(data.annotations.detections[-1], detection_id="m-0000")
    with pytest.raises(ValueError, match="ID"):
        analyze_frame(replace(data, annotations=replace(data.annotations,
                      detections=data.annotations.detections[:-1] + (duplicated,))))


def test_image_barriers_can_leave_a_computed_zero_with_an_actual_fitted_model():
    points = lattice_patches(aligned=True)
    result = analyze_frame(analysis_input(points, image=molecule_image(points, steps=True)))
    assert result.status == "complete"
    assert len(result.classes) == 5 and result.metadata["model_state"]["fit_count"] >= 5
    assert result.assigned_count == result.domain_count == 0
    assert result.active_count == 405
    assert result.metadata["domain_construction"]["barrier_cut_edges"] > 0
    assert all(member.class_id == "" for member in result.assignments.values())


def test_one_near_duplicate_per_molecule_does_not_define_the_lattice_scale():
    points = five_lattices()
    names = [f"m-{i:04d}" for i in range(len(points))]
    duplicate_names = [f"z-{i:04d}" for i in range(len(points))]
    normal = analyze_frame(analysis_input(points, image=np.zeros((256, 384)), names=names))
    duplicated = analyze_frame(analysis_input(np.vstack((points, points + .05)), image=np.zeros((256, 384)),
                                            names=names + duplicate_names))
    assert duplicated.suppressed_count == len(points)
    assert duplicated.parameters["spacing_px"] == normal.parameters["spacing_px"]
    assert {name: memberships(duplicated)[name] for name in names} == memberships(normal)


def test_even_no_annotation_outcomes_keep_source_content_provenance():
    first = analyze_frame(analysis_input())
    second = analyze_frame(analysis_input(image=np.ones((256, 256))))
    assert first.metadata["input_sha256"] != second.metadata["input_sha256"]
