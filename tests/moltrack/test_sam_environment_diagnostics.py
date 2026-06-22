import tempfile
import unittest
from pathlib import Path
from subprocess import CompletedProcess

from moltrack.diagnostics.sam_environment import (
    build_sam_environment_report,
    discover_sam2_checkpoints,
    probe_python_executable,
    run_fast_sam_contract_smoke,
)


class SamEnvironmentDiagnosticsTests(unittest.TestCase):
    def test_fast_environment_report_checks_paths_checkpoints_and_contracts_without_gpu(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            sam2_env = root / "envs" / "sam2" / "python.exe"
            sam3_env = root / "envs" / "sam3" / "python.exe"
            sam2_checkpoints = root / "checkpoints" / "sam2"
            sam2_repo = root / "repos" / "sam2"
            sam3_repo = root / "repos" / "sam3"
            sam3_transformers_worker = root / "workers" / "run_sam3_subprocess.py"
            sam31_official_worker = root / "workers" / "run_sam31_official_subprocess.py"
            hf_cache = root / "hf"
            for path in (
                sam2_env.parent,
                sam3_env.parent,
                sam2_checkpoints,
                sam2_repo,
                sam3_repo,
                sam3_transformers_worker.parent,
                hf_cache,
            ):
                path.mkdir(parents=True, exist_ok=True)
            sam2_env.write_text("python", encoding="utf-8")
            sam3_env.write_text("python", encoding="utf-8")
            sam3_transformers_worker.write_text("worker", encoding="utf-8")
            sam31_official_worker.write_text("worker", encoding="utf-8")
            (sam2_checkpoints / "sam2.1_hiera_base_plus.pt").write_bytes(b"fake")
            (sam2_checkpoints / "sam2.1_hiera_large.pt").write_bytes(b"fake")

            checkpoints = discover_sam2_checkpoints(sam2_checkpoints)
            report = build_sam_environment_report(
                sam2_python=sam2_env,
                sam2_checkpoint_dir=sam2_checkpoints,
                sam2_repo_path=sam2_repo,
                sam3_python=sam3_env,
                sam3_repo_path=sam3_repo,
                sam3_transformers_worker=sam3_transformers_worker,
                sam31_official_worker=sam31_official_worker,
                hf_cache_dir=hf_cache,
            )
            contract_report = run_fast_sam_contract_smoke(root / "contracts")

        self.assertEqual([checkpoint.name for checkpoint in checkpoints], ["sam2.1_hiera_base_plus.pt", "sam2.1_hiera_large.pt"])
        self.assertTrue(report.ok, report.to_text())
        self.assertIn("SAM2 checkpoints: 2 found", report.to_text())
        self.assertTrue(contract_report.ok, contract_report.to_text())
        self.assertIn("SAM2 contract round-trip", contract_report.to_text())
        self.assertIn("SAM3 contract round-trip", contract_report.to_text())

    def test_python_probe_reports_wsl_vsock_failure_as_warning_not_error(self) -> None:
        def fake_run(*_args, **_kwargs):
            return CompletedProcess(
                args=["sam3/python.exe", "--version"],
                returncode=1,
                stdout="",
                stderr="UtilBindVsockAnyPort failed: socket unavailable",
            )

        result = probe_python_executable("C:/Users/rlewa/anaconda3/envs/sam3/python.exe", subprocess_run=fake_run)

        self.assertEqual(result.severity, "warning")
        self.assertTrue(result.ok)
        self.assertIn("UtilBindVsockAnyPort", result.message)


if __name__ == "__main__":
    unittest.main()
