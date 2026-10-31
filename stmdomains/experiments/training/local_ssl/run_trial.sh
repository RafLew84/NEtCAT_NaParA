#!/usr/bin/env bash
# Issue22 research reproduction; the output directory must be fresh.
set -euo pipefail
PREPARED_INPUT=${1:-.scratch/training-20}
BASELINE_INPUT=${2:-.scratch/autoencoder-21}
TRIAL_OUTPUT=${3:-.scratch/local-ssl-22-repeat}
REFERENCE_INPUT=${4:-.scratch/unsupervised-input/evaluation}
NETCAT_PYTHON=${NETCAT_PYTHON:-/home/rlew/projekty/conda-migration-ubuntu-20261008/envs/netcat/bin/python}
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 CUBLAS_WORKSPACE_CONFIG=:4096:8
export MPLCONFIGDIR=${MPLCONFIGDIR:-/tmp/stmdomains-matplotlib}
if [[ -e "$TRIAL_OUTPUT" ]]; then
    echo "Use a fresh output directory: $TRIAL_OUTPUT" >&2
    exit 1
fi
MODULE=stmdomains.experiments.training.local_ssl
for STAGE in audit-baseline plan; do
    "$NETCAT_PYTHON" -m "$MODULE.prepare" "$STAGE" --prepared "$PREPARED_INPUT" \
        --baseline "$BASELINE_INPUT" --output "$TRIAL_OUTPUT"
done
"$NETCAT_PYTHON" -m "$MODULE.fit" train --prepared "$PREPARED_INPUT" \
    --baseline "$BASELINE_INPUT" --output "$TRIAL_OUTPUT" --device cuda
"$NETCAT_PYTHON" -m "$MODULE.prepare" audit-training --prepared "$PREPARED_INPUT" \
    --baseline "$BASELINE_INPUT" --output "$TRIAL_OUTPUT"
for STAGE in cache encode partition freeze; do
    "$NETCAT_PYTHON" -m "$MODULE.predict" "$STAGE" --prepared "$PREPARED_INPUT" \
        --baseline "$BASELINE_INPUT" --output "$TRIAL_OUTPUT" --device cuda
done
"$NETCAT_PYTHON" -m "$MODULE.evaluate" --predictions "$TRIAL_OUTPUT" \
    --controls-evaluation "$PREPARED_INPUT/controls/evaluation" \
    --measurement-evaluation "$REFERENCE_INPUT" --out "$TRIAL_OUTPUT/evaluation"
"$NETCAT_PYTHON" -m "$MODULE.diagnostics" --output "$TRIAL_OUTPUT" \
    --prepared "$PREPARED_INPUT" --evaluation "$PREPARED_INPUT/controls/evaluation" --device cuda
"$NETCAT_PYTHON" -m "$MODULE.figures" --output "$TRIAL_OUTPUT" --prepared "$PREPARED_INPUT"
"$NETCAT_PYTHON" -m "$MODULE.gallery" --output "$TRIAL_OUTPUT" \
    --control-manifest "$PREPARED_INPUT/controls/evaluation/manifest.json"
"$NETCAT_PYTHON" -m "$MODULE.summarize" --output "$TRIAL_OUTPUT" \
    --manifest "$TRIAL_OUTPUT/evidence.json"
