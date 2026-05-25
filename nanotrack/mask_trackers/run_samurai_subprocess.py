#!/usr/bin/env python3
"""Run SAMURAI mask tracking for one NanoTrack seed."""

from __future__ import annotations

import argparse
from contextlib import contextmanager, nullcontext
from dataclasses import dataclass
import importlib
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import sys
from typing import Any, Iterator

import numpy as np

if __package__ in (None, ""):
    REPO_ROOT = Path(__file__).resolve().parents[2]
    if str(REPO_ROOT) not in sys.path:
        sys.path.insert(0, str(REPO_ROOT))
    from nanotrack.mask_trackers.config import MaskTrackerKind, SAMURAI_MODEL_VARIANTS
    from nanotrack.mask_trackers.contract import MaskTrackerRunInput, MaskTrackerRunOutput
else:
    from .config import MaskTrackerKind, SAMURAI_MODEL_VARIANTS
    from .contract import MaskTrackerRunInput, MaskTrackerRunOutput


DEFAULT_SAMURAI_VARIANT = "sam2.1_hiera_base_plus"


@dataclass(frozen=True)
class SamuraiMaterializedInput:
    """Paths created for SAMURAI's file-oriented demo/runtime format."""

    root_dir: Path
    frame_dir: Path
    bbox_path: Path
    frame_paths: tuple[Path, ...]
    bbox_xywh: tuple[int, int, int, int]


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="NanoTrack SAMURAI subprocess worker.")
    parser.add_argument("--input-npz", required=True, help="Input NPZ produced by NanoTrack.")
    parser.add_argument("--output-npz", required=True, help="Output NPZ path.")
    parser.add_argument("--checkpoint", required=True, help="Path to a SAMURAI/SAM2.1 checkpoint.")
    parser.add_argument("--repo-path", default=None, help="Optional path to the local SAMURAI repo.")
    parser.add_argument("--variant", default=None, help="SAMURAI model variant.")
    parser.add_argument("--config", default=None, help="SAMURAI config identifier.")
    parser.add_argument("--device", default="auto", help="Torch device request.")
    parser.add_argument("--stub", action="store_true", help="Use deterministic synthetic masks instead of SAMURAI.")
    return parser.parse_args()


def _load_input(path: Path) -> MaskTrackerRunInput:
    with np.load(path, allow_pickle=False) as payload:
        input_payload = {key: payload[key] for key in payload.files}
    return MaskTrackerRunInput.from_npz_payload(input_payload)


def _bootstrap_windows_conda_dlls() -> None:
    if os.name != "nt" or not hasattr(os, "add_dll_directory"):
        return
    env_root = Path(sys.executable).resolve().parent
    dll_dirs = [
        env_root,
        env_root / "Library" / "bin",
        env_root / "DLLs",
        env_root / "Scripts",
        env_root / "Lib" / "site-packages" / "torch" / "lib",
    ]
    existing = [str(path) for path in dll_dirs if path.exists()]
    current_path = os.environ.get("PATH", "")
    if existing:
        os.environ["PATH"] = os.pathsep.join(existing + ([current_path] if current_path else []))
    for directory in existing:
        try:
            os.add_dll_directory(directory)
        except (FileNotFoundError, OSError):
            continue


def _normalize_path_key(path_value: str | os.PathLike[str] | None) -> str:
    if path_value is None:
        return ""
    return os.path.normcase(os.path.normpath(str(path_value)))


@contextmanager
def _samurai_import_context(repo_path: Path) -> Iterator[None]:
    repo_root = Path(repo_path).expanduser().resolve()
    sam2_root = repo_root / "sam2"
    build_sam_path = sam2_root / "sam2" / "build_sam.py"
    demo_path = repo_root / "scripts" / "demo.py"
    if not demo_path.exists() or not build_sam_path.exists():
        raise FileNotFoundError(
            "Invalid SAMURAI repo_path. Expected scripts/demo.py and sam2/sam2/build_sam.py "
            f"under: {repo_root}"
        )

    repo_root_key = _normalize_path_key(repo_root)
    sam2_root_key = _normalize_path_key(sam2_root)
    original_sys_path = list(sys.path)
    original_cwd = os.getcwd()

    filtered_sys_path: list[str] = []
    for entry in original_sys_path:
        entry_key = _normalize_path_key(entry)
        if entry_key in {repo_root_key, sam2_root_key}:
            continue
        filtered_sys_path.append(entry)

    sys.path[:] = [str(sam2_root), str(repo_root), *filtered_sys_path]
    for module_name in list(sys.modules):
        if module_name == "sam2" or module_name.startswith("sam2."):
            sys.modules.pop(module_name, None)
    try:
        os.chdir(sam2_root)
        yield
    finally:
        os.chdir(original_cwd)
        sys.path[:] = original_sys_path


def _materialize_samurai_inputs(run_input: MaskTrackerRunInput, root_dir: Path) -> SamuraiMaterializedInput:
    """Write frames and initial bbox in the layout expected by SAMURAI demos."""

    if run_input.tracker_kind is not MaskTrackerKind.SAMURAI:
        raise ValueError(
            f"SAMURAI worker expected tracker_kind='samurai', got {run_input.tracker_kind.value!r}."
        )

    root = Path(root_dir)
    frame_dir = root / "frames"
    frame_dir.mkdir(parents=True, exist_ok=True)
    bbox_path = root / "bbox.txt"

    frames_rgb = _prepare_frames_rgb(run_input.frames)
    frame_paths: list[Path] = []
    for frame_index, frame_rgb in enumerate(frames_rgb):
        frame_path = frame_dir / f"{frame_index:06d}.jpg"
        _save_rgb_frame(frame_path, frame_rgb)
        frame_paths.append(frame_path)

    height, width = frames_rgb.shape[1:3]
    bbox_xyxy = _initial_bbox_xyxy(run_input, height=height, width=width)
    bbox_xywh = _bbox_xyxy_to_integer_xywh(bbox_xyxy, height=height, width=width)
    bbox_path.write_text(",".join(str(value) for value in bbox_xywh) + "\n", encoding="utf-8")

    return SamuraiMaterializedInput(
        root_dir=root,
        frame_dir=frame_dir,
        bbox_path=bbox_path,
        frame_paths=tuple(frame_paths),
        bbox_xywh=bbox_xywh,
    )


def _save_rgb_frame(path: Path, frame_rgb: np.ndarray) -> None:
    from PIL import Image

    Image.fromarray(np.asarray(frame_rgb, dtype=np.uint8), mode="RGB").save(path, quality=95)


def _prepare_frames_rgb(frames: np.ndarray) -> np.ndarray:
    frames_np = np.asarray(frames)
    if frames_np.ndim == 3:
        frames_np = frames_np[..., None]
    if frames_np.ndim != 4:
        raise ValueError("frames must have shape [T, H, W] or [T, H, W, C].")
    if frames_np.shape[-1] == 1:
        frames_np = np.repeat(frames_np, 3, axis=-1)
    elif frames_np.shape[-1] >= 3:
        frames_np = frames_np[..., :3]
    else:
        raise ValueError("frames channel dimension must be 1 or >=3.")

    output = np.zeros(frames_np.shape, dtype=np.uint8)
    for frame_idx, frame in enumerate(frames_np):
        frame_f32 = np.asarray(frame, dtype=np.float32)
        finite_mask = np.isfinite(frame_f32)
        if not np.any(finite_mask):
            continue
        finite_values = frame_f32[finite_mask]
        value_min = float(np.min(finite_values))
        value_max = float(np.max(finite_values))
        if value_max <= value_min + 1e-8:
            continue
        normalized = np.clip((frame_f32 - value_min) / (value_max - value_min), 0.0, 1.0)
        output[frame_idx] = np.asarray(np.round(normalized * 255.0), dtype=np.uint8)
    return output


def _initial_bbox_xyxy(run_input: MaskTrackerRunInput, *, height: int, width: int) -> np.ndarray:
    if run_input.query_box_xyxy is not None:
        return np.asarray(run_input.query_box_xyxy, dtype=np.float32)
    if run_input.initial_mask is not None:
        bbox = _bbox_from_mask(np.asarray(run_input.initial_mask, dtype=bool))
        return np.asarray(bbox, dtype=np.float32)
    if run_input.query_point_tyx is not None:
        _local_t, y, x = [float(value) for value in run_input.query_point_tyx]
        return np.asarray([x - 1.0, y - 1.0, x + 2.0, y + 2.0], dtype=np.float32)
    raise ValueError("SAMURAI stub requires a bbox, point, or initial mask prompt.")


def _query_seed_frame_index(run_input: MaskTrackerRunInput) -> int:
    if run_input.query_point_tyx is None:
        return 0
    seed_frame = int(round(float(run_input.query_point_tyx[0])))
    frame_count = int(run_input.frames.shape[0])
    if not 0 <= seed_frame < frame_count:
        raise ValueError(f"SAMURAI seed frame index out of range: {seed_frame}.")
    return seed_frame


def _bbox_xyxy_to_integer_xywh(
    bbox_xyxy: np.ndarray,
    *,
    height: int,
    width: int,
) -> tuple[int, int, int, int]:
    x0, y0, x1, y1 = [float(value) for value in np.asarray(bbox_xyxy, dtype=np.float32)]
    col0 = max(0, min(width, int(np.floor(x0))))
    row0 = max(0, min(height, int(np.floor(y0))))
    col1 = max(0, min(width, int(np.ceil(x1))))
    row1 = max(0, min(height, int(np.ceil(y1))))
    return (col0, row0, max(0, col1 - col0), max(0, row1 - row0))


def _synthetic_output(
    run_input: MaskTrackerRunInput,
    *,
    checkpoint_name: str,
    variant: str | None,
) -> MaskTrackerRunOutput:
    if run_input.tracker_kind is not MaskTrackerKind.SAMURAI:
        raise ValueError(
            f"SAMURAI worker expected tracker_kind='samurai', got {run_input.tracker_kind.value!r}."
        )

    frame_count, height, width = run_input.frames.shape[:3]
    masks = np.zeros((frame_count, height, width), dtype=bool)

    if run_input.initial_mask is not None:
        masks[:] = run_input.initial_mask
    elif run_input.query_box_xyxy is not None:
        masks[:] = _mask_from_bbox(run_input.query_box_xyxy, height=height, width=width)
    elif run_input.query_point_tyx is not None:
        masks[:] = _mask_from_bbox(
            _initial_bbox_xyxy(run_input, height=height, width=width),
            height=height,
            width=width,
        )
    else:  # Defensive only; MaskTrackerRunInput already validates this.
        raise ValueError("SAMURAI stub requires a bbox, point, or initial mask prompt.")

    return _output_from_masks(
        run_input,
        masks=masks,
        model_name="samurai_stub",
        checkpoint_name=checkpoint_name,
        variant=variant,
    )


def _run_real_samurai(
    run_input: MaskTrackerRunInput,
    *,
    materialized: SamuraiMaterializedInput,
    checkpoint_path: Path,
    repo_path: Path | None,
    variant: str | None,
    config_identifier: str | None,
    device_name: str,
) -> MaskTrackerRunOutput:
    if run_input.tracker_kind is not MaskTrackerKind.SAMURAI:
        raise ValueError(
            f"SAMURAI worker expected tracker_kind='samurai', got {run_input.tracker_kind.value!r}."
        )
    if repo_path is None:
        raise FileNotFoundError("SAMURAI real inference requires --repo-path.")
    if not checkpoint_path.exists():
        raise FileNotFoundError(f"SAMURAI checkpoint not found: {checkpoint_path}")

    frame_count, height, width = run_input.frames.shape[:3]
    masks = np.zeros((frame_count, height, width), dtype=bool)
    bbox_xyxy = _bbox_xywh_to_xyxy(materialized.bbox_xywh)
    seed_frame = _query_seed_frame_index(run_input)
    resolved_variant = variant or DEFAULT_SAMURAI_VARIANT
    resolved_config = _resolve_samurai_config_identifier(
        config_identifier,
        variant=resolved_variant,
        checkpoint_path=checkpoint_path,
    )

    with _samurai_import_context(repo_path):
        torch_module = importlib.import_module("torch")
        resolved_device = _resolve_samurai_device(torch_module, device_name)
        build_sam_module = importlib.import_module("sam2.build_sam")
        predictor = build_sam_module.build_sam2_video_predictor(
            resolved_config,
            str(checkpoint_path),
            device=resolved_device,
        )
        state = None
        try:
            autocast_ctx = _samurai_autocast_context(torch_module, resolved_device)
            with torch_module.inference_mode(), autocast_ctx:
                state = predictor.init_state(str(materialized.frame_dir), offload_video_to_cpu=True)
                add_result = predictor.add_new_points_or_box(
                    state,
                    box=np.asarray(bbox_xyxy, dtype=np.float32),
                    frame_idx=seed_frame,
                    obj_id=0,
                )
                _record_samurai_output_tuple(
                    add_result,
                    masks=masks,
                    probability_threshold=run_input.mask_probability_threshold,
                )
                for output_tuple in predictor.propagate_in_video(state):
                    _record_samurai_output_tuple(
                        output_tuple,
                        masks=masks,
                        probability_threshold=run_input.mask_probability_threshold,
                    )
        finally:
            _release_samurai_resources(torch_module)

    return _output_from_masks(
        run_input,
        masks=masks,
        model_name="samurai",
        checkpoint_name=checkpoint_path.name,
        variant=resolved_variant,
    )


def _resolve_samurai_config_identifier(
    config_identifier: str | None,
    *,
    variant: str | None,
    checkpoint_path: Path,
) -> str:
    if config_identifier:
        return str(config_identifier)

    variant_key = _normalize_samurai_variant_key(variant or checkpoint_path.name)
    if variant_key in SAMURAI_MODEL_VARIANTS:
        return SAMURAI_MODEL_VARIANTS[variant_key][1]

    checkpoint_name = checkpoint_path.name.lower()
    if "large" in checkpoint_name:
        return "configs/samurai/sam2.1_hiera_l.yaml"
    if "base_plus" in checkpoint_name or "b+" in checkpoint_name:
        return "configs/samurai/sam2.1_hiera_b+.yaml"
    if "small" in checkpoint_name:
        return "configs/samurai/sam2.1_hiera_s.yaml"
    if "tiny" in checkpoint_name:
        return "configs/samurai/sam2.1_hiera_t.yaml"
    raise ValueError(
        "Could not resolve SAMURAI config identifier. Pass --config explicitly "
        f"for variant={variant!r}, checkpoint={checkpoint_path.name!r}."
    )


def _normalize_samurai_variant_key(variant: str | None) -> str:
    raw = str(variant or DEFAULT_SAMURAI_VARIANT).strip()
    name = Path(raw).name
    for suffix in (".pth.tar", ".pth", ".pt", ".tar", ".yaml", ".yml"):
        if name.lower().endswith(suffix):
            name = name[: -len(suffix)]
            break
    key = name.lower().replace("-", "_").replace("sam2_1", "sam2.1")
    aliases = {
        "large": "sam2.1_hiera_large",
        "l": "sam2.1_hiera_large",
        "base": "sam2.1_hiera_base_plus",
        "base_plus": "sam2.1_hiera_base_plus",
        "b+": "sam2.1_hiera_base_plus",
        "b_plus": "sam2.1_hiera_base_plus",
        "small": "sam2.1_hiera_small",
        "s": "sam2.1_hiera_small",
        "tiny": "sam2.1_hiera_tiny",
        "t": "sam2.1_hiera_tiny",
    }
    key = key.replace("hiera_b+", "hiera_base_plus").replace("b+", "base_plus")
    return aliases.get(key, key)


def _resolve_samurai_device(torch_module: Any, device_name: str | None) -> str:
    normalized = str(device_name or "auto").strip().lower()
    cuda_available = bool(getattr(getattr(torch_module, "cuda", None), "is_available", lambda: False)())
    if normalized in {"", "auto"}:
        return "cuda:0" if cuda_available else "cpu"
    if normalized == "cuda":
        normalized = "cuda:0"
    if normalized.isdigit():
        normalized = f"cuda:{normalized}"
    if normalized.startswith("cuda") and not cuda_available:
        raise RuntimeError("SAMURAI requested CUDA, but torch.cuda.is_available() is false.")
    return normalized


def _samurai_autocast_context(torch_module: Any, device_name: str):
    if not str(device_name).startswith("cuda"):
        return nullcontext()
    autocast = getattr(torch_module, "autocast", None)
    if autocast is None:
        return nullcontext()
    return autocast("cuda", dtype=getattr(torch_module, "float16", None))


def _record_samurai_output_tuple(
    output_tuple: Any,
    *,
    masks: np.ndarray,
    probability_threshold: float = 0.5,
) -> None:
    if output_tuple is None:
        return
    try:
        frame_index, object_ids, mask_logits = output_tuple
    except (TypeError, ValueError):
        raise ValueError("SAMURAI output must be a tuple: (frame_index, object_ids, masks).")

    frame_idx = int(frame_index)
    if not 0 <= frame_idx < masks.shape[0]:
        return
    for object_id, mask_tensor in zip(object_ids, mask_logits):
        if int(object_id) != 0:
            continue
        masks[frame_idx] = _coerce_samurai_mask(
            mask_tensor,
            frame_shape=masks.shape[1:3],
            probability_threshold=probability_threshold,
        )


def _coerce_samurai_mask(
    mask_tensor: Any,
    *,
    frame_shape: tuple[int, int],
    probability_threshold: float = 0.5,
) -> np.ndarray:
    if hasattr(mask_tensor, "detach"):
        arr = mask_tensor.detach().cpu().numpy()
    else:
        arr = np.asarray(mask_tensor)
    arr = np.asarray(arr)
    if arr.ndim == 3 and arr.shape[0] == 1:
        arr = arr[0]
    elif arr.ndim > 2:
        arr = np.squeeze(arr)
    if arr.ndim != 2:
        raise ValueError(f"Unexpected SAMURAI mask tensor shape: {arr.shape}.")
    mask = np.asarray(
        _soft_samurai_mask_to_bool(arr, probability_threshold=probability_threshold),
        dtype=bool,
    )
    if mask.shape == tuple(frame_shape):
        return mask
    return _resize_mask_nearest(mask, frame_shape)


def _resize_mask_nearest(mask: np.ndarray, frame_shape: tuple[int, int]) -> np.ndarray:
    height, width = int(frame_shape[0]), int(frame_shape[1])
    try:
        import cv2  # type: ignore

        return np.asarray(
            cv2.resize(mask.astype(np.uint8), (width, height), interpolation=cv2.INTER_NEAREST),
            dtype=bool,
        )
    except Exception:
        try:
            from PIL import Image

            resized = Image.fromarray(mask.astype(np.uint8) * 255).resize((width, height), Image.NEAREST)
            return np.asarray(resized, dtype=np.uint8) > 0
        except Exception:
            output = np.zeros((height, width), dtype=bool)
            copy_height = min(height, mask.shape[0])
            copy_width = min(width, mask.shape[1])
            output[:copy_height, :copy_width] = mask[:copy_height, :copy_width]
            return output


def _sigmoid(values: np.ndarray) -> np.ndarray:
    clipped = np.clip(np.asarray(values, dtype=np.float32), -60.0, 60.0)
    return 1.0 / (1.0 + np.exp(-clipped))


def _soft_samurai_mask_to_bool(mask: np.ndarray, *, probability_threshold: float) -> np.ndarray:
    mask_np = np.asarray(mask)
    finite_values = mask_np[np.isfinite(mask_np)]
    if finite_values.size == 0:
        return np.zeros(mask_np.shape, dtype=bool)
    value_min = float(np.min(finite_values))
    value_max = float(np.max(finite_values))
    if 0.0 <= value_min and value_max <= 1.0:
        return mask_np >= float(probability_threshold)
    return _sigmoid(mask_np) >= float(probability_threshold)


def _bbox_xywh_to_xyxy(bbox_xywh: tuple[int, int, int, int]) -> tuple[float, float, float, float]:
    x, y, box_width, box_height = [float(value) for value in bbox_xywh]
    return (x, y, x + box_width, y + box_height)


def _release_samurai_resources(torch_module: Any) -> None:
    try:
        import gc

        gc.collect()
    except Exception:
        pass
    clear_autocast_cache = getattr(torch_module, "clear_autocast_cache", None)
    if callable(clear_autocast_cache):
        try:
            clear_autocast_cache()
        except Exception:
            pass
    cuda_module = getattr(torch_module, "cuda", None)
    empty_cache = getattr(cuda_module, "empty_cache", None)
    if callable(empty_cache):
        try:
            empty_cache()
        except Exception:
            pass


def _output_from_masks(
    run_input: MaskTrackerRunInput,
    *,
    masks: np.ndarray,
    model_name: str,
    checkpoint_name: str,
    variant: str | None,
) -> MaskTrackerRunOutput:
    masks_bool = np.asarray(masks, dtype=bool)
    visible_mask = np.any(masks_bool, axis=(1, 2))
    mask_areas = np.asarray([float(np.count_nonzero(mask)) for mask in masks_bool], dtype=np.float32)
    mask_bboxes = np.asarray([_bbox_from_mask(mask) for mask in masks_bool], dtype=np.float32)
    mask_scores = visible_mask.astype(np.float32)
    mask_component_counts = np.asarray([_mask_component_count(mask) for mask in masks_bool], dtype=np.int32)

    return MaskTrackerRunOutput(
        tracker_kind=MaskTrackerKind.SAMURAI,
        track_id=run_input.track_id,
        frame_index_offset=run_input.frame_index_offset,
        masks=masks_bool,
        visible_mask=visible_mask,
        mask_areas=mask_areas,
        mask_bboxes_xyxy=mask_bboxes,
        mask_scores=mask_scores,
        mask_component_counts=mask_component_counts,
        model_name=model_name,
        model_variant=variant,
        checkpoint_name=checkpoint_name,
    )


def _mask_from_bbox(bbox_xyxy: np.ndarray, *, height: int, width: int) -> np.ndarray:
    x0, y0, x1, y1 = [float(value) for value in np.asarray(bbox_xyxy, dtype=np.float32)]
    col0 = max(0, min(width, int(np.floor(x0))))
    row0 = max(0, min(height, int(np.floor(y0))))
    col1 = max(0, min(width, int(np.ceil(x1))))
    row1 = max(0, min(height, int(np.ceil(y1))))

    mask = np.zeros((height, width), dtype=bool)
    if col1 > col0 and row1 > row0:
        mask[row0:row1, col0:col1] = True
    return mask


def _bbox_from_mask(mask: np.ndarray) -> tuple[float, float, float, float]:
    rows, cols = np.nonzero(mask)
    if rows.size == 0 or cols.size == 0:
        return (0.0, 0.0, 0.0, 0.0)
    return (
        float(cols.min()),
        float(rows.min()),
        float(cols.max() + 1),
        float(rows.max() + 1),
    )


def _mask_component_count(mask: np.ndarray) -> int:
    if not np.any(mask):
        return 0
    try:
        import cv2  # type: ignore

        num_labels, _ = cv2.connectedComponents(np.asarray(mask, dtype=np.uint8), connectivity=8)
        return max(0, int(num_labels) - 1)
    except Exception:
        return 1


def main() -> int:
    _bootstrap_windows_conda_dlls()
    args = _parse_args()
    checkpoint_path = Path(args.checkpoint).expanduser().resolve()
    run_input = _load_input(Path(args.input_npz).resolve())
    with TemporaryDirectory(prefix="nanotrack_samurai_") as temp_dir:
        materialized = _materialize_samurai_inputs(run_input, Path(temp_dir))
        if args.stub or args.variant == "stub":
            run_output = _synthetic_output(
                run_input,
                checkpoint_name=checkpoint_path.name,
                variant=args.variant,
            )
        else:
            run_output = _run_real_samurai(
                run_input,
                materialized=materialized,
                checkpoint_path=checkpoint_path,
                repo_path=None if args.repo_path is None else Path(args.repo_path).expanduser().resolve(),
                variant=args.variant,
                config_identifier=args.config,
                device_name=str(args.device),
            )

    output_path = Path(args.output_npz)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(output_path, **run_output.to_npz_payload())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
