import sys
import textwrap
import threading
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from nanotrack.subprocess_utils import CancellableSubprocessRunner, SubprocessCancelledError


def _write_worker_script(path: Path, body: str) -> None:
    path.write_text(textwrap.dedent(body), encoding="utf-8")


class CancellableSubprocessRunnerTests(unittest.TestCase):
    def test_cancel_terminates_running_subprocess(self) -> None:
        with TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            worker_script = temp_path / "sleep_worker.py"
            marker_path = temp_path / "started.txt"
            _write_worker_script(
                worker_script,
                f"""
                from pathlib import Path
                import time

                Path({str(marker_path)!r}).write_text("started", encoding="utf-8")
                time.sleep(30.0)
                """,
            )
            runner = CancellableSubprocessRunner()
            errors: list[BaseException] = []

            def run_worker() -> None:
                try:
                    runner.run([sys.executable, str(worker_script)], cwd=str(temp_path), timeout=60.0)
                except BaseException as exc:
                    errors.append(exc)

            thread = threading.Thread(target=run_worker)
            thread.start()
            for _ in range(200):
                if marker_path.exists():
                    break
                thread.join(timeout=0.01)
            self.assertTrue(marker_path.exists())

            runner.cancel()
            thread.join(timeout=5.0)

            self.assertFalse(thread.is_alive())
            self.assertEqual(len(errors), 1)
            self.assertIsInstance(errors[0], SubprocessCancelledError)


if __name__ == "__main__":
    unittest.main()
