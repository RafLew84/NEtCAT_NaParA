# Issue21a: bounded rVAE decoder and KL follow-up

Research experiment, separate from application code and the frozen issue21.
The scope and budget are in
[ticket21a](../../../../docs/stmdomains/issues/21a-rvae-decoder-and-kl.md).
The original training, Fourier/ACF, graph and evaluation modules are reused
without modifying their source. No additional packages or measurements are needed.

Use the existing `netcat` Python with CUDA, from the repository root. All large
outputs remain in a new local directory. Do not reuse an attempted run directory.

```bash
bash stmdomains/experiments/training/rvae_followup/run_followup.sh \
  .scratch/training-20 .scratch/autoencoder-21 .scratch/rvae-21a-repeat \
  .scratch/unsupervised-input/evaluation
```

`NETCAT_PYTHON` may override the environment's Python path. The wrapper reserves
the new protocol before training, creates fresh controls, executes two diagnostic
runs and nine full fits, freezes predictions, and only then opens evaluation truth.
It never runs SSL, changes the order gate, or retrains old model/adapter baselines.

The main model matrix has original/Fourier-coordinate decoders and KL targets
0.001/0.0001. Original decoder+0.001 comes from21; the other three cells have
three new seeds each. All full fits use transfer z32 and the same data, three
training scales, sampler, validation batches and optimizer as21. Domain inference
uses only the primary48px grid with stride16 and the two original graph solvers.
The protocol's `fh` denotes the unchanged FH variant with k=4 (saved ID `fh4`).
Full-frame overlays and the separate transfer-test graph are both retained.

`protocol.json` fixes the new synthetic seeds, exact quarter-turn diagnostic and
illustrative patch. `fit plan` freezes this file, architecture, training sources,
the16diagnostic patch IDs/hashes, baseline identity and all11planned run IDs.
Generation of synthetic ground truth is an isolated preparation step. Predictors
receive only the analysis trees and deny evaluation/reference paths.

Budgets: two diagnostic runs each2000steps/5minutes; nine full fits each2000steps/
15minutes; at most22000steps and2h25minutes overall;8GiB CUDA tensors,12GiB RSS,
4GiB extra checkpoints and7200CPU seconds of preparation/postprocessing. These
are ceilings, not expected durations. Failed/stopped fits consume their attempt;
no replacement seed, restart or parameter search is allowed. Checkpoints include
optimizer, scheduler, sampler, augmentation and random states.

Key artifacts under the output root:

- `baseline-audit.json`: verification of all100299frozen issue21 artifacts.
- `plan.json`, `protocol.json`, `diagnostic-inputs.npz`: pretraining identity.
- `diagnostic/`, `training/`, `logs/`: all attempts, selected/fixed-step checkpoints,
  loss histories, validation identity, costs and failures.
- `controls/analysis/` and `controls/evaluation/`: separately stored inputs/truth.
- `cache/`, `features/`, `predictions/`: grid48 inference and complete result exports.
- `frozen-predictions.json`: local and external input/model/source hashes before truth.
- `evaluation/`: coverage, pair/boundary errors, negative controls, stability and
  matched comparisons to FFT, AE and the original rVAE.
- `feature-diagnostics.json`, `figures/`, `index.html`: descriptive checks and
  standalone gallery; no selection or retraining based on these views.
- `*.resources.json`: cumulative measured preparation/postprocessing CPU usage.

Original TTMAPP has already been viewed; its evaluation is developmental and
cannot establish independent-acquisition generalization. Fresh synthetic seeds
are new realizations of known idealized cases. Better reconstruction, raw angle
or representation alone does not qualify a detector. The unchanged gate may
still reject almost every STM window; unknown physical types/angles remain null.
