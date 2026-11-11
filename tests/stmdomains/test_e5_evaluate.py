import numpy as np

from stmdomains.experiments.e5_evaluate import evaluation_rows, valid_reference


def test_evaluation_preserves_anchor_but_restores_new_small_window_support():
    rows = [dict(element_id='a', raw_edge_xy=[19., 40.], available=False,
                 transfer_split=None, scale_raw_px=48)]
    changed = evaluation_rows(rows, np.array([True]), np.array([True]))
    assert changed[0]['raw_edge_xy'] == [19., 40.]
    assert changed[0]['available'] is True
    assert changed[0]['transfer_split'] == 'test'
    assert rows[0]['available'] is False
    assert rows[0]['transfer_split'] is None


def test_reference_uncertainty_is_excluded_without_changing_source():
    truth = dict(domain_labels=np.ones((2, 2), int), evaluation_valid=np.ones((2, 2), bool),
                 boundary_uncertain=np.array([[True, False], [False, False]]),
                 boundary_unscored=np.array([[False, False], [True, False]]))
    assert np.array_equal(valid_reference(truth), [[False, True], [False, True]])
    assert truth['evaluation_valid'].all()
    assert valid_reference({}) is None
