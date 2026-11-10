# Issue21: bounded AE/rVAE domain comparison

Research code only. This does not install a trained detector in STM Domains.
The fixed experiment is specified by `experiment-plan.json` and
[the issue20 protocol](../../../docs/stmdomains/self-supervised-training-protocol.md).
Issue21 implements AE/rVAE, not the separate SSL family reserved for22.

Run from the repository root with the existing `netcat` environment and a
visible CUDA GPU. The local `.venv` does not contain Torch. No AtomAI, Pyro,
pyroVED, affogato, downloaded weights or new packages are required.

```bash
bash stmdomains/experiments/training/run_autoencoder_trial.sh \
  .scratch/training-20 .scratch/autoencoder-21-repeat \
  .scratch/unsupervised-input/evaluation
```

Use a new output directory. `NETCAT_PYTHON` overrides the environment's Python
path. The wrapper executes two technical resume checks and exactly18 planned
fits:12 transfer fits (2families×2latent sizes×3seeds), then6 transductive z32
refits. The latter use the median selected transfer step for their own family.
It never adds replacement seeds, trains on synthetic truths or selects a model
using domain-reference metrics. Each fit has a separate process, frozen config,
complete checkpoints and the limits fixed in20.

Stages can also run separately with the same arguments:

```bash
python -m stmdomains.experiments.training.fit --data .scratch/training-20 \
  --out .scratch/autoencoder-21/training
python -m stmdomains.experiments.training.predict cache
python -m stmdomains.experiments.training.predict encode
python -m stmdomains.experiments.training.predict partition
python -m stmdomains.experiments.training.predict freeze
```

The predictor denies evaluation/reference file access. Only the subsequent
`evaluate` command accepts those paths and first verifies the complete freeze.
The CLI's default output above is `.scratch/autoencoder-21`; change it with
`--output`. `cache`, `partition` and `freeze` reject existing outputs. `encode`
can continue completed model extractions. The training runner can reuse complete
runs only with the same architecture/code/plan identity; it does not silently
retry a stopped or failed fit. Technical fixes after starting an experiment must
be documented, and previously used final controls cannot become unseen again.

Main artifacts:

- `training/architecture.json`, `registry.json` and each run's `config.json`,
  `validation.json`, `run.json`, `step-*.pt`: architecture, selection and costs.
- `training-resume/`: full6step versus3+save+newprocess3 checks for both models.
- `cache/`: all grid/center geometries, normalized64×64 network inputs, native
  FFT/ACF descriptors and old-negative ACF calibration at32/48/64 reference pixels.
- `features/`: deterministic content and raw-angle descriptors of selected models.
- `predictions/`: train-only PCA/distance adapters, full result envelopes, complete
  relation tables and before/after arrays for FH and MWS.
- `frozen-predictions.json`: hashes published before opening final truth.
- `evaluation/`: complete per-sample and pooled CSV/JSON, fixed control criteria,
  comparable coverage, seed stability and missing-center invariance checks.
- `feature-diagnostics.json`: descriptive collapse/brightness/frame diagnostics
  and raw rVAE angle differences. These do not select checkpoints or thresholds.
- `index.html`: standalone visual comparison of full fields and refusal states.

The main comparison is the48px grid;32/64px and direct center graphs are fixed
diagnostics using the same weights. Center assignments mapped from the main grid
are reported separately. Technical resampling×2 uses supplied reference-pixel
spacing before grid generation and extraction, without fitting scale to a lattice.

Full-frame transfer overlays are exploratory inference. Held-out measurement
metrics use separate graphs containing only eligible test nodes/edges, so paths
outside the test band cannot connect test components. All models use the same
frozen order gate, which may refuse almost every location. Unknown structural
types, material and unvalidated lattice angles stay null. A graph component is
a proposal; neither it nor a displayed grid cell is a measured domain contour.

The models differ in decoder and KL regularization as well as rotation variables;
this budget does not isolate all those causes with an additional ordinary VAE.
No result from this single correlated acquisition establishes transfer to another
material or acquisition. Native application GUI acceptance remains separate.
