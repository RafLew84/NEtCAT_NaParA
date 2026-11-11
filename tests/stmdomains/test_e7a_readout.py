from stmdomains.experiments.e7a_readout import comparison


def test_lower_merge_with_coverage_loss_is_tradeoff():
    base = dict(coverage=.8, merge=.4, split=.2, false_zero_rate=None)
    trial = dict(base, coverage=.4, merge=.1)
    assert comparison(base, trial)['status'] == 'tradeoff_or_worse'


def test_missing_pair_denominator_is_not_zero_error():
    base = dict(coverage=.2, merge=None, split=.2, false_zero_rate=None)
    trial = dict(base, coverage=.8, merge=.1)
    actual = comparison(base, trial)
    assert actual['status'] == 'incomplete_comparison' and actual['missing'] == ['merge']
    assert comparison(base, base)['status'] == 'unchanged_observed_metrics'
