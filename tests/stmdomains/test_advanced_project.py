"""Saved projects preserve the advanced method, draft and diagnostic raster."""

from dataclasses import asdict
import numpy as np

from stmdomains.analysis import analyze_frame
from stmdomains.analysis.barrier_settings import BarrierSettings
from stmdomains.analysis.descriptor_settings import DescriptorSettings
from stmdomains.analysis.series_settings import SeriesAnalysisPlan
from stmdomains.core.frame_presentation import FramePresenter
from stmdomains.core.project import ProjectAnalysis, ProjectSnapshot
from stmdomains.io.moltrack_import import prepare_import
from stmdomains.io.project import open_project, save_project
from stmdomains.io.project_validation import analysis_plan
from stmdomains.tools.analysis_demo import create_analysis_demo


def test_project_keeps_advanced_result_and_independent_draft_without_recalculation(tmp_path, monkeypatch):
    from sklearn.cluster import KMeans
    from sklearn.decomposition import PCA
    series = prepare_import(create_analysis_demo(tmp_path / 'input')['series']).series
    descriptor = DescriptorSettings(descriptor_sigma_factor=1.7, pca_max_components=7)
    barriers = BarrierSettings(high_percentile=95, dilation_factor=.25)
    result = analyze_frame(FramePresenter(series).analysis_input(1), k=4,
                           descriptor_settings=descriptor, barrier_settings=barriers)
    assert result.barrier_mask.any()
    draft = SeriesAnalysisPlan(current_frame=True, descriptor_settings=DescriptorSettings(descriptor_sigma_factor=2))
    analysis = ProjectAnalysis('advanced', (1,), {1: result}, {1: {'status': result.status}}, (result.catalogue,))
    snapshot = ProjectSnapshot(series, {'current_index': 1, 'layers': {'barriers': True}},
        {'plan': asdict(draft), 'scope': 'current_frame', 'class_mode': 'new'}, analysis)
    path = tmp_path / 'advanced.stmdomains'
    save_project(path, snapshot)
    def no_fit(*args, **kwargs):
        raise AssertionError('Restoring a project must not fit models')
    monkeypatch.setattr(PCA, 'fit', no_fit)
    monkeypatch.setattr(KMeans, 'fit', no_fit)
    opened = open_project(path)
    restored = opened.analysis.frames[1]
    np.testing.assert_array_equal(restored.barrier_mask, result.barrier_mask)
    assert restored.parameters == result.parameters and restored.catalogue.identifier == result.catalogue.identifier
    assert analysis_plan(opened.draft['plan']).descriptor_settings.descriptor_sigma_factor == 2
    assert opened.view['layers']['barriers'] is True
    reapplied = analyze_frame(FramePresenter(opened.series).analysis_input(1), catalogue=restored.catalogue,
                              barrier_settings=BarrierSettings.from_parameters(restored.parameters))
    np.testing.assert_array_equal(reapplied.barrier_mask, restored.barrier_mask)
    assert reapplied.assignments == restored.assignments
