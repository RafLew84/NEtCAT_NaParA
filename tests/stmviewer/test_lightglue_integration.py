"""Registration entry points preserve LightGlue identity and explicit availability."""
from stmviewer.deep_matcher import DeepMatcherOptions


def test_lightglue_is_separate_method_and_graph_reports_its_missing_source(tmp_path):
    from stmviewer.registration import REGISTRATION_METHODS, DEEP_METHODS
    from stmviewer.graph_methods import graph_unavailable_reason
    assert REGISTRATION_METHODS['lightglue_superpoint'] == 'LightGlue + SuperPoint'
    assert 'lightglue_superpoint' in DEEP_METHODS
    reason = graph_unavailable_reason('lightglue_superpoint', DeepMatcherOptions(source=tmp_path))
    assert reason is not None and 'kod' in reason.lower() and 'LightGlue' in reason
