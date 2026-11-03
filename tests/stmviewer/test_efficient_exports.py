"""EfficientLoFTR provenance follows the exported measurement pixels."""
import json
from dataclasses import replace

import numpy as np
import pytest

from stmviewer.mpp import open_mpp_series
from stmviewer.mpp_export import save_aligned_mpp
from test_efficient_session import evidence
from test_manual_movie import cpu_result, corrected_trial
from stmviewer.manual_movie import apply_movie_correction


@pytest.mark.parametrize('manual', [False, True])
@pytest.mark.parametrize('finite_fill', [False, True])
def test_chain_export_keeps_model_provenance_after_manual_edit(tmp_path, manual, finite_fill):
    base = cpu_result()
    diagnostics = (None, evidence(shape=base.frames[0].original.data.shape),
                   evidence((-3., 2.), shape=base.frames[0].original.data.shape))
    base = replace(base, method='EfficientLoFTR', correspondence_diagnostics=diagnostics)
    corrected = apply_movie_correction(base, corrected_trial(base, 1, 1, 0)) if manual else base
    path = tmp_path / 'efficient-corrected.mpp'
    save_aligned_mpp(path, corrected, wsxm_compatible=finite_fill)
    reopened = open_mpp_series(path, check_cancelled=lambda: None)
    assert reopened[1].alignment.correspondence == diagnostics[1]
    for expected, actual in zip(corrected.frames, reopened, strict=True):
        np.testing.assert_array_equal(actual.data, expected.image.data)
        assert actual.alignment.shift_xy == expected.shift_xy
    metadata = json.loads(path.with_name(path.name + '.stmviewer.json').read_text())
    assert metadata['version'] == 8
