"""Advanced settings change the actual method, while frozen catalogues stay frozen."""

import numpy as np
import pytest

from stmdomains.analysis import analyze_frame
from test_frame_analysis import analysis_input, five_lattices, memberships


def test_decimal_pair_range_accepts_minimum_width_and_rejects_narrower_ranges():
    from stmdomains.analysis.descriptor_settings import DescriptorSettings
    for bounds in ((.2, .3), (.3, .4), (1.3, 1.4)):
        settings = DescriptorSettings(descriptor_pair_distance_range=bounds)
        assert settings.descriptor_pair_distance_range == bounds
    with pytest.raises(ValueError, match='szerokość'):
        DescriptorSettings(descriptor_pair_distance_range=(.2, .299999))


def test_descriptor_settings_fit_matching_dimensions_and_a_new_catalogue():
    from stmdomains.analysis.descriptor_settings import DescriptorSettings
    data = analysis_input(five_lattices(), image=np.zeros((256, 384)))
    baseline = analyze_frame(data)
    settings = DescriptorSettings(descriptor_sigma_factor=1.7, descriptor_radial_bins=8,
                                  descriptor_angle_bins=18, pca_max_components=7)
    changed = analyze_frame(data, descriptor_settings=settings)
    assert changed.status == 'complete'
    assert changed.catalogue.identifier != baseline.catalogue.identifier
    assert np.asarray(changed.catalogue.state['pca_components']).shape == (7, 144)
    assert np.asarray(changed.catalogue.state['centers']).shape == (5, 7)
    assert changed.parameters['descriptor_sigma_factor'] == 1.7
    reused = analyze_frame(data, catalogue=changed.catalogue)
    assert reused.catalogue is changed.catalogue
    assert memberships(reused) == memberships(changed)
    restored = analyze_frame(data, descriptor_settings=DescriptorSettings())
    assert restored.catalogue.identifier == baseline.catalogue.identifier
    assert memberships(restored) == memberships(baseline)


def test_shared_custom_descriptor_survives_reuse_and_refuses_incompatible_plan(tmp_path):
    from stmdomains.analysis.descriptor_settings import DescriptorSettings
    from stmdomains.analysis.series_settings import SeriesAnalysisPlan
    from stmdomains.analysis.series_analysis import analyze_series
    from stmdomains.core.frame_presentation import FramePresenter
    from stmdomains.io.moltrack_import import prepare_import
    from stmdomains.tools.analysis_demo import create_analysis_demo
    series = prepare_import(create_analysis_demo(tmp_path)['series']).series
    reader = FramePresenter(series).analysis_input
    settings = DescriptorSettings(descriptor_radial_bins=8, descriptor_angle_bins=18, pca_max_components=7)
    plan = SeriesAnalysisPlan(start=0, end=1, k=4, descriptor_settings=settings)
    events = list(analyze_series(reader, frame_count=series.frame_count, series_id=series.identity, plan=plan))
    catalogue = events[0]
    assert np.asarray(catalogue.state['pca_components']).shape == (7, 144)
    assert all(event.result.catalogue is catalogue for event in events[1:])
    from dataclasses import replace
    reused = list(analyze_series(reader, frame_count=series.frame_count, series_id=series.identity,
                                plan=replace(plan, fit_source='existing'), catalogue=catalogue))
    assert memberships(reused[1].result) == memberships(events[1].result)
    def forbidden_read(index):
        pytest.fail('Incompatible descriptor must be refused before reading frames')
    with pytest.raises(ValueError, match='opis|parametr'):
        list(analyze_series(forbidden_read, frame_count=series.frame_count, series_id=series.identity,
                            plan=replace(plan, fit_source='existing', descriptor_settings=DescriptorSettings()),
                            catalogue=catalogue))


def test_auto_uses_requested_pca_limit_in_its_selected_model():
    from stmdomains.analysis.descriptor_settings import DescriptorSettings
    from stmdomains.tools.auto_classes_demo import lattice
    data = analysis_input(lattice(45, (128, 128)))
    result = analyze_frame(data, class_count_mode='auto', auto_max_k=3,
                           descriptor_settings=DescriptorSettings(pca_max_components=3))
    assert result.catalogue is not None, result.message
    assert result.catalogue.k == 1
    assert np.asarray(result.catalogue.state['pca_components']).shape == (3, 504)
    assert result.catalogue.parameters['pca_max_components'] == 3


def test_barrier_changes_preserve_fitted_classes_and_change_observed_masks(monkeypatch):
    from stmdomains.analysis.barrier_settings import BarrierSettings
    from stmdomains.tools.analysis_demo import lattice_patches, molecule_image
    from sklearn.cluster import KMeans
    from sklearn.decomposition import PCA
    points = lattice_patches(aligned=True)
    data = analysis_input(points, image=molecule_image(points, steps=True))
    baseline = analyze_frame(data)
    assert baseline.status == 'complete' and baseline.barrier_mask.any()
    def no_fit(*args, **kwargs):
        pytest.fail('Barrier-only analysis must not fit PCA or KMeans')
    monkeypatch.setattr(PCA, 'fit', no_fit)
    monkeypatch.setattr(KMeans, 'fit', no_fit)
    changed = analyze_frame(data, catalogue=baseline.catalogue,
        barrier_settings=BarrierSettings(minimum_span_factor=100, dilation_factor=0))
    assert changed.catalogue is baseline.catalogue
    assert not changed.barrier_mask.any()
    assert changed.assigned_count > baseline.assigned_count
    assert {key: a.provisional_class_id for key, a in changed.assignments.items()} == {
        key: a.provisional_class_id for key, a in baseline.assignments.items()}
    assert baseline.barrier_mask.any() and not baseline.barrier_mask.flags.writeable
    assert changed.parameters['barrier_minimum_span_factor'] == 100


def test_rebuilding_domains_keeps_nondefault_descriptor_and_barriers():
    from dataclasses import replace
    from stmdomains.analysis.descriptor_settings import DescriptorSettings
    from stmdomains.analysis.barrier_settings import BarrierSettings
    from stmdomains.analysis.domain_settings import DomainSettings
    from stmdomains.analysis.domain_tuning import recalculate_domains
    data = analysis_input(five_lattices(), image=np.zeros((256, 384)))
    result = analyze_frame(data, descriptor_settings=DescriptorSettings(descriptor_sigma_factor=1.7),
                           barrier_settings=BarrierSettings(high_percentile=95))
    rebuilt = recalculate_domains(data, result, DomainSettings(minimum_domain_size=10))
    assert rebuilt.catalogue is result.catalogue
    assert rebuilt.parameters['descriptor_sigma_factor'] == 1.7
    assert rebuilt.parameters['barrier_high_percentile'] == 95
    assert rebuilt.metadata['barriers']['parameters']['high_percentile'] == 95
    np.testing.assert_array_equal(rebuilt.barrier_mask, result.barrier_mask)
    tampered = replace(result, parameters={**result.parameters, 'descriptor_sigma_factor': 1.25})
    with pytest.raises(ValueError, match='Analizuj klatkę'):
        recalculate_domains(data, tampered, DomainSettings())


def test_incompatible_model_dimensions_fail_before_preparing_frame():
    from dataclasses import replace
    from stmdomains.core.immutable import plain_metadata
    data = analysis_input(five_lattices(), image=np.zeros((256, 384)))
    result = analyze_frame(data)
    state = plain_metadata(result.catalogue.state)
    state['pca_mean'] = state['pca_mean'][:-1]
    invalid = replace(result.catalogue, state=state)
    progress = []
    with pytest.raises(ValueError, match='wymiar'):
        analyze_frame(data, catalogue=invalid, progress=progress.append)
    assert not progress
