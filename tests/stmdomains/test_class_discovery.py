"""Manual K and explicitly selected class-discovery inputs."""

import numpy as np
import pytest
from dataclasses import replace

from stmdomains.analysis import analyze_frame
from test_frame_analysis import analysis_input, five_lattices


@pytest.mark.parametrize("k", [1, 4, 8])
def test_manual_k_reaches_the_fit_assignments_and_result(k):
    data = analysis_input(five_lattices(), image=np.zeros((256, 384)))
    result = analyze_frame(data, k=k)
    assert result.status == "complete", result.message
    assert len(result.classes) == result.parameters["k"] == result.metadata["model_state"]["k"] == k
    assert len(result.metadata["model_state"]["centers"]) == k
    assert {m.provisional_class_id for m in result.assignments.values()} <= {str(i) for i in range(1, k + 1)}
    assert result.assigned_count > 0


def test_k1_small_or_constant_fit_accepts_its_pattern_and_refuses_distant_features():
    from stmdomains.analysis.clustering import fit_model, apply_classes

    samples = np.array([[1., 0.], [0., 1.]])
    for training in (samples[:1], np.repeat(samples[:1], 3, axis=0)):
        state = fit_model(training, 1, lambda: None)
        assert state is not None and state["margin_rule"] == "not_applicable_k1"
        labels, reliable, details = apply_classes(samples, np.ones(2, bool), state, lambda: None)
        assert labels.tolist() == [0, 0]
        assert reliable.tolist() == [True, False]
        assert np.isfinite(details["class_confidence"]).all()
    assert fit_model(samples[:1], 2, lambda: None) is None


def test_fitted_model_applies_without_training_again(monkeypatch):
    from sklearn.decomposition import PCA
    from sklearn.cluster import KMeans
    from stmdomains.analysis.clustering import fit_classes, apply_classes

    features = np.array([[1., 0., 0.], [.98, .02, 0.], [0., 1., 0.], [.02, .98, 0.]])
    valid = np.ones(4, bool)
    labels, reliable, details, state = fit_classes(features, valid, valid, lambda: None, k=2)

    def forbid_fit(*args, **kwargs):
        raise AssertionError("Applying an existing catalogue must not fit PCA or KMeans")

    monkeypatch.setattr(PCA, "fit", forbid_fit)
    monkeypatch.setattr(KMeans, "fit", forbid_fit)
    reapplied = apply_classes(features, valid, state, lambda: None)
    np.testing.assert_array_equal(reapplied[0], labels)
    np.testing.assert_array_equal(reapplied[1], reliable)
    np.testing.assert_array_equal(reapplied[2]["class_confidence"], details["class_confidence"])


def input_at(index, *, points=None):
    data = analysis_input(five_lattices() if points is None else points, image=np.zeros((256, 384)))
    return replace(data, frame=replace(data.frame, working_index=index, source_index=index + 10),
                   annotations=replace(data.annotations, detections=tuple(
                       replace(d, frame_index=index) for d in data.annotations.detections)))


def test_shared_fit_reads_only_selected_inputs_and_applies_to_a_separate_target(monkeypatch):
    from sklearn.decomposition import PCA
    from stmdomains.analysis import discover_classes
    from stmdomains.analysis.class_settings import ClassFitSettings

    seen = []

    def read(index):
        assert index in (1, 2, 4), "Unselected frame must not participate in discovery"
        seen.append(index)
        return input_at(index)

    result = discover_classes(read, frame_count=5, current_index=4,
                              settings=ClassFitSettings(k=4, scope="selected_range", start=1, end=2))
    assert set(seen) == {1, 2, 4}
    assert result.status == "complete" and result.working_index == 4
    assert result.metadata["fit_scope"] == "selected_range"
    assert result.metadata["fit_working_indices"] == (1, 2)
    assert result.catalogue is not None
    assert result.catalogue.identifier == result.metadata["model_id"]
    assert [row["working_index"] for row in result.metadata["fit_frames"]] == [1, 2]
    assert all(row["spacing_px"] > 0 and row["input_sha256"] for row in result.metadata["fit_frames"])

    def forbid_fit(*args, **kwargs):
        raise AssertionError("The saved catalogue must be applied, not refitted")

    monkeypatch.setattr(PCA, "fit", forbid_fit)
    repeated = analyze_frame(input_at(4), catalogue=result.catalogue)
    assert repeated.assignments == result.assignments
    np.testing.assert_array_equal(repeated.domain_labels, result.domain_labels)
    other = analyze_frame(input_at(0), catalogue=result.catalogue)
    assert other.catalogue is result.catalogue and other.metadata["model_id"] == result.metadata["model_id"]


@pytest.mark.parametrize("k", [0, 9, 1.5, True])
def test_invalid_manual_k_is_refused(k):
    with pytest.raises(ValueError, match="od 1 do 8"):
        analyze_frame(input_at(0), k=k)


def test_local_fit_does_not_read_other_frames_and_does_not_transfer_its_catalogue():
    from stmdomains.analysis import discover_classes
    from stmdomains.analysis.class_settings import ClassFitSettings

    def only_current(index):
        assert index == 2
        return input_at(index)

    settings = ClassFitSettings(k=1)
    first = discover_classes(only_current, frame_count=4, current_index=2, settings=settings)
    repeated = discover_classes(only_current, frame_count=50, current_index=2, settings=settings)
    assert first.assignments == repeated.assignments
    assert first.catalogue.identifier == repeated.catalogue.identifier
    with pytest.raises(ValueError, match="Lokalny katalog"):
        analyze_frame(input_at(3), catalogue=first.catalogue)
    with pytest.raises(ValueError, match="innej serii"):
        analyze_frame(replace(input_at(2), series_id="other"), catalogue=first.catalogue)
    with pytest.raises(TypeError):
        first.catalogue.state["k"] = 8


def test_whole_series_records_empty_frames_and_target_does_not_change_the_fit():
    from stmdomains.analysis import discover_classes
    from stmdomains.analysis.class_settings import ClassFitSettings

    frames = [input_at(0), input_at(1, points=[])]
    settings = ClassFitSettings(k=4, scope="whole_series")
    result = discover_classes(frames.__getitem__, frame_count=2, current_index=0, settings=settings)
    empty = discover_classes(frames.__getitem__, frame_count=2, current_index=1, settings=settings)
    assert result.catalogue.identifier == empty.catalogue.identifier
    assert result.metadata["fit_working_indices"] == (0, 1)
    assert empty.status == "no_annotations" and empty.catalogue.k == 4
    assert empty.metadata["fit_frames"][1]["used_samples"] == 0
    assert empty.metadata["fit_frames"][1]["status"] == "no_annotations"


def test_discovery_refuses_missing_data_and_invalid_range_and_can_be_cancelled():
    from stmdomains.analysis import discover_classes
    from stmdomains.analysis.class_settings import ClassFitSettings
    from stmdomains.core.analysis_result import AnalysisCancelled

    with pytest.raises(ValueError, match="Brak użytecznych"):
        discover_classes(lambda i: input_at(i, points=[]), frame_count=2, current_index=0,
                         settings=ClassFitSettings(k=8, scope="whole_series"))
    with pytest.raises(ValueError, match="poza serię"):
        discover_classes(input_at, frame_count=2, current_index=0,
                         settings=ClassFitSettings(scope="selected_range", end=2))
    with pytest.raises(ValueError, match="Początek"):
        ClassFitSettings(scope="selected_range", start=2, end=1)
    cancelled = False

    def progress(text):
        nonlocal cancelled
        if "Kalibracja" in text:
            cancelled = True

    with pytest.raises(AnalysisCancelled):
        discover_classes(input_at, frame_count=3, current_index=0,
                         settings=ClassFitSettings(scope="whole_series"),
                         cancelled=lambda: cancelled, progress=progress)
