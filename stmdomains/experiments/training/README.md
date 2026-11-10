# Issue 20: reproducible training preparation

This package prepares inputs and runs a short technical GPU/checkpoint probe.
It does not train or select a domain detector. The closed comparison plan is
[experiment-plan.json](experiment-plan.json); its rationale and evaluation
contract are in [the protocol](../../../docs/stmdomains/self-supervised-training-protocol.md).

Run from the repository root in `netcat` (the workspace `.venv` lacks Torch).
No packages or model weights were installed for this preparation. The tested
environment has Python 3.12, Torch 2.9.1+cu128, NumPy, SciPy and Matplotlib.
The GPU must be visible to the process; this session required execution
outside the filesystem/device sandbox.

```bash
bash stmdomains/experiments/training/run_preparation.sh \
  .scratch/unsupervised-input/analysis \
  data/TTMAPP/MOVIE_23raw_TTMAPP_I_AU111.MPP \
  data/TTMAPP/detection_full.moltrack.json \
  .scratch/training-20-repeat
```

The output must be new. Set `NETCAT_PYTHON` to override the recorded `netcat`
interpreter. The wrapper executes data preparation, fresh evaluation controls,
an independent raw-input audit and complete replay with reference access
denied, then the GPU probe and an evidence manifest/geometry figure.
It never accepts a manual-reference path.

Outputs:

- `data/analysis/`: the 24 original, hash-checked label-free measurement inputs.
- `data/windows.jsonl`: every grid/center/scale, effective support, availability,
  transfer membership and raw resampled-patch hash. Images are loaded lazily;
  all 38,622 windows are not materialized as a training tensor on disk.
- `data/split.json`, `normalization.json`: frozen geometry and scalar intensity
  transforms. Train fitting and all-field transduction are distinct.
- `data/gpu-batch.npz`: 84 real, normalized 64px training windows for the probe.
- `controls/analysis/` and `controls/evaluation/`: 81 reserved realizations;
  only the former is allowed at prediction time. Neither feeds representation
  training or checkpoint selection.
- `gpu/`: short-run timings, operation checks, checkpoints and fresh-process
  continuation comparisons for three seeds. Checkpoints are trusted local
  pickle archives, not a public interchange format.
- `evidence.json`, `geometry.png`: small audit summary and a geometry-only plot.

For a training sampler, load windows with `read_windows`, select the regime's
eligible rows, load a frame with `bundle.load_sample`, and call `extract_patch`
with its frozen normalizer. `augmented_pair` returns both tensors and the
coordinate maps; save its NumPy generator using checkpoint `np_generator=`.
All-scale sampling and the actual model/loss are implemented in 21/22.
Synthetic inference must first apply `synthetic_in_normalizer_units`; this
fixed contrast convention avoids silently interpreting renderer units as STM
raw values. Its original arrays and truth remain unchanged.

Sampling is with replacement, uniformly over scales and eligible frames,
then eligible grid locations. Overlapping windows and scales are correlated.
Center-based extraction is separate, never a filter on the grid. Unsupported
border windows are retained as unavailable; zero padding is forbidden.

The checkpoint supports synchronous float32 training at completed step
boundaries. It saves weights, optimizer, scheduler, all used random streams,
sampler and caller-provided progress. It does not support pending gradients,
AMP scaler state, workers or prefetch queues. The planned runs use none of
these. Each actual model still needs its own short resume test in 21/22.
CUDA `grid_sample` backward is not strictly deterministic in this environment;
the planned rVAE uses the tested coordinate-rotation decoder primitive.

```bash
python -m pytest -q tests/stmdomains
```

The pilot's spatial separation is a property of saved registration, not a
guarantee of independent physical fields. Its 8px guard is not calibrated.
Transfer has only 96 eligible 48px grid windows across three training frames;
results cannot establish generalization to another acquisition. Full native
application GUI, solver quality and trained-model quality are outside issue 20.
