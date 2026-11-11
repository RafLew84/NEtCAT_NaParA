import numpy as np

from stmdomains.experiments.e7_metrics import relation_metrics


def test_relations_exclude_unknown_and_preserve_missing_class():
    result = relation_metrics(np.array([.1, .2, .99]), np.array([True, True, False]),
                              np.array([True, True, False]), classifier=True)
    assert result['counts']['scored_pairs'] == 2
    assert result['roc_auc'] is None
    assert result['average_precision'] is None
    assert result['fixed_threshold']['balanced_accuracy'] is None
    assert result['fixed_threshold']['same_recall'] == 1


def test_threshold_and_rank_are_distinct_and_denominators_explicit():
    result = relation_metrics(np.array([.1, .6, .5, .9]), np.array([True, True, False, False]),
                              np.ones(4, bool), classifier=True)
    assert result['roc_auc'] == .75
    assert result['fixed_threshold']['tp'] == 2
    assert result['fixed_threshold']['fp'] == 1
    assert result['fixed_threshold']['balanced_accuracy'] == .75
    historical = relation_metrics(np.array([1., 2.]), np.array([True, False]),
                                  np.ones(2, bool))
    assert historical['roc_auc'] == 1
    assert historical['fixed_threshold'] is None
