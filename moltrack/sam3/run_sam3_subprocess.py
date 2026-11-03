from __future__ import annotations

import importlib.util
from pathlib import Path


def _load_worker_main():
    worker_path = Path(__file__).with_name("subprocess_worker.py")
    spec = importlib.util.spec_from_file_location("moltrack_sam3_subprocess_worker", worker_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load SAM3 worker module: {worker_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.main


main = _load_worker_main()

if __name__ == "__main__":
    raise SystemExit(main(default_version="sam3", default_backend="transformers_sam3"))
