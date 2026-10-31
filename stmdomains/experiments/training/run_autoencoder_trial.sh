#!/usr/bin/env bash
# Research comparison21. Large artifacts stay local, outside version control.
set -euo pipefail

PREPARED_INPUT=${1:-.scratch/training-20}
TRIAL_OUTPUT=${2:-.scratch/autoencoder-21-repeat}
REFERENCE_INPUT=${3:-.scratch/unsupervised-input/evaluation}
NETCAT_PYTHON=${NETCAT_PYTHON:-/home/rlew/projekty/conda-migration-ubuntu-20261008/envs/netcat/bin/python}
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 CUBLAS_WORKSPACE_CONFIG=:4096:8

if [[ -e "$TRIAL_OUTPUT" ]]; then
    echo "Use a new output directory: $TRIAL_OUTPUT" >&2
    exit 1
fi
mkdir -p "$TRIAL_OUTPUT"

"$NETCAT_PYTHON" -m stmdomains.experiments.training.resume_check \
    --data "$PREPARED_INPUT" --out "$TRIAL_OUTPUT/training-resume"
"$NETCAT_PYTHON" -m stmdomains.experiments.training.fit \
    --data "$PREPARED_INPUT" --out "$TRIAL_OUTPUT/training"
for TRIAL_STAGE in cache encode partition freeze; do
    "$NETCAT_PYTHON" -m stmdomains.experiments.training.predict "$TRIAL_STAGE" \
        --prepared "$PREPARED_INPUT" --output "$TRIAL_OUTPUT"
done
# The evaluation trees are first handed to a process after the freeze above.
"$NETCAT_PYTHON" -m stmdomains.experiments.training.evaluate \
    --predictions "$TRIAL_OUTPUT" \
    --controls-evaluation "$PREPARED_INPUT/controls/evaluation" \
    --measurement-evaluation "$REFERENCE_INPUT" --out "$TRIAL_OUTPUT/evaluation"
"$NETCAT_PYTHON" -m stmdomains.experiments.training.diagnostics \
    --output "$TRIAL_OUTPUT" --evaluation "$PREPARED_INPUT/controls/evaluation"
"$NETCAT_PYTHON" -m stmdomains.experiments.training.gallery --output "$TRIAL_OUTPUT" \
    --control-manifest "$PREPARED_INPUT/controls/evaluation/manifest.json"
"$NETCAT_PYTHON" -m stmdomains.experiments.training.figures --output "$TRIAL_OUTPUT"
"$NETCAT_PYTHON" -m stmdomains.experiments.training.summarize_trial \
    --output "$TRIAL_OUTPUT" --manifest "$TRIAL_OUTPUT/evidence.json"
