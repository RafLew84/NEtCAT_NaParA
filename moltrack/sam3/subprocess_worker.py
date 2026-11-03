from __future__ import annotations

import argparse
from contextlib import nullcontext
import sys
from pathlib import Path
from typing import Any

import numpy as np


DEFAULT_LOCAL_SAM3_REPO = Path(r"C:\Users\rlewa\Documents\PROJEKTY\sam3")
SAM31_MODEL_ID = "facebook/sam3.1"


def main(*, default_version: str, default_backend: str) -> int:
    args = _parse_args()
    _prepare_import_paths()
    run_worker(
        input_npz=args.input_npz,
        output_npz=args.output_npz,
        model_id=args.model_id,
        device=args.device,
        score_threshold=args.score_threshold,
        mask_threshold=args.mask_threshold,
        default_version=default_version,
        default_backend=default_backend,
    )
    return 0


def run_worker(
    *,
    input_npz: str | Path,
    output_npz: str | Path,
    model_id: str,
    device: str,
    score_threshold: float,
    mask_threshold: float,
    default_version: str,
    default_backend: str,
) -> None:
    del default_version
    payload = _load_input_payload(input_npz)
    image_rgb = payload["image_rgb"]
    input_boxes_xyxy = payload["prompt_bboxes_xyxy"]
    input_boxes_labels = payload["prompt_labels"]
    backend = _resolve_backend(
        payload_backend=str(payload.get("backend") or ""),
        default_backend=default_backend,
        model_id=model_id,
    )

    if backend == "official_sam31":
        output_arrays = _run_official_sam31_visual_search(
            image_rgb=image_rgb,
            input_boxes_xyxy=input_boxes_xyxy,
            input_boxes_labels=input_boxes_labels,
            model_id=model_id,
            device_arg=device,
            score_threshold=float(score_threshold),
            mask_threshold=float(mask_threshold),
            max_results=payload["max_results"],
        )
    else:
        output_arrays = _run_transformers_visual_search(
            image_rgb=image_rgb,
            input_boxes_xyxy=input_boxes_xyxy,
            input_boxes_labels=input_boxes_labels,
            model_id=model_id,
            device_arg=device,
            score_threshold=float(score_threshold),
            mask_threshold=float(mask_threshold),
            max_results=payload["max_results"],
        )

    _write_output_npz(
        output_npz,
        output_arrays=output_arrays,
        backend=backend,
        model_id=model_id,
        device=device,
    )


def _run_transformers_visual_search(
    *,
    image_rgb: np.ndarray,
    input_boxes_xyxy: np.ndarray,
    input_boxes_labels: np.ndarray,
    model_id: str,
    device_arg: str,
    score_threshold: float,
    mask_threshold: float,
    max_results: int,
) -> dict[str, np.ndarray]:
    if _is_sam31_model_id(model_id):
        raise RuntimeError(
            "facebook/sam3.1 is a checkpoint-only repository without Hugging Face "
            "Transformers integration. Use the official_sam31 backend for this model."
        )
    _validate_visual_search_inputs(image_rgb, input_boxes_xyxy, input_boxes_labels)

    import torch
    from PIL import Image
    from transformers import Sam3Model, Sam3Processor

    device = _choose_device(device_arg, torch)
    image = Image.fromarray(np.asarray(image_rgb, dtype=np.uint8)).convert("RGB")
    processor = Sam3Processor.from_pretrained(model_id)
    model = Sam3Model.from_pretrained(model_id).to(device)
    model.eval()

    inputs = processor(
        images=image,
        input_boxes=[np.asarray(input_boxes_xyxy, dtype=np.float32).tolist()],
        input_boxes_labels=[np.asarray(input_boxes_labels, dtype=np.int64).tolist()],
        return_tensors="pt",
    )
    inputs = {
        key: value.to(device) if hasattr(value, "to") else value
        for key, value in inputs.items()
    }

    with torch.inference_mode():
        if str(device).startswith("cuda"):
            with torch.autocast(device_type="cuda", dtype=torch.bfloat16):
                outputs = model(**inputs)
        else:
            outputs = model(**inputs)

    processed = processor.post_process_instance_segmentation(
        outputs,
        threshold=float(score_threshold),
        mask_threshold=float(mask_threshold),
        target_sizes=[(int(image.height), int(image.width))],
    )[0]
    return _processed_instances_to_output_arrays(
        processed,
        image_shape=(int(image.height), int(image.width)),
        score_threshold=float(score_threshold),
        max_results=int(max_results),
    )


def _run_official_sam31_visual_search(
    *,
    image_rgb: np.ndarray,
    input_boxes_xyxy: np.ndarray,
    input_boxes_labels: np.ndarray,
    model_id: str,
    device_arg: str,
    score_threshold: float,
    mask_threshold: float,
    max_results: int,
) -> dict[str, np.ndarray]:
    if not _is_sam31_model_id(model_id):
        raise RuntimeError("Official SAM3.1 runner is only configured for facebook/sam3.1.")
    _validate_visual_search_inputs(image_rgb, input_boxes_xyxy, input_boxes_labels)

    try:
        import torch
        from PIL import Image
        from sam3.model.sam3_image_processor import Sam3Processor
        from sam3.model_builder import build_sam3_image_model, download_ckpt_from_hf
    except Exception as exc:
        raise RuntimeError(
            "Official SAM3.1 runner requires facebookresearch/sam3 installed in "
            "the selected SAM3 environment."
        ) from exc

    device = _choose_device(device_arg, torch)
    checkpoint = _resolve_sam31_checkpoint(download_ckpt_from_hf)
    try:
        model = build_sam3_image_model(
            checkpoint_path=str(checkpoint),
            load_from_HF=False,
            device=device,
            eval_mode=True,
        )
        processor = Sam3Processor(
            model,
            device=device,
            confidence_threshold=float(score_threshold),
        )
    except Exception as exc:
        raise RuntimeError(
            "Official SAM3.1 runner could not initialize the model/checkpoint. "
            f"Checkpoint: {checkpoint}"
        ) from exc

    image = Image.fromarray(np.asarray(image_rgb, dtype=np.uint8)).convert("RGB")
    autocast_context = _cuda_bfloat16_autocast_context(torch, device)
    with torch.inference_mode(), autocast_context:
        state = processor.set_image(image)
        for box_xyxy, label in zip(input_boxes_xyxy, input_boxes_labels, strict=True):
            normalized_box = _xyxy_to_normalized_cxcywh(
                box_xyxy,
                image_width=int(image.width),
                image_height=int(image.height),
            )
            state = processor.add_geometric_prompt(
                normalized_box.tolist(),
                bool(int(label) == 1),
                state,
            )

    boxes = _tensor_to_numpy(state.get("boxes", [])).astype(np.float32, copy=False).reshape((-1, 4))
    scores = _tensor_to_numpy(state.get("scores", [])).astype(np.float32, copy=False).reshape((-1,))
    masks = _masks_from_official_state(
        state,
        mask_threshold=float(mask_threshold),
        image_shape=(int(image.height), int(image.width)),
        result_count=int(boxes.shape[0]),
    )
    return _filter_output_arrays(
        boxes,
        scores,
        masks,
        score_threshold=float(score_threshold),
        max_results=int(max_results),
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run MolTrack SAM3 subprocess worker.")
    parser.add_argument("--input-npz", required=True)
    parser.add_argument("--output-npz", required=True)
    parser.add_argument("--model-id", required=True)
    parser.add_argument("--device", default="cuda")
    parser.add_argument("--score-threshold", type=float, default=0.3)
    parser.add_argument("--mask-threshold", type=float, default=0.5)
    return parser.parse_args()


def _prepare_import_paths() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    for path in (repo_root, DEFAULT_LOCAL_SAM3_REPO):
        if path.exists():
            path_text = str(path)
            if path_text not in sys.path:
                sys.path.insert(0, path_text)


def _load_input_payload(path: str | Path) -> dict[str, Any]:
    with np.load(Path(path), allow_pickle=False) as data:
        boxes_key = "prompt_bboxes_xyxy" if "prompt_bboxes_xyxy" in data.files else "input_boxes"
        labels_key = "prompt_labels" if "prompt_labels" in data.files else "input_boxes_labels"
        return {
            "image_rgb": np.asarray(data["image_rgb"], dtype=np.uint8),
            "prompt_bboxes_xyxy": np.asarray(data[boxes_key], dtype=np.float32).reshape((-1, 4)),
            "prompt_labels": np.asarray(data[labels_key], dtype=np.int64).reshape((-1,)),
            "backend": str(np.asarray(data["backend"]).item()) if "backend" in data.files else "",
            "max_results": int(np.asarray(data["max_results"]).item()) if "max_results" in data.files else 300,
        }


def _resolve_backend(*, payload_backend: str, default_backend: str, model_id: str) -> str:
    backend = str(payload_backend or default_backend).strip()
    if _is_sam31_model_id(model_id):
        return "official_sam31"
    return backend or "transformers_sam3"


def _is_sam31_model_id(model_id: str) -> bool:
    normalized = str(model_id).strip().lower()
    return normalized == SAM31_MODEL_ID or "sam3.1" in normalized or "sam31" in normalized


def _validate_visual_search_inputs(
    image_rgb: np.ndarray,
    input_boxes_xyxy: np.ndarray,
    input_boxes_labels: np.ndarray,
) -> None:
    image = np.asarray(image_rgb)
    if image.ndim != 3 or image.shape[2] != 3:
        raise ValueError("SAM3 visual search requires image_rgb with shape HxWx3.")
    boxes = np.asarray(input_boxes_xyxy, dtype=np.float32).reshape((-1, 4))
    labels = np.asarray(input_boxes_labels, dtype=np.int64).reshape((-1,))
    if boxes.shape[0] == 0:
        raise ValueError("SAM3 visual search requires at least one bbox prompt.")
    if boxes.shape[0] != labels.shape[0]:
        raise ValueError("SAM3 prompt boxes and labels must have the same length.")


def _processed_instances_to_output_arrays(
    processed: dict[str, Any],
    *,
    image_shape: tuple[int, int],
    score_threshold: float,
    max_results: int,
) -> dict[str, np.ndarray]:
    boxes = _tensor_to_numpy(processed.get("boxes", [])).astype(np.float32, copy=False).reshape((-1, 4))
    scores = _tensor_to_numpy(processed.get("scores", [])).astype(np.float32, copy=False).reshape((-1,))
    masks = _normalize_output_masks(processed.get("masks", []), image_shape=image_shape)
    return _filter_output_arrays(
        boxes,
        scores,
        masks,
        score_threshold=float(score_threshold),
        max_results=int(max_results),
    )


def _filter_output_arrays(
    boxes_xyxy: np.ndarray,
    scores: np.ndarray,
    masks: np.ndarray,
    *,
    score_threshold: float,
    max_results: int,
) -> dict[str, np.ndarray]:
    image_shape = tuple(int(value) for value in np.asarray(masks).shape[-2:])
    boxes_xyxy = np.asarray(boxes_xyxy, dtype=np.float32).reshape((-1, 4))
    scores = np.asarray(scores, dtype=np.float32).reshape((-1,))
    masks = _normalize_output_masks(masks, image_shape=image_shape)
    if scores.size == 0 and masks.shape[0] > 0:
        scores = np.ones((masks.shape[0],), dtype=np.float32)
    if boxes_xyxy.size == 0 and masks.shape[0] > 0:
        boxes_xyxy = _boxes_from_masks(masks)

    count = min(int(boxes_xyxy.shape[0]), int(scores.shape[0]), int(masks.shape[0]))
    if count <= 0:
        return _empty_output_arrays(image_shape)

    boxes_xyxy = boxes_xyxy[:count]
    scores = scores[:count]
    masks = masks[:count]
    non_empty = masks.reshape((count, -1)).any(axis=1)
    keep = np.nonzero(non_empty & (scores >= float(score_threshold)))[0]
    if keep.size:
        keep = keep[np.argsort(scores[keep])[::-1]]
    keep = keep[: int(max_results)]
    return {
        "bboxes_xyxy": boxes_xyxy[keep].astype(np.float32, copy=False),
        "scores": scores[keep].astype(np.float32, copy=False),
        "masks": masks[keep].astype(bool, copy=False),
    }


def _empty_output_arrays(image_shape: tuple[int, int]) -> dict[str, np.ndarray]:
    height, width = image_shape
    return {
        "bboxes_xyxy": np.zeros((0, 4), dtype=np.float32),
        "scores": np.zeros((0,), dtype=np.float32),
        "masks": np.zeros((0, int(height), int(width)), dtype=bool),
    }


def _normalize_output_masks(value: Any, *, image_shape: tuple[int, int]) -> np.ndarray:
    height, width = image_shape
    masks = np.asarray(_tensor_to_numpy(value), dtype=bool)
    if masks.size == 0:
        return np.zeros((0, int(height), int(width)), dtype=bool)
    if masks.ndim == 4 and masks.shape[0] == 1:
        masks = masks[0]
    if masks.ndim == 4 and masks.shape[1] == 1:
        masks = masks[:, 0, :, :]
    if masks.ndim == 2:
        masks = masks[None, :, :]
    if masks.ndim != 3:
        return np.zeros((0, int(height), int(width)), dtype=bool)
    return masks.astype(bool, copy=False)


def _masks_from_official_state(
    state: dict[str, Any],
    *,
    mask_threshold: float,
    image_shape: tuple[int, int],
    result_count: int,
) -> np.ndarray:
    if "masks_logits" in state:
        masks = _tensor_to_numpy(state["masks_logits"]) > float(mask_threshold)
    else:
        masks = _tensor_to_numpy(state.get("masks", [])).astype(bool, copy=False)
    normalized = _normalize_output_masks(masks, image_shape=image_shape)
    if normalized.size == 0:
        height, width = image_shape
        return np.zeros((int(result_count), int(height), int(width)), dtype=bool)
    return normalized


def _boxes_from_masks(masks: np.ndarray) -> np.ndarray:
    boxes: list[tuple[float, float, float, float]] = []
    for mask in np.asarray(masks, dtype=bool):
        y_indices, x_indices = np.nonzero(mask)
        if y_indices.size == 0 or x_indices.size == 0:
            boxes.append((0.0, 0.0, 0.0, 0.0))
            continue
        boxes.append(
            (
                float(x_indices.min()),
                float(y_indices.min()),
                float(x_indices.max() + 1),
                float(y_indices.max() + 1),
            )
        )
    return np.asarray(boxes, dtype=np.float32).reshape((-1, 4))


def _xyxy_to_normalized_cxcywh(
    box_xyxy: np.ndarray,
    *,
    image_width: int,
    image_height: int,
) -> np.ndarray:
    x1, y1, x2, y2 = np.asarray(box_xyxy, dtype=np.float32).reshape((4,))
    width = max(0.0, float(x2) - float(x1))
    height = max(0.0, float(y2) - float(y1))
    center_x = float(x1) + width / 2.0
    center_y = float(y1) + height / 2.0
    return np.asarray(
        [
            center_x / max(1.0, float(image_width)),
            center_y / max(1.0, float(image_height)),
            width / max(1.0, float(image_width)),
            height / max(1.0, float(image_height)),
        ],
        dtype=np.float32,
    )


def _resolve_sam31_checkpoint(downloader) -> Path:
    try:
        return Path(downloader(version="sam3.1"))
    except Exception as exc:
        raise RuntimeError(
            "Official SAM3.1 checkpoint could not be downloaded. Configure Hugging "
            "Face access or provide a cached facebook/sam3.1 checkpoint."
        ) from exc


def _choose_device(device_arg: str, torch_module) -> str:
    if device_arg != "auto":
        return device_arg
    return "cuda" if torch_module.cuda.is_available() else "cpu"


def _cuda_bfloat16_autocast_context(torch_module, device: str):
    if str(device).startswith("cuda"):
        return torch_module.autocast("cuda", dtype=torch_module.bfloat16)
    return nullcontext()


def _tensor_to_numpy(value: Any) -> np.ndarray:
    if value is None:
        return np.asarray([])
    if hasattr(value, "detach"):
        cpu_value = value.detach().cpu()
        if str(getattr(cpu_value, "dtype", "")) in {"torch.bfloat16", "torch.float16"}:
            cpu_value = cpu_value.float()
        return cpu_value.numpy()
    return np.asarray(value)


def _write_output_npz(
    path: str | Path,
    *,
    output_arrays: dict[str, np.ndarray],
    backend: str,
    model_id: str,
    device: str,
) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    masks = np.asarray(output_arrays["masks"], dtype=bool)
    np.savez_compressed(
        path,
        bboxes_xyxy=output_arrays["bboxes_xyxy"],
        boxes=output_arrays["bboxes_xyxy"],
        scores=output_arrays["scores"],
        masks=masks,
        areas=masks.reshape((masks.shape[0], -1)).sum(axis=1).astype(np.float32),
        backend=np.asarray(str(backend)),
        model_id=np.asarray(str(model_id)),
        device=np.asarray(str(device)),
    )
