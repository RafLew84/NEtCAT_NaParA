import tempfile
import unittest
from pathlib import Path

from moltrack.sam2 import discover_sam2_checkpoints, select_default_sam2_checkpoint


class Sam2CheckpointDiscoveryTests(unittest.TestCase):
    def test_discovers_four_sam2_checkpoints_and_prefers_base_plus(self) -> None:
        names = [
            "sam2.1_hiera_base_plus.pt",
            "sam2.1_hiera_large.pt",
            "sam2.1_hiera_small.pt",
            "sam2.1_hiera_tiny.pt",
        ]
        with tempfile.TemporaryDirectory() as tmpdir:
            checkpoint_dir = Path(tmpdir)
            for name in names:
                (checkpoint_dir / name).write_bytes(b"checkpoint")
            (checkpoint_dir / "notes.txt").write_text("not a checkpoint", encoding="utf-8")

            checkpoints = discover_sam2_checkpoints(checkpoint_dir)

        self.assertEqual([checkpoint.name for checkpoint in checkpoints], names)
        self.assertEqual(select_default_sam2_checkpoint(checkpoints).name, "sam2.1_hiera_base_plus.pt")


if __name__ == "__main__":
    unittest.main()
