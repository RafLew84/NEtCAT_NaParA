"""Closing with active work must exit cleanly, including Qt object destruction."""

import os
from pathlib import Path
import subprocess
import sys

import pytest

from stmdomains.tools.browsing_demo import create_browsing_demo


@pytest.mark.parametrize("work", ["import", "thumbnail"])
@pytest.mark.parametrize("exit_method", ["window", "application"])
def test_exit_waits_for_background_work_before_destroying_qt(tmp_path, work, exit_method):
    session = create_browsing_demo(tmp_path)["series"]
    root = Path(__file__).resolve().parents[2]
    environment = dict(os.environ, PYTHONPATH=str(root))
    environment.setdefault("QT_QPA_PLATFORM", "offscreen")
    process = subprocess.run(
        [sys.executable, str(Path(__file__).with_name("qt_shutdown_process.py")),
         str(session), work, exit_method],
        cwd=root, env=environment, capture_output=True, text=True, timeout=10,
    )
    assert process.returncode == 0, process.stdout + process.stderr
    assert "Traceback" not in process.stderr
