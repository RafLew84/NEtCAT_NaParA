#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 4 ]]; then
  echo "Usage: bash run_preparation.sh ANALYSIS_DIR MPP SESSION_JSON NEW_OUTPUT_DIR" >&2
  exit 2
fi
netcat_python=${NETCAT_PYTHON:-/home/rlew/projekty/conda-migration-ubuntu-20261008/envs/netcat/bin/python}
analysis=$1
mpp=$2
session=$3
out=$4
if [[ -e "$out" ]]; then
  echo "Output directory already exists: $out" >&2
  exit 2
fi
mkdir -p "$out"
"$netcat_python" -m stmdomains.experiments.training.prepare --analysis "$analysis" --out "$out/data"
"$netcat_python" -m stmdomains.experiments.training.controls --out "$out/controls"
"$netcat_python" -m stmdomains.experiments.training.verify --root "$out/data" --analysis "$analysis" --replay "$out/verification-replay" --mpp "$mpp" --session "$session"
"$netcat_python" -m stmdomains.experiments.training.gpu_probe --batch "$out/data/gpu-batch.npz" --out "$out/gpu" --device cuda
"$netcat_python" -m stmdomains.experiments.training.summarize --root "$out"
