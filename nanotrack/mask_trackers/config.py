"""Runtime configuration for optional subprocess-based mask trackers."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path


PROJECTS_ROOT = Path(r"C:\Users\rlewa\Documents\PROJEKTY")
TRACKLEED_MODELS_ROOT = Path(r"C:\Users\rlewa\Documents\PROJEKTY\trackleed\tracking_models")

DEFAULT_SAM2_PYTHON = Path(r"C:\Users\rlewa\anaconda3\envs\sam2\python.exe")
DEFAULT_SAM2_REPO_PATH = Path(r"C:\Users\rlewa\Documents\PROJEKTY\sam2")
DEFAULT_SAM2_MODELS_DIR = Path(r"C:\Users\rlewa\Documents\PROJEKTY\trackleed\tracking_models\sam2")
DEFAULT_SAM2_CHECKPOINT = Path(
    r"C:\Users\rlewa\Documents\PROJEKTY\trackleed\tracking_models\sam2\sam2.1_hiera_base_plus.pt"
)

DEFAULT_DAM4SAM_PYTHON = Path(r"C:\Users\rlewa\anaconda3\envs\dam4sam\python.exe")
DEFAULT_DAM4SAM_REPO_PATH = Path(r"C:\Users\rlewa\Documents\PROJEKTY\dam4sam")
DEFAULT_DAM4SAM_MODELS_DIR = Path(r"C:\Users\rlewa\Documents\PROJEKTY\trackleed\tracking_models\dam4sam")
DEFAULT_DAM4SAM_TRACKER_VARIANT = "sam21pp-B"

DEFAULT_SAMURAI_PYTHON = Path(r"C:\Users\rlewa\anaconda3\envs\samurai\python.exe")
DEFAULT_SAMURAI_REPO_PATH = Path(r"C:\Users\rlewa\Documents\PROJEKTY\samurai")
DEFAULT_SAMURAI_MODELS_DIR = Path(r"C:\Users\rlewa\Documents\PROJEKTY\trackleed\tracking_models\samurai")
DEFAULT_SAMURAI_MODEL_VARIANT = "sam2.1_hiera_base_plus"


DAM4SAM_TRACKER_VARIANTS: dict[str, tuple[str, str]] = {
    "sam21pp-L": ("sam2.1_hiera_large.pt", "sam21pp_hiera_l.yaml"),
    "sam21pp-B": ("sam2.1_hiera_base_plus.pt", "sam21pp_hiera_b+.yaml"),
    "sam21pp-S": ("sam2.1_hiera_small.pt", "sam21pp_hiera_s.yaml"),
    "sam21pp-T": ("sam2.1_hiera_tiny.pt", "sam21pp_hiera_t.yaml"),
}

DAM4SAM_VARIANT_ALIASES = {
    "sam21pp-b+": "sam21pp-B",
    "sam21pp-b_plus": "sam21pp-B",
    "sam21pp-base-plus": "sam21pp-B",
    "sam21pp-base_plus": "sam21pp-B",
    "sam21pp-base": "sam21pp-B",
    "sam21pp-l": "sam21pp-L",
    "sam21pp-large": "sam21pp-L",
    "sam21pp-s": "sam21pp-S",
    "sam21pp-small": "sam21pp-S",
    "sam21pp-t": "sam21pp-T",
    "sam21pp-tiny": "sam21pp-T",
}

SAMURAI_MODEL_VARIANTS: dict[str, tuple[str, str]] = {
    "sam2.1_hiera_large": ("sam2.1_hiera_large.pt", "configs/samurai/sam2.1_hiera_l.yaml"),
    "sam2.1_hiera_base_plus": (
        "sam2.1_hiera_base_plus.pt",
        "configs/samurai/sam2.1_hiera_b+.yaml",
    ),
    "sam2.1_hiera_small": ("sam2.1_hiera_small.pt", "configs/samurai/sam2.1_hiera_s.yaml"),
    "sam2.1_hiera_tiny": ("sam2.1_hiera_tiny.pt", "configs/samurai/sam2.1_hiera_t.yaml"),
}

SAMURAI_VARIANT_ALIASES = {
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

DEFAULT_DAM4SAM_CHECKPOINT = (
    DEFAULT_DAM4SAM_MODELS_DIR
    / DAM4SAM_TRACKER_VARIANTS[DEFAULT_DAM4SAM_TRACKER_VARIANT][0]
)
DEFAULT_SAMURAI_CHECKPOINT = (
    DEFAULT_SAMURAI_MODELS_DIR
    / SAMURAI_MODEL_VARIANTS[DEFAULT_SAMURAI_MODEL_VARIANT][0]
)


class MaskTrackerKind(str, Enum):
    """Known mask-tracker backends exposed by NanoTrack."""

    SAM2 = "sam2"
    DAM4SAM = "dam4sam"
    SAMURAI = "samurai"

    @classmethod
    def from_value(cls, value: "MaskTrackerKind | str") -> "MaskTrackerKind":
        if isinstance(value, cls):
            return value
        normalized = str(value).strip().lower()
        for kind in cls:
            if normalized == kind.value:
                return kind
        raise ValueError(f"Unsupported mask tracker kind: {value!r}.")


MASK_TRACKER_KINDS = (
    MaskTrackerKind.SAM2,
    MaskTrackerKind.DAM4SAM,
    MaskTrackerKind.SAMURAI,
)


@dataclass(frozen=True)
class MaskTrackerBackendConfig:
    """Runtime configuration shared by subprocess-based mask trackers."""

    kind: MaskTrackerKind | str
    python_executable: str | Path
    worker_script: str | Path
    models_dir: str | Path
    checkpoint_path: str | Path
    repo_path: str | Path | None = None
    variant: str | None = None
    config_identifier: str | None = None
    device: str = "auto"
    timeout_sec: float = 600.0
    working_directory: str | Path | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "kind", MaskTrackerKind.from_value(self.kind))
        if self.timeout_sec <= 0:
            raise ValueError("timeout_sec must be positive.")
        if self.variant is not None and not str(self.variant).strip():
            raise ValueError("variant must be non-empty when provided.")


def default_mask_tracker_config(kind: MaskTrackerKind | str) -> MaskTrackerBackendConfig:
    tracker_kind = MaskTrackerKind.from_value(kind)
    if tracker_kind is MaskTrackerKind.SAM2:
        return MaskTrackerBackendConfig(
            kind=tracker_kind,
            python_executable=DEFAULT_SAM2_PYTHON,
            worker_script=_sam2_worker_script(),
            models_dir=DEFAULT_SAM2_MODELS_DIR,
            checkpoint_path=DEFAULT_SAM2_CHECKPOINT,
            repo_path=DEFAULT_SAM2_REPO_PATH,
            timeout_sec=600.0,
        )
    if tracker_kind is MaskTrackerKind.DAM4SAM:
        return MaskTrackerBackendConfig(
            kind=tracker_kind,
            python_executable=DEFAULT_DAM4SAM_PYTHON,
            worker_script=Path(__file__).with_name("run_dam4sam_subprocess.py"),
            models_dir=DEFAULT_DAM4SAM_MODELS_DIR,
            checkpoint_path=DEFAULT_DAM4SAM_CHECKPOINT,
            repo_path=DEFAULT_DAM4SAM_REPO_PATH,
            variant=DEFAULT_DAM4SAM_TRACKER_VARIANT,
            config_identifier=config_identifier_for_kind(tracker_kind, DEFAULT_DAM4SAM_TRACKER_VARIANT),
            timeout_sec=1800.0,
        )
    if tracker_kind is MaskTrackerKind.SAMURAI:
        return MaskTrackerBackendConfig(
            kind=tracker_kind,
            python_executable=DEFAULT_SAMURAI_PYTHON,
            worker_script=Path(__file__).with_name("run_samurai_subprocess.py"),
            models_dir=DEFAULT_SAMURAI_MODELS_DIR,
            checkpoint_path=DEFAULT_SAMURAI_CHECKPOINT,
            repo_path=DEFAULT_SAMURAI_REPO_PATH,
            variant=DEFAULT_SAMURAI_MODEL_VARIANT,
            config_identifier=config_identifier_for_kind(tracker_kind, DEFAULT_SAMURAI_MODEL_VARIANT),
            timeout_sec=1800.0,
        )
    raise AssertionError(f"Unhandled mask tracker kind: {tracker_kind!r}")


def checkpoint_name_for_kind(kind: MaskTrackerKind | str, variant: str | None = None) -> str:
    tracker_kind = MaskTrackerKind.from_value(kind)
    if tracker_kind is MaskTrackerKind.SAM2:
        return DEFAULT_SAM2_CHECKPOINT.name
    if tracker_kind is MaskTrackerKind.DAM4SAM:
        normalized_variant = _normalize_dam4sam_variant(variant or DEFAULT_DAM4SAM_TRACKER_VARIANT)
        return DAM4SAM_TRACKER_VARIANTS[normalized_variant][0]
    if tracker_kind is MaskTrackerKind.SAMURAI:
        normalized_variant = _normalize_samurai_variant(variant or DEFAULT_SAMURAI_MODEL_VARIANT)
        return SAMURAI_MODEL_VARIANTS[normalized_variant][0]
    raise AssertionError(f"Unhandled mask tracker kind: {tracker_kind!r}")


def config_identifier_for_kind(kind: MaskTrackerKind | str, variant: str | None = None) -> str | None:
    tracker_kind = MaskTrackerKind.from_value(kind)
    if tracker_kind is MaskTrackerKind.SAM2:
        return None
    if tracker_kind is MaskTrackerKind.DAM4SAM:
        normalized_variant = _normalize_dam4sam_variant(variant or DEFAULT_DAM4SAM_TRACKER_VARIANT)
        return DAM4SAM_TRACKER_VARIANTS[normalized_variant][1]
    if tracker_kind is MaskTrackerKind.SAMURAI:
        normalized_variant = _normalize_samurai_variant(variant or DEFAULT_SAMURAI_MODEL_VARIANT)
        return SAMURAI_MODEL_VARIANTS[normalized_variant][1]
    raise AssertionError(f"Unhandled mask tracker kind: {tracker_kind!r}")


def _normalize_dam4sam_variant(variant: str) -> str:
    normalized = str(variant).strip()
    if normalized in DAM4SAM_TRACKER_VARIANTS:
        return normalized
    alias_key = normalized.lower()
    if alias_key in DAM4SAM_VARIANT_ALIASES:
        return DAM4SAM_VARIANT_ALIASES[alias_key]
    raise ValueError(f"Unsupported DAM4SAM tracker variant: {variant!r}.")


def _normalize_samurai_variant(variant: str) -> str:
    normalized = str(variant).strip()
    if normalized in SAMURAI_MODEL_VARIANTS:
        return normalized
    alias_key = normalized.lower()
    if alias_key in SAMURAI_VARIANT_ALIASES:
        return SAMURAI_VARIANT_ALIASES[alias_key]
    raise ValueError(f"Unsupported SAMURAI model variant: {variant!r}.")


def _sam2_worker_script() -> Path:
    return Path(__file__).resolve().parents[1] / "sam2" / "run_sam2_subprocess.py"
