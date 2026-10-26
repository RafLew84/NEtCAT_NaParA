#!/usr/bin/env bash
# Reproduce issue18 from an existing audited analysis tree, into a NEW directory.
set -euo pipefail
analysis=${1:?source analysis directory}
assets=${2:?local model assets directory}
out=${3:?new output directory}
netcat_python=${NETCAT_PYTHON:-/home/rlew/projekty/conda-migration-ubuntu-20261008/envs/netcat/bin/python}
device=${FEATURE_DEVICE:-cuda}
export CUBLAS_WORKSPACE_CONFIG=:4096:8
"$netcat_python" - "$analysis" "$out" <<'PY'
from pathlib import Path
import json,shutil,sys
from stmdomains.experiments.frozen.extract import PILOT
from stmdomains.experiments.bundle import write_json
src,out=map(Path,sys.argv[1:]);out.mkdir(parents=True,exist_ok=False)
m=json.loads((src/'manifest.json').read_text());m['samples']=[r for r in m['samples'] if r['sample_id'] in PILOT]
assert len(m['samples'])==len(PILOT)
for r in m['samples']:
 p=out/'input/analysis'/r['file'];p.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(src/r['file'],p)
write_json(out/'input/analysis/manifest.json',m)
PY
"$netcat_python" -m stmdomains.experiments.frozen.assets --out "$assets"
"$netcat_python" -m stmdomains.experiments.frozen.extract --analysis "$out/input/analysis" --assets "$assets" --out "$out" --device "$device"
"$netcat_python" -m stmdomains.experiments.frozen.verify --root "$out" --assets "$assets" --device "$device"
"$netcat_python" -m stmdomains.experiments.frozen.preview --root "$out"
