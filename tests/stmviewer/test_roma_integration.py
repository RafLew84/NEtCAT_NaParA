"""RoMa reaches the same application entry points with explicit resource failures."""
from pathlib import Path

import pytest

from stmviewer.deep_matcher import DeepMatcherOptions
from stmviewer.graph_registration import register_graph
from stmviewer.pair_comparison import estimate_pair
from stmviewer.registration import RegistrationError, register_series
from stmviewer.series import open_frame_series


@pytest.mark.parametrize('route', ['pair', 'series', 'graph'])
def test_roma_missing_interpreter_has_one_explicit_reason_in_all_routes(tmp_path, route):
    frames = open_frame_series([Path(__file__).parent / 'fixtures/registration/cpu.mpp'])[:3]
    options = DeepMatcherOptions(interpreter=tmp_path / 'missing-python')
    with pytest.raises(RegistrationError, match='[Ii]nterpreter'):
        if route == 'pair':
            estimate_pair(frames[0], frames[1], method='roma_v2', deep_options=options)
        elif route == 'series':
            register_series(frames, method='roma_v2', deep_options=options)
        else:
            register_graph(frames, method='roma_v2', deep_options=options)
