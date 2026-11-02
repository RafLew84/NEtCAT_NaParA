"""Reject saved MatchAnything evidence that contradicts the declared model."""
from dataclasses import replace
import json

import pytest

from stmviewer.session_metadata import decode_session, encode_session
from stmviewer.session_state import SessionState, SessionViewState
from test_manual_movie import cpu_result
from test_matchanything_session import matchanything_evidence, matchanything_graph


def test_matchanything_cannot_be_relabelled_as_standard_efficientloftr():
    base = cpu_result()
    evidence = matchanything_evidence(shape=base.frames[0].original.data.shape)
    relabelled = replace(base, method='EfficientLoFTR', correspondence_diagnostics=(None, evidence, None))
    with pytest.raises(ValueError, match='model|metod'):
        encode_session(SessionState(tuple(f.original for f in base.frames), relabelled))


def test_matchanything_controls_cannot_be_disguised_as_an_older_session_schema():
    from pathlib import Path
    from stmviewer.deep_matcher import DeepMatcherOptions
    frames = tuple(frame.original for frame in cpu_result().frames)
    display = SessionViewState(matchanything_options=DeepMatcherOptions(Path('/absent/model.ckpt')))
    manifest, arrays = encode_session(SessionState(frames, display=display))
    manifest['schema'] = 'stmviewer-state-v6'
    with pytest.raises(ValueError, match='v7|V7'):
        decode_session(manifest, arrays)
