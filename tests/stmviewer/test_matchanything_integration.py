"""Public registration entry points identify the separate model and fail explicitly."""
import pytest
from stmviewer.deep_matcher import DeepMatcherOptions


def test_matchanything_is_a_separate_method_with_explicit_graph_unavailability(tmp_path):
    from stmviewer.registration import REGISTRATION_METHODS, DEEP_METHODS
    from stmviewer.graph_methods import graph_unavailable_reason
    assert REGISTRATION_METHODS['matchanything_eloftr'] == 'MatchAnything-ELoFTR'
    assert 'matchanything_eloftr' in DEEP_METHODS
    reason = graph_unavailable_reason('matchanything_eloftr', DeepMatcherOptions(source=tmp_path))
    assert 'kod MatchAnything' in reason
