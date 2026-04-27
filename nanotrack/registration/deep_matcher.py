"""Experimental deep-feature matcher backend reduced to translation-only shifts."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

import numpy as np

from nanotrack.core import RegistrationFrameResult

from .phase_correlation import PhaseCorrelationBackendError
from .view import RegistrationViewResult


class DeepMatcherProtocol(Protocol):
    """Protocol for injected feature matchers used by DeepMatcherTranslationBackend."""

    def match(self, reference_frame: np.ndarray, moving_frame: np.ndarray) -> object:
        """Return reference/moving matched points as arrays or a matcher-specific dict."""


@dataclass(frozen=True)
class DeepMatcherTranslationConfig:
    """Runtime configuration for translation-only deep matcher registration."""

    matcher: str = "loftr"
    device: str = "auto"
    pretrained: str = "outdoor"
    min_matches: int = 8
    min_inliers: int = 4
    residual_threshold_px: float = 2.0
    low_confidence_inlier_ratio: float = 0.5

    def __post_init__(self) -> None:
        matcher = str(self.matcher).strip().lower()
        if matcher not in ("loftr", "lightglue", "superglue", "injected"):
            raise ValueError("matcher must be 'loftr', 'lightglue', 'superglue', or 'injected'.")
        object.__setattr__(self, "matcher", matcher)

        device = str(self.device).strip().lower()
        if device not in ("auto", "cpu", "cuda"):
            raise ValueError("device must be 'auto', 'cpu', or 'cuda'.")
        object.__setattr__(self, "device", device)

        pretrained = str(self.pretrained).strip()
        if not pretrained:
            raise ValueError("pretrained must be a non-empty string.")
        object.__setattr__(self, "pretrained", pretrained)

        min_matches = int(self.min_matches)
        if min_matches <= 0:
            raise ValueError("min_matches must be positive.")
        object.__setattr__(self, "min_matches", min_matches)

        min_inliers = int(self.min_inliers)
        if min_inliers <= 0:
            raise ValueError("min_inliers must be positive.")
        object.__setattr__(self, "min_inliers", min_inliers)

        residual_threshold_px = float(self.residual_threshold_px)
        if not np.isfinite(residual_threshold_px) or residual_threshold_px <= 0.0:
            raise ValueError("residual_threshold_px must be a finite positive value.")
        object.__setattr__(self, "residual_threshold_px", residual_threshold_px)

        low_confidence_inlier_ratio = float(self.low_confidence_inlier_ratio)
        if not np.isfinite(low_confidence_inlier_ratio) or not 0.0 < low_confidence_inlier_ratio <= 1.0:
            raise ValueError("low_confidence_inlier_ratio must be in (0, 1].")
        object.__setattr__(self, "low_confidence_inlier_ratio", low_confidence_inlier_ratio)


class DeepMatcherTranslationBackend:
    """Estimate one global translation from feature matches using robust consensus."""

    method_name = "deep_matcher_translation"

    def __init__(
        self,
        config: DeepMatcherTranslationConfig | None = None,
        matcher: DeepMatcherProtocol | None = None,
    ):
        self.config = config or DeepMatcherTranslationConfig()
        if self.config.matcher == "injected" and matcher is None:
            raise ValueError("matcher='injected' requires an injected matcher object.")
        if matcher is not None and not callable(getattr(matcher, "match", None)):
            raise TypeError("matcher must provide a callable match(reference_frame, moving_frame) method.")
        self._matcher = matcher

    def estimate(
        self,
        reference_frame: np.ndarray,
        moving_frame: np.ndarray,
        *,
        moving_frame_index: int,
        reference_mask: np.ndarray | None = None,
        moving_mask: np.ndarray | None = None,
    ) -> RegistrationFrameResult:
        """Return a translation-only shift estimated from feature correspondences."""

        frame_index = int(moving_frame_index)
        if frame_index < 0:
            raise ValueError("moving_frame_index must be non-negative.")

        reference = self._prepare_frame(reference_frame, "reference_frame")
        moving = self._prepare_frame(moving_frame, "moving_frame")
        if reference.shape != moving.shape:
            raise ValueError("reference_frame and moving_frame must have the same shape.")

        reference_mask_bool = self._prepare_optional_mask(reference_mask, reference.shape, "reference_mask")
        moving_mask_bool = self._prepare_optional_mask(moving_mask, moving.shape, "moving_mask")
        matcher = self._matcher or self._build_matcher()
        raw_matches = matcher.match(reference, moving)
        reference_xy, moving_xy, scores = self._normalize_matches(raw_matches)
        reference_xy, moving_xy, scores = self._filter_matches_by_masks(
            reference_xy,
            moving_xy,
            scores,
            reference_mask_bool,
            moving_mask_bool,
        )
        if reference_xy.shape[0] < self.config.min_matches:
            raise PhaseCorrelationBackendError(
                f"Only {reference_xy.shape[0]} feature matches; need at least {self.config.min_matches}."
            )

        translations_xy = reference_xy - moving_xy
        consensus = self._robust_consensus(translations_xy, scores)
        if consensus["num_inliers"] < self.config.min_inliers:
            raise PhaseCorrelationBackendError(
                f"Only {consensus['num_inliers']} inlier feature matches; "
                f"need at least {self.config.min_inliers}."
            )

        inlier_ratio = float(consensus["num_inliers"] / reference_xy.shape[0])
        median_residual = float(consensus["median_residual"])
        residual_quality = 1.0 - min(median_residual / self.config.residual_threshold_px, 1.0)
        quality_score = float(np.clip(0.7 * inlier_ratio + 0.3 * residual_quality, 0.0, 1.0))
        status = "ok" if inlier_ratio >= self.config.low_confidence_inlier_ratio else "low_confidence"
        shift_xy = np.asarray(consensus["shift_xy"], dtype=np.float64)

        return RegistrationFrameResult(
            frame_index=frame_index,
            shift_xy=(float(shift_xy[0]), float(shift_xy[1])),
            method=self.method_name,
            quality_score=quality_score,
            status=status,
        )

    def estimate_pair(
        self,
        registration_view: RegistrationViewResult | np.ndarray,
        *,
        reference_index: int,
        moving_index: int,
        reference_mask: np.ndarray | None = None,
        moving_mask: np.ndarray | None = None,
    ) -> RegistrationFrameResult:
        """Estimate a translation-only shift from matcher correspondences in a frame stack."""

        frames = self._registration_frames(registration_view)
        reference_index = self._normalize_frame_index(reference_index, frames.shape[0], "reference_index")
        moving_index = self._normalize_frame_index(moving_index, frames.shape[0], "moving_index")
        return self.estimate(
            frames[reference_index],
            frames[moving_index],
            moving_frame_index=moving_index,
            reference_mask=reference_mask,
            moving_mask=moving_mask,
        )

    def _build_matcher(self) -> DeepMatcherProtocol:
        if self.config.matcher == "loftr":
            return _KorniaLoFTRMatcher(self.config)
        if self.config.matcher in ("lightglue", "superglue"):
            raise PhaseCorrelationBackendError(
                f"Deep matcher {self.config.matcher!r} is reserved for an optional integration "
                "and is not available in this environment."
            )
        raise PhaseCorrelationBackendError("No deep matcher object was provided.")

    def _robust_consensus(
        self,
        translations_xy: np.ndarray,
        scores: np.ndarray | None,
    ) -> dict[str, object]:
        best_inliers: np.ndarray | None = None
        best_score = -float("inf")
        weights = np.ones(translations_xy.shape[0], dtype=np.float64) if scores is None else scores
        for candidate in translations_xy:
            residuals = np.linalg.norm(translations_xy - candidate, axis=1)
            inliers = residuals <= self.config.residual_threshold_px
            num_inliers = int(np.count_nonzero(inliers))
            if num_inliers == 0:
                continue
            inlier_weight = float(np.sum(weights[inliers]))
            median_residual = float(np.median(residuals[inliers]))
            score = inlier_weight - 1e-6 * median_residual
            if best_inliers is None or score > best_score:
                best_inliers = inliers
                best_score = score

        if best_inliers is None:
            return {"shift_xy": np.asarray([0.0, 0.0]), "num_inliers": 0, "median_residual": float("inf")}

        refined_shift = self._weighted_median(translations_xy[best_inliers], weights[best_inliers])
        refined_residuals = np.linalg.norm(translations_xy - refined_shift, axis=1)
        refined_inliers = refined_residuals <= self.config.residual_threshold_px
        if int(np.count_nonzero(refined_inliers)) >= int(np.count_nonzero(best_inliers)):
            best_inliers = refined_inliers
            refined_shift = self._weighted_median(translations_xy[best_inliers], weights[best_inliers])
            refined_residuals = np.linalg.norm(translations_xy - refined_shift, axis=1)

        return {
            "shift_xy": np.asarray(refined_shift, dtype=np.float64),
            "num_inliers": int(np.count_nonzero(best_inliers)),
            "median_residual": float(np.median(refined_residuals[best_inliers])),
        }

    @staticmethod
    def _weighted_median(values_xy: np.ndarray, weights: np.ndarray) -> np.ndarray:
        if values_xy.shape[0] == 0:
            return np.asarray([0.0, 0.0], dtype=np.float64)
        if not np.all(np.isfinite(weights)) or float(np.sum(weights)) <= 0.0:
            return np.median(values_xy, axis=0)
        medians = []
        for axis in range(2):
            order = np.argsort(values_xy[:, axis])
            sorted_values = values_xy[order, axis]
            sorted_weights = weights[order]
            cutoff = 0.5 * float(np.sum(sorted_weights))
            medians.append(float(sorted_values[np.searchsorted(np.cumsum(sorted_weights), cutoff)]))
        return np.asarray(medians, dtype=np.float64)

    @staticmethod
    def _normalize_matches(raw_matches: object) -> tuple[np.ndarray, np.ndarray, np.ndarray | None]:
        scores: np.ndarray | None = None
        if isinstance(raw_matches, dict):
            reference_raw = (
                raw_matches.get("reference_xy")
                if "reference_xy" in raw_matches
                else raw_matches.get("keypoints0", raw_matches.get("mkpts0_f"))
            )
            moving_raw = (
                raw_matches.get("moving_xy")
                if "moving_xy" in raw_matches
                else raw_matches.get("keypoints1", raw_matches.get("mkpts1_f"))
            )
            score_raw = raw_matches.get("scores", raw_matches.get("confidence"))
        elif isinstance(raw_matches, tuple) and len(raw_matches) in (2, 3):
            reference_raw = raw_matches[0]
            moving_raw = raw_matches[1]
            score_raw = raw_matches[2] if len(raw_matches) == 3 else None
        else:
            raise ValueError("matcher must return a dict or a tuple of matched point arrays.")

        reference_xy = np.asarray(reference_raw, dtype=np.float64)
        moving_xy = np.asarray(moving_raw, dtype=np.float64)
        if reference_xy.ndim != 2 or reference_xy.shape[1] != 2:
            raise ValueError("reference matched points must have shape (N, 2).")
        if moving_xy.ndim != 2 or moving_xy.shape != reference_xy.shape:
            raise ValueError("moving matched points must have shape matching reference points.")
        if not np.all(np.isfinite(reference_xy)) or not np.all(np.isfinite(moving_xy)):
            raise ValueError("matched points must contain only finite values.")

        if score_raw is not None:
            scores = np.asarray(score_raw, dtype=np.float64).reshape((-1,))
            if scores.shape[0] != reference_xy.shape[0]:
                raise ValueError("match scores must have one value per match.")
            if not np.all(np.isfinite(scores)):
                raise ValueError("match scores must contain only finite values.")
            scores = np.maximum(scores, 0.0)
        return reference_xy, moving_xy, scores

    def _filter_matches_by_masks(
        self,
        reference_xy: np.ndarray,
        moving_xy: np.ndarray,
        scores: np.ndarray | None,
        reference_mask: np.ndarray | None,
        moving_mask: np.ndarray | None,
    ) -> tuple[np.ndarray, np.ndarray, np.ndarray | None]:
        keep = np.ones(reference_xy.shape[0], dtype=bool)
        if reference_mask is not None:
            keep &= self._points_inside_mask(reference_xy, reference_mask)
        if moving_mask is not None:
            keep &= self._points_inside_mask(moving_xy, moving_mask)
        filtered_scores = None if scores is None else scores[keep]
        return reference_xy[keep], moving_xy[keep], filtered_scores

    @staticmethod
    def _points_inside_mask(points_xy: np.ndarray, mask: np.ndarray) -> np.ndarray:
        x = np.rint(points_xy[:, 0]).astype(np.int64)
        y = np.rint(points_xy[:, 1]).astype(np.int64)
        inside = (0 <= x) & (x < mask.shape[1]) & (0 <= y) & (y < mask.shape[0])
        keep = np.zeros(points_xy.shape[0], dtype=bool)
        keep[inside] = mask[y[inside], x[inside]]
        return keep

    @staticmethod
    def _prepare_frame(frame: np.ndarray, name: str) -> np.ndarray:
        prepared = np.asarray(frame, dtype=np.float32)
        if prepared.ndim != 2:
            raise ValueError(f"{name} must be a 2D image.")
        if prepared.shape[0] < 1 or prepared.shape[1] < 1:
            raise ValueError(f"{name} must be non-empty.")
        if not np.all(np.isfinite(prepared)):
            raise ValueError(f"{name} must contain only finite values.")
        return prepared

    @staticmethod
    def _prepare_optional_mask(mask: np.ndarray | None, frame_shape: tuple[int, int], name: str) -> np.ndarray | None:
        if mask is None:
            return None
        prepared = np.asarray(mask, dtype=bool)
        if prepared.ndim != 2:
            raise ValueError(f"{name} must be a 2D boolean image.")
        if prepared.shape != frame_shape:
            raise ValueError(f"{name} shape must match registration frame shape.")
        if not np.any(prepared):
            raise ValueError(f"{name} must contain at least one valid pixel.")
        return prepared

    @staticmethod
    def _registration_frames(registration_view: RegistrationViewResult | np.ndarray) -> np.ndarray:
        frames = registration_view.frames if isinstance(registration_view, RegistrationViewResult) else registration_view
        stack = np.asarray(frames, dtype=np.float32)
        if stack.ndim != 3:
            raise ValueError("registration_view must be a 3D frame stack.")
        if stack.shape[0] < 1:
            raise ValueError("registration_view must contain at least one frame.")
        if not np.all(np.isfinite(stack)):
            raise ValueError("registration_view must contain only finite values.")
        return stack

    @staticmethod
    def _normalize_frame_index(frame_index: int, frame_count: int, name: str) -> int:
        normalized = int(frame_index)
        if normalized < 0 or normalized >= frame_count:
            raise IndexError(f"{name} is out of registration_view frame range.")
        return normalized


class _KorniaLoFTRMatcher:
    """Lazy optional adapter around kornia.feature.LoFTR."""

    def __init__(self, config: DeepMatcherTranslationConfig):
        try:
            import torch
            from kornia.feature import LoFTR
        except ModuleNotFoundError as exc:
            raise PhaseCorrelationBackendError(
                "LoFTR matcher requires optional dependencies 'torch' and 'kornia'."
            ) from exc

        self._torch = torch
        if config.device == "auto":
            device = "cuda" if torch.cuda.is_available() else "cpu"
        else:
            device = config.device
        self._device = torch.device(device)
        self._model = LoFTR(pretrained=config.pretrained).eval().to(self._device)

    def match(self, reference_frame: np.ndarray, moving_frame: np.ndarray) -> dict[str, np.ndarray]:
        torch = self._torch
        reference_tensor = self._to_tensor(reference_frame)
        moving_tensor = self._to_tensor(moving_frame)
        with torch.no_grad():
            output = self._model({"image0": reference_tensor, "image1": moving_tensor})
        result: dict[str, np.ndarray] = {
            "keypoints0": output["keypoints0"].detach().cpu().numpy(),
            "keypoints1": output["keypoints1"].detach().cpu().numpy(),
        }
        if "confidence" in output:
            result["confidence"] = output["confidence"].detach().cpu().numpy()
        return result

    def _to_tensor(self, frame: np.ndarray):
        frame_array = np.asarray(frame, dtype=np.float32)
        min_value = float(np.min(frame_array))
        max_value = float(np.max(frame_array))
        scale = max(max_value - min_value, float(np.finfo(np.float32).eps))
        normalized = (frame_array - min_value) / scale
        return self._torch.from_numpy(normalized[None, None, :, :]).float().to(self._device)
