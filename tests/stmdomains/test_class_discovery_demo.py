"""User-runnable controls for K1, excessive K, and untouched out-of-scope frames."""

import pytest

from stmdomains.analysis import discover_classes
from stmdomains.analysis.class_settings import ClassFitSettings
from stmdomains.core.frame_presentation import FramePresenter
from stmdomains.io.moltrack_import import prepare_import
from stmdomains.tools.class_discovery_demo import create_class_discovery_demo


def test_single_frame_demo_supports_k1_but_refuses_k8(tmp_path):
    paths = create_class_discovery_demo(tmp_path)
    presenter = FramePresenter(prepare_import(paths["single"]).series)
    result = discover_classes(presenter.analysis_input, frame_count=1, current_index=0,
                              settings=ClassFitSettings(k=1))
    assert result.status == "complete" and result.catalogue.k == 1 and result.domain_count == 1
    with pytest.raises(ValueError, match="K8"):
        discover_classes(presenter.analysis_input, frame_count=1, current_index=0, settings=ClassFitSettings(k=8))


def test_pair_of_demo_series_has_identical_local_result_despite_different_other_frames(tmp_path):
    paths = create_class_discovery_demo(tmp_path)
    first, second = [FramePresenter(prepare_import(paths[name]).series) for name in ("pair_a", "pair_b")]
    a, b = [discover_classes(presenter.analysis_input, frame_count=3, current_index=0, settings=ClassFitSettings(k=5))
            for presenter in (first, second)]
    assert a.assignments == b.assignments and a.catalogue.identifier == b.catalogue.identifier
    assert not (first.series.frame(1).image == second.series.frame(1).image).all()
