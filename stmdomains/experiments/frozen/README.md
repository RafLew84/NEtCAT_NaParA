# Frozen local features — issue 18

Reusable research preparation, independent of the application UI. No domain
labels, clustering, training, PCA or domain quality scores are produced here.
Both models are frozen and evaluated in float32. Model parameters and buffers
(including BatchNorm) are hashed before and after extraction.

A complete preparation, including the geometry inspector and verification,
can be reproduced with one command (use an unused output directory):

```bash
bash stmdomains/experiments/frozen/run_preparation.sh \
  /home/rlew/projekty/NEtCAT-domains/.scratch/image-texture-domains/input/analysis \
  /tmp/frozen-assets /tmp/frozen-features
```

Use local netcat (torch 2.9.1+cu128, torchvision 0.24.1+cu128, NumPy and Pillow).
No changes to shared requirements or installation are needed. From the repo:

```bash
NETCAT_PYTHON=/home/rlew/projekty/conda-migration-ubuntu-20261008/envs/netcat/bin/python
$NETCAT_PYTHON -m stmdomains.experiments.frozen.assets --out /tmp/frozen-assets
CUBLAS_WORKSPACE_CONFIG=:4096:8 $NETCAT_PYTHON -m stmdomains.experiments.frozen.extract \
  --analysis /home/rlew/projekty/NEtCAT-domains/.scratch/image-texture-domains/input/analysis \
  --assets /tmp/frozen-assets --out /tmp/frozen-features --device cuda
```

Downloads are explicit and limited to official public model weights and a
pinned DINOv2 code archive; expected SHA-256 values are checked. Extraction
is entirely offline. `--device cpu` is supported. The present Codex sandbox
cannot access the GPU; the reported RTX run used escalated execution.

Defaults: 12 explicitly listed samples (`extract.PILOT`), both models, radii
24/36 reference pixels (window widths 48/72), model inputs 112/224, two frame
normalizations, grid step12, all centers, batch32, four CPU threads. Repeated
`--sample`, `--model`, `--radius`, `--size`, `--normalization`, `--mode` flags
restrict a run. For all input frames pass their sample IDs explicitly; an
omitted sample list means the documented pilot, not the full series.

FCN taps backbone.layer1 (256 channels) and layer2 (512), spatially averages
each map and concatenates them (768). DINOv2 ViT-S/14 uses the mean of final
LayerNorm patch tokens (384), without CLS or registers. These vectors describe
local windows, not the whole frame. The main map is a field of window vectors;
individual native feature maps are exposed by `FrozenExtractor.maps` and
recorded for representative edge/interior windows in the verification output.
This pooling is our adaptation, not a replication of the STM paper's pixelwise
feature interpolation and fixed-K grouping.

The grayscale measurement is normalized using either frame-wide 2nd/98th
percentiles or frame-wide min/max, clipped to [0,1], replicated into RGB and
normalized with ImageNet mean/std. No display gamma or center-dependent
normalization is used. This differs from the STM notebook's per-window
z-score, and from the torchvision preset's automatic resize to520. The source
paper's later training and manual choice of classes are not used.

Geometry uses original pixel-edge coordinates. The technical pixel spacing
controls window width, independently of molecular spacing. Rectangular fields
are covered by the grid without a center crop. Crops use explicit bilinear
sampling and reflection outside the image. `source_measured` plus window bounds
and fractional measured support separate actual data from reflected/imputed
pixels. Model inputs are divisible by14, so DINO needs no extra spatial padding.
FCN's internal convolution padding is recorded. The descriptor depends on its
whole crop; normalization statistics additionally depend on all measured frame
pixels. DINO token anchors must not be described as the whole receptive field.

Cache identity includes image, measurement mask, technical scale, config,
model/weights/code hashes, runtime/device and preprocessing. Grid keys exclude
annotations; center keys include sorted IDs and positions. A change of model,
window, normalization or image gives a different key. Original annotation hashes
are retained in the run manifest. Arrays and JSON are hash-checked on reuse.
Paths in run manifests are relative to the output directory, including an
external cache if `--cache` is used. Keep referenced files together when moving.

`cache/*.npz` stores features, xy, object IDs, requested and clipped window
bounds, source measurement mask and measured/field support fractions. Matching
JSON stores exact model and preprocessing identity, native map shapes, costs
and array hashes. `manifest.json` maps each frame/configuration/sampling mode
to its cache entry. Large arrays and models stay outside Git.

For the full audit, place the pilot analysis tree at `OUTPUT/input/analysis`
(the input manifest and its sample files, no evaluation tree), then run:

```bash
CUBLAS_WORKSPACE_CONFIG=:4096:8 $NETCAT_PYTHON -m stmdomains.experiments.frozen.verify \
  --root OUTPUT --assets /tmp/frozen-assets --device cuda
$NETCAT_PYTHON -m stmdomains.experiments.frozen.preview --root OUTPUT
$NETCAT_PYTHON -m pytest -q tests/stmdomains
```

The verification requires a new `OUTPUT/replay` cache: every distinct grid
input must be recomputed once. Identical images (single and missing-centers
controls) intentionally share entries within that fresh run. It removes all
annotations, introduces unrelated invalid reference data, compares arrays at
atol1e-5/rtol1e-4 for identical batch layout; batch/order checks use
atol1e-4/rtol1e-4 (DINO exceeded the stricter original absolute tolerance in
one check, recorded explicitly). It checks coordinates, cache reuse, hashes
and model immutability. Native map witnesses are kept separately. Tests cover
coordinate ramps, rectangular geometry, edge reflection, missing measurements,
technical resizing, cache invalidation/corruption and degenerate images.

`index.html` is a self-contained geometry inspector: grid crosses and molecule
circles are separate, selected window bounds and measured support are explicit.
It visualizes where descriptors are taken, not detected domains or PCA classes.
Issue19 will evaluate their usefulness with the classic baselines.

Optional local HTML verification:

```bash
QT_QPA_PLATFORM=offscreen QTWEBENGINE_CHROMIUM_FLAGS="--no-sandbox --disable-gpu" QTWEBENGINE_DISABLE_SANDBOX=1 \
  $NETCAT_PYTHON tests/stmdomains/check_frozen_preview.py OUTPUT
```
