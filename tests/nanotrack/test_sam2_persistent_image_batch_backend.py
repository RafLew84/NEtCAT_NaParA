import sys
import textwrap
import threading
import time
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

import numpy as np

from nanotrack.sam2 import (
    Sam2ImageBatchInput,
    Sam2PersistentImageBatchBackend,
    Sam2PersistentImageBatchBackendConfig,
    Sam2PersistentImageBatchBackendError,
    Sam2PersistentImageBatchCancelledError,
    Sam2PersistentImageBatchProtocolError,
    Sam2PersistentImageBatchTimeoutError,
)


def _write_worker_script(path: Path, source: str) -> None:
    path.write_text(textwrap.dedent(source), encoding="utf-8")


class Sam2PersistentImageBatchBackendTests(unittest.TestCase):
    def _make_input(self, frame_index: int, detection_id: str) -> Sam2ImageBatchInput:
        return Sam2ImageBatchInput(
            frame=np.arange(48, dtype=np.float32).reshape(6, 8),
            frame_index=frame_index,
            source_view="raw",
            boxes_xyxy=np.asarray(((1.0, 1.0, 4.0, 4.0),), dtype=np.float32),
            prompt_detection_ids=(detection_id,),
            chunk_size=16,
        )

    def test_one_ready_worker_handles_multiple_frames_with_one_model_load(self) -> None:
        with TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            worker_script = temp_path / "fake_persistent_worker.py"
            events_path = temp_path / "events.txt"
            _write_worker_script(
                worker_script,
                """
                import argparse
                import json
                from pathlib import Path
                import sys

                import numpy as np

                parser = argparse.ArgumentParser()
                parser.add_argument("--checkpoint", required=True)
                parser.add_argument("--repo-path", required=True)
                parser.add_argument("--config", required=True)
                parser.add_argument("--device", required=True)
                parser.add_argument("--apply-postprocessing", action="store_true")
                parser.add_argument("--disable-postprocessing", action="store_true")
                args = parser.parse_args()

                assert args.checkpoint == "selected-checkpoint.pt"
                assert args.repo_path == "sam2-repo"
                assert args.config == "configs/sam2.1/model.yaml"
                assert args.device == "cuda:0"
                assert args.apply_postprocessing
                events = Path("events.txt")
                events.write_text("model_loaded\\n", encoding="utf-8")
                print(json.dumps({"protocol_version": 1, "type": "ready"}), flush=True)

                for line in sys.stdin:
                    message = json.loads(line)
                    if message["type"] == "close":
                        with events.open("a", encoding="utf-8") as stream:
                            stream.write("close\\n")
                        break

                    with np.load(message["input_npz"], allow_pickle=False) as payload:
                        frame_index = payload["frame_index"].copy()
                        source_view = payload["source_view"].copy()
                        prompt_ids = payload["prompt_detection_ids"].copy()
                        contract_version = payload["contract_version"].copy()
                        frame = payload["frame"]
                    with events.open("a", encoding="utf-8") as stream:
                        stream.write(f"frame:{int(frame_index)}\\n")

                    mask = np.zeros((1, *frame.shape[:2]), dtype=np.uint8)
                    mask[0, 1:3, 2:4] = 1
                    np.savez_compressed(
                        message["output_npz"],
                        contract_version=contract_version,
                        frame_index=frame_index,
                        source_view=source_view,
                        prompt_detection_ids=prompt_ids,
                        masks=mask,
                        mask_scores=np.asarray((0.9,), dtype=np.float32),
                        mask_bboxes_xyxy=np.asarray(((2.0, 1.0, 4.0, 3.0),), dtype=np.float32),
                        mask_component_counts=np.asarray((1,), dtype=np.int64),
                    )
                    print(json.dumps({
                        "protocol_version": 1,
                        "type": "frame_result",
                        "request_id": message["request_id"],
                        "output_npz": message["output_npz"],
                    }), flush=True)
                """,
            )
            backend = Sam2PersistentImageBatchBackend(
                Sam2PersistentImageBatchBackendConfig(
                    python_executable=sys.executable,
                    worker_script=worker_script,
                    checkpoint_path="selected-checkpoint.pt",
                    repo_path="sam2-repo",
                    config_path="configs/sam2.1/model.yaml",
                    device="cuda:0",
                    startup_timeout_sec=5.0,
                    frame_timeout_sec=5.0,
                    working_directory=temp_path,
                )
            )

            with backend.open_session() as session:
                process_id = session.process_id
                self.assertTrue(session.is_running)
                first = session.segment_frame(self._make_input(2, "bbox-2"))
                second = session.segment_frame(self._make_input(5, "bbox-5"))
                self.assertEqual(session.process_id, process_id)

            self.assertFalse(session.is_running)
            self.assertEqual(first.frame_index, 2)
            self.assertEqual(first.prompt_detection_ids, ("bbox-2",))
            self.assertEqual(second.frame_index, 5)
            self.assertEqual(second.prompt_detection_ids, ("bbox-5",))
            self.assertEqual(
                events_path.read_text(encoding="utf-8").splitlines(),
                ["model_loaded", "frame:2", "frame:5", "close"],
            )

    def test_second_frame_is_not_sent_until_first_frame_result_is_received(self) -> None:
        with TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            worker_script = temp_path / "backpressure_worker.py"
            events_path = temp_path / "events.txt"
            _write_worker_script(
                worker_script,
                """
                import argparse
                import json
                from pathlib import Path
                from queue import Empty, Queue
                import sys
                from threading import Thread
                import time

                import numpy as np

                parser = argparse.ArgumentParser()
                parser.add_argument("--checkpoint")
                parser.add_argument("--device")
                parser.add_argument("--apply-postprocessing", action="store_true")
                parser.add_argument("--disable-postprocessing", action="store_true")
                parser.parse_args()

                messages = Queue()
                def read_messages():
                    for line in sys.stdin:
                        messages.put(json.loads(line))
                Thread(target=read_messages, daemon=True).start()

                events = Path("events.txt")
                events.write_text("", encoding="utf-8")
                print(json.dumps({"protocol_version": 1, "type": "ready"}), flush=True)
                while True:
                    message = messages.get()
                    if message["type"] == "close":
                        break
                    request_id = message["request_id"]
                    with events.open("a", encoding="utf-8") as stream:
                        stream.write(f"start:{request_id}\\n")
                    time.sleep(0.25)
                    try:
                        early = messages.get_nowait()
                    except Empty:
                        early = None
                    if early is not None:
                        with events.open("a", encoding="utf-8") as stream:
                            stream.write(f"early:{early['request_id']}\\n")
                        messages.put(early)

                    with np.load(message["input_npz"], allow_pickle=False) as payload:
                        frame_index = payload["frame_index"].copy()
                        source_view = payload["source_view"].copy()
                        prompt_ids = payload["prompt_detection_ids"].copy()
                        version = payload["contract_version"].copy()
                        shape = payload["frame"].shape[:2]
                    np.savez_compressed(
                        message["output_npz"],
                        contract_version=version,
                        frame_index=frame_index,
                        source_view=source_view,
                        prompt_detection_ids=prompt_ids,
                        masks=np.zeros((1, *shape), dtype=np.uint8),
                        mask_scores=np.asarray((0.5,), dtype=np.float32),
                        mask_bboxes_xyxy=np.zeros((1, 4), dtype=np.float32),
                        mask_component_counts=np.zeros((1,), dtype=np.int64),
                    )
                    with events.open("a", encoding="utf-8") as stream:
                        stream.write(f"result:{request_id}\\n")
                    print(json.dumps({
                        "protocol_version": 1,
                        "type": "frame_result",
                        "request_id": request_id,
                        "output_npz": message["output_npz"],
                    }), flush=True)
                """,
            )
            backend = Sam2PersistentImageBatchBackend(
                Sam2PersistentImageBatchBackendConfig(
                    python_executable=sys.executable,
                    worker_script=worker_script,
                    checkpoint_path="checkpoint.pt",
                    repo_path=None,
                    startup_timeout_sec=5.0,
                    frame_timeout_sec=5.0,
                    working_directory=temp_path,
                )
            )
            results = []
            errors = []

            with backend.open_session() as session:
                first_thread = threading.Thread(
                    target=lambda: self._capture_result(
                        session,
                        self._make_input(2, "bbox-2"),
                        results,
                        errors,
                    )
                )
                second_thread = threading.Thread(
                    target=lambda: self._capture_result(
                        session,
                        self._make_input(5, "bbox-5"),
                        results,
                        errors,
                    )
                )
                first_thread.start()
                deadline = time.monotonic() + 2.0
                while "start:frame-1" not in events_path.read_text(encoding="utf-8"):
                    self.assertLess(time.monotonic(), deadline)
                    time.sleep(0.01)
                second_thread.start()
                first_thread.join(timeout=3.0)
                second_thread.join(timeout=3.0)

            self.assertFalse(first_thread.is_alive())
            self.assertFalse(second_thread.is_alive())
            self.assertEqual(errors, [])
            self.assertEqual(sorted(result.frame_index for result in results), [2, 5])
            self.assertEqual(
                events_path.read_text(encoding="utf-8").splitlines(),
                [
                    "start:frame-1",
                    "result:frame-1",
                    "start:frame-2",
                    "result:frame-2",
                ],
            )

    def test_malformed_frame_response_is_reported_and_session_files_are_removed(self) -> None:
        with TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            worker_script = temp_path / "malformed_worker.py"
            _write_worker_script(
                worker_script,
                """
                import argparse
                import json
                import sys

                parser = argparse.ArgumentParser()
                parser.add_argument("--checkpoint")
                parser.add_argument("--device")
                parser.add_argument("--apply-postprocessing", action="store_true")
                parser.add_argument("--disable-postprocessing", action="store_true")
                parser.parse_args()
                print(json.dumps({"protocol_version": 1, "type": "ready"}), flush=True)
                for line in sys.stdin:
                    message = json.loads(line)
                    if message["type"] == "close":
                        break
                    print("not-json", flush=True)
                """,
            )
            backend = Sam2PersistentImageBatchBackend(
                Sam2PersistentImageBatchBackendConfig(
                    python_executable=sys.executable,
                    worker_script=worker_script,
                    checkpoint_path="checkpoint.pt",
                    repo_path=None,
                    startup_timeout_sec=5.0,
                    frame_timeout_sec=5.0,
                    working_directory=temp_path,
                )
            )

            with backend.open_session() as session:
                session_temp_path = session.temporary_directory
                self.assertTrue(session_temp_path.exists())
                with self.assertRaisesRegex(
                    Sam2PersistentImageBatchProtocolError,
                    "malformed JSON",
                ):
                    session.segment_frame(self._make_input(2, "bbox-2"))

            self.assertFalse(session_temp_path.exists())

    def test_worker_exit_reports_exit_code_and_stderr_without_waiting_for_timeout(self) -> None:
        with TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            worker_script = temp_path / "broken_worker.py"
            _write_worker_script(
                worker_script,
                """
                import argparse
                import json
                import sys

                parser = argparse.ArgumentParser()
                parser.add_argument("--checkpoint")
                parser.add_argument("--device")
                parser.add_argument("--apply-postprocessing", action="store_true")
                parser.add_argument("--disable-postprocessing", action="store_true")
                parser.parse_args()
                print(json.dumps({"protocol_version": 1, "type": "ready"}), flush=True)
                json.loads(sys.stdin.readline())
                sys.stderr.write("checkpoint exploded\\n")
                sys.stderr.flush()
                raise SystemExit(7)
                """,
            )
            backend = Sam2PersistentImageBatchBackend(
                Sam2PersistentImageBatchBackendConfig(
                    python_executable=sys.executable,
                    worker_script=worker_script,
                    checkpoint_path="checkpoint.pt",
                    repo_path=None,
                    startup_timeout_sec=5.0,
                    frame_timeout_sec=5.0,
                    working_directory=temp_path,
                )
            )

            started_at = time.monotonic()
            with backend.open_session() as session:
                with self.assertRaises(Sam2PersistentImageBatchBackendError) as context:
                    session.segment_frame(self._make_input(2, "bbox-2"))
            elapsed = time.monotonic() - started_at

            self.assertLess(elapsed, 2.0)
            self.assertIn("Exit code: 7", str(context.exception))
            self.assertIn("checkpoint exploded", str(context.exception))

    def test_frame_timeout_stops_worker_and_removes_session_files(self) -> None:
        with TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            worker_script = temp_path / "hanging_worker.py"
            _write_worker_script(
                worker_script,
                """
                import argparse
                import json
                import sys
                import time

                parser = argparse.ArgumentParser()
                parser.add_argument("--checkpoint")
                parser.add_argument("--device")
                parser.add_argument("--apply-postprocessing", action="store_true")
                parser.add_argument("--disable-postprocessing", action="store_true")
                parser.parse_args()
                print(json.dumps({"protocol_version": 1, "type": "ready"}), flush=True)
                json.loads(sys.stdin.readline())
                time.sleep(10.0)
                """,
            )
            backend = Sam2PersistentImageBatchBackend(
                Sam2PersistentImageBatchBackendConfig(
                    python_executable=sys.executable,
                    worker_script=worker_script,
                    checkpoint_path="checkpoint.pt",
                    repo_path=None,
                    startup_timeout_sec=5.0,
                    frame_timeout_sec=0.05,
                    close_timeout_sec=0.05,
                    working_directory=temp_path,
                )
            )

            started_at = time.monotonic()
            with backend.open_session() as session:
                session_temp_path = session.temporary_directory
                with self.assertRaisesRegex(
                    Sam2PersistentImageBatchTimeoutError,
                    "frame request frame-1.*0.050 s",
                ):
                    session.segment_frame(self._make_input(2, "bbox-2"))
            elapsed = time.monotonic() - started_at

            self.assertLess(elapsed, 1.0)
            self.assertFalse(session_temp_path.exists())

    def test_worker_error_message_is_reported_with_its_diagnostic(self) -> None:
        with TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            worker_script = temp_path / "error_message_worker.py"
            _write_worker_script(
                worker_script,
                """
                import argparse
                import json
                import sys

                parser = argparse.ArgumentParser()
                parser.add_argument("--checkpoint")
                parser.add_argument("--device")
                parser.add_argument("--apply-postprocessing", action="store_true")
                parser.add_argument("--disable-postprocessing", action="store_true")
                parser.parse_args()
                print(json.dumps({"protocol_version": 1, "type": "ready"}), flush=True)
                for line in sys.stdin:
                    message = json.loads(line)
                    if message["type"] == "close":
                        break
                    print(json.dumps({
                        "protocol_version": 1,
                        "type": "error",
                        "request_id": message["request_id"],
                        "message": "CUDA out of memory for frame 12",
                    }), flush=True)
                """,
            )
            backend = Sam2PersistentImageBatchBackend(
                Sam2PersistentImageBatchBackendConfig(
                    python_executable=sys.executable,
                    worker_script=worker_script,
                    checkpoint_path="checkpoint.pt",
                    repo_path=None,
                    startup_timeout_sec=5.0,
                    frame_timeout_sec=5.0,
                    working_directory=temp_path,
                )
            )

            with backend.open_session() as session:
                with self.assertRaisesRegex(
                    Sam2PersistentImageBatchBackendError,
                    "CUDA out of memory for frame 12",
                ):
                    session.segment_frame(self._make_input(12, "bbox-12"))

    def test_cancel_stops_active_worker_without_waiting_for_frame_timeout(self) -> None:
        with TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            worker_script = temp_path / "cancel_worker.py"
            started_path = temp_path / "started.txt"
            _write_worker_script(
                worker_script,
                """
                import argparse
                import json
                from pathlib import Path
                import sys
                import time

                parser = argparse.ArgumentParser()
                parser.add_argument("--checkpoint")
                parser.add_argument("--device")
                parser.add_argument("--apply-postprocessing", action="store_true")
                parser.add_argument("--disable-postprocessing", action="store_true")
                parser.parse_args()
                print(json.dumps({"protocol_version": 1, "type": "ready"}), flush=True)
                json.loads(sys.stdin.readline())
                Path("started.txt").write_text("started", encoding="utf-8")
                time.sleep(10.0)
                """,
            )
            backend = Sam2PersistentImageBatchBackend(
                Sam2PersistentImageBatchBackendConfig(
                    python_executable=sys.executable,
                    worker_script=worker_script,
                    checkpoint_path="checkpoint.pt",
                    repo_path=None,
                    startup_timeout_sec=5.0,
                    frame_timeout_sec=20.0,
                    close_timeout_sec=0.05,
                    working_directory=temp_path,
                )
            )
            errors = []

            started_at = time.monotonic()
            with backend.open_session() as session:
                run_thread = threading.Thread(
                    target=lambda: self._capture_result(
                        session,
                        self._make_input(2, "bbox-cancel"),
                        [],
                        errors,
                    )
                )
                run_thread.start()
                deadline = time.monotonic() + 2.0
                while not started_path.exists():
                    self.assertLess(time.monotonic(), deadline)
                    time.sleep(0.01)
                session.cancel()
                run_thread.join(timeout=2.0)

                self.assertFalse(run_thread.is_alive())
                self.assertFalse(session.is_running)

            self.assertLess(time.monotonic() - started_at, 2.0)
            self.assertEqual(len(errors), 1)
            self.assertIsInstance(errors[0], Sam2PersistentImageBatchCancelledError)

    def test_cancel_stops_worker_during_model_loading_before_ready(self) -> None:
        with TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            worker_script = temp_path / "loading_worker.py"
            started_path = temp_path / "loading.txt"
            _write_worker_script(
                worker_script,
                """
                import argparse
                from pathlib import Path
                import time

                parser = argparse.ArgumentParser()
                parser.add_argument("--checkpoint")
                parser.add_argument("--device")
                parser.add_argument("--apply-postprocessing", action="store_true")
                parser.add_argument("--disable-postprocessing", action="store_true")
                parser.parse_args()
                Path("loading.txt").write_text("loading", encoding="utf-8")
                time.sleep(10.0)
                """,
            )
            backend = Sam2PersistentImageBatchBackend(
                Sam2PersistentImageBatchBackendConfig(
                    python_executable=sys.executable,
                    worker_script=worker_script,
                    checkpoint_path="checkpoint.pt",
                    repo_path=None,
                    startup_timeout_sec=20.0,
                    close_timeout_sec=0.05,
                    working_directory=temp_path,
                )
            )
            session = backend.open_session()
            errors = []

            def enter_session() -> None:
                try:
                    with session:
                        pass
                except BaseException as error:
                    errors.append(error)

            started_at = time.monotonic()
            startup_thread = threading.Thread(target=enter_session)
            startup_thread.start()
            deadline = time.monotonic() + 2.0
            while not started_path.exists():
                self.assertLess(time.monotonic(), deadline)
                time.sleep(0.01)
            session.cancel()
            startup_thread.join(timeout=2.0)

            self.assertFalse(startup_thread.is_alive())
            self.assertLess(time.monotonic() - started_at, 2.0)
            self.assertEqual(len(errors), 1)
            self.assertIsInstance(errors[0], Sam2PersistentImageBatchCancelledError)

    @staticmethod
    def _capture_result(session, run_input, results, errors) -> None:
        try:
            results.append(session.segment_frame(run_input))
        except BaseException as error:
            errors.append(error)


if __name__ == "__main__":
    unittest.main()
