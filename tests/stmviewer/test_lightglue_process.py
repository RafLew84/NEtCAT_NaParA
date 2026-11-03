"""External worker lifecycle for the same-interpreter LightGlue adapter."""

from pathlib import Path
import sys

import pytest
from stmviewer.registration import RegistrationError
from stmviewer.roma_process import RomaProcess


def test_worker_failures_identify_lightglue_not_roma(tmp_path):
    script = tmp_path / 'broken_worker.py'
    script.write_text('''import json,sys
request=json.loads(sys.stdin.readline())
print(json.dumps({'version':1, 'id':request['id'], 'kind':'error', 'message':'brak CUDA'}),flush=True)
''')
    with pytest.raises(RegistrationError, match='LightGlue') as error:
        RomaProcess(Path(sys.executable), {'samples':2048, 'device':'cuda'},
                    worker_script=script, model_label='LightGlue + SuperPoint', temp_prefix='stmviewer-lightglue-')
    assert 'RoMa' not in str(error.value)
    assert 'brak CUDA' in str(error.value)
