"""Scientific guardrails for post-freeze local SSL diagnostics."""
import numpy as np

from stmdomains.experiments.training.local_ssl.diagnostics import interior_separation, pure_support_label
from stmdomains.experiments.training.local_ssl.gallery import document_template


def test_pure_support_excludes_crossing_and_unknown_regions():
    truth = dict(domain_labels=np.ones((20, 20), dtype=int), evaluation_valid=np.ones((20, 20), dtype=bool))
    truth["domain_labels"][:, 10:] = 2
    row = dict(available=True, support_xyxy=[2, 2, 9, 9])
    assert pure_support_label(row, truth) == 1
    assert pure_support_label(dict(row, support_xyxy=[8, 2, 12, 9]), truth) == 0
    truth["evaluation_valid"][4, 4] = False
    assert pure_support_label(row, truth) == 0
    assert pure_support_label(dict(row, available=False), truth) == 0


def test_separation_does_not_score_missing_parts_or_flat_descriptors():
    flat = np.ones((5, 4))
    result = interior_separation(flat, [1, 1, 2, 2, 0])
    assert result["squared_centroid_distance"] == 0
    assert result["separation_ratio"] is None
    assert interior_separation(flat, [1, 1, 1, 1, 1])["squared_centroid_distance"] is None


def test_separation_is_invariant_to_positive_descriptor_amplitude():
    features = np.array([[1., .1], [1., -.1], [.1, 1.], [-.1, 1.]])
    labels = [1, 1, 2, 2]
    first = interior_separation(features, labels)
    second = interior_separation(features * np.array([1., 3., 10., 2.])[:, None], labels)
    assert np.isclose(first["separation_ratio"], second["separation_ratio"])


def test_gallery_retains_regimes_and_identifies_untrained_control():
    template = document_template()
    assert 'value="transductive"' in template
    assert "local_ssl_untrained" in template
    for scenario in ("phase", "missing", "artifact"):
        assert f'id="scenario-{scenario}"' in template
    assert "eksperyment 22" in template
    assert "próba AE / rVAE" not in template
