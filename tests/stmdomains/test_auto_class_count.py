"""Auto distinguishes compact classes from missing or ambiguous evidence."""

import numpy as np
import pytest

from stmdomains.analysis.automatic_classes import AutoSelectionUnavailable, fit_auto_model
from stmdomains.core.analysis_result import AnalysisCancelled


def choose(samples, maximum=8, active=None, check=lambda: None):
    return fit_auto_model(samples, maximum, check, active_count=len(samples) if active is None else active,
                          useful_count=len(samples))


def two_groups():
    rng = np.random.default_rng(21)
    samples = np.concatenate([rng.uniform(0, .03, (40, 8)) + np.eye(8)[i] for i in (0, 3)])
    return samples / np.linalg.norm(samples, axis=1)[:, None]


def test_constant_population_is_one_class_without_silhouette():
    model = choose(np.tile([1., 0., 0.], (30, 1)))
    decision = model["class_selection"]
    assert model["k"] == decision["selected_k"] == 1
    assert decision["mode"] == "auto" and decision["max_k"] == 8
    assert decision["ranking"][0]["silhouette"] is None
    assert decision["reason"] and decision["rule_version"]


def test_separated_populations_choose_two_repeatably_and_respect_maximum():
    samples = two_groups()
    first = choose(samples, 4)
    assert first == choose(samples, 4)
    assert first["k"] == 2
    assert [r["k"] for r in first["class_selection"]["ranking"]] == [1, 2, 3, 4]
    with pytest.raises(AutoSelectionUnavailable) as failure:
        choose(samples, 1)
    assert failure.value.decision["selected_k"] is None
    assert len(failure.value.decision["ranking"]) == 1


@pytest.mark.parametrize("count,active", [(0, 0), (19, 19), (30, 150)])
def test_insufficient_support_is_not_a_fallback_class(count, active):
    with pytest.raises(AutoSelectionUnavailable) as failure:
        choose(np.tile([1., 0.], (count, 1)), active=active)
    assert failure.value.decision["selected_k"] is None
    assert not failure.value.decision["ranking"]
    assert failure.value.decision["reason"]


def test_diffuse_population_remains_undetermined_instead_of_forced_partition():
    samples = np.random.default_rng(89).dirichlet(np.ones(32) * .15, size=180) ** .5
    with pytest.raises(AutoSelectionUnavailable) as failure:
        choose(samples)
    assert len(failure.value.decision["ranking"]) == 8
    assert all(not row["eligible"] for row in failure.value.decision["ranking"])


def test_auto_can_be_cancelled_and_validates_maximum():
    def stop():
        raise AnalysisCancelled()
    with pytest.raises(AnalysisCancelled):
        choose(two_groups(), check=stop)
    for maximum in (0, 9, True, 2.5):
        with pytest.raises(ValueError):
            choose(two_groups(), maximum)


def test_ranking_is_bounded_but_final_model_fits_all_available_samples():
    model = choose(np.tile(two_groups(), (20, 1)), maximum=2)
    decision = model["class_selection"]
    assert model["fit_count"] == decision["fit_count"] == 1600
    assert decision["ranking_count"] == 1200 and decision["final_validation"]["eligible"]
    assert sum(decision["final_validation"]["sizes"]) == 1600
    assert decision["selected_k"] == 2 and decision["at_upper_bound"]


def test_full_fit_validation_can_refuse_a_partition_accepted_on_the_subset():
    # Deterministic sampling omits these scattered outliers. The final check
    # must detect them instead of publishing the ranking decision blindly.
    samples = np.tile([1., 0.], (1600, 1))
    sampled = np.linspace(0, 1599, 1200, dtype=int)
    omitted = np.setdiff1d(np.arange(1600), sampled)
    samples[omitted] = [0., 1.]
    with pytest.raises(AutoSelectionUnavailable) as failure:
        choose(samples, maximum=1)
    decision = failure.value.decision
    assert decision["ranking"][0]["eligible"]
    assert not decision["final_validation"]["eligible"] and decision["selected_k"] is None
