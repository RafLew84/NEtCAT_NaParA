"""Parameters defining the native descriptor method and its class catalogue."""

from typing import Any
from stmdomains.analysis.domain_settings import DomainSettings

PARAMETERS: dict[str, Any] = {
    "method_version": "stm-domains-local-1", "k": 5, "seed": 24,
    "descriptor_radial_bins": 14, "descriptor_angle_bins": 36, "descriptor_sigma_factor": 1.25,
    "descriptor_pair_distance_range": [.55, 2.8], "pca_max_components": 24,
    **DomainSettings().parameters(),
    "class_margin": .075, "class_radius_quantile": .95, "class_radius_multiplier": 1.10,
    "order_radius_factor": 3., "order_sigma_factor": 4 / 3,
    "order_frequency_range_in_inverse_spacings": [.5, 2.], "order_frequency_count": 22,
    "order_angle_count": 48, "order_minimum_local_count": 10, "order_minimum_effective_count": 8.,
    "maximum_input_detections": 3000,
    "maximum_image_pixels": 4_194_304,
}
COLORS = ("#10b9bd", "#f5b343", "#e366b6", "#9075db", "#66c26d", "#5b9de3", "#e77b54", "#c5c94d")


def model_parameters(k: int) -> dict[str, Any]:
    return {key: k if key == "k" else value for key, value in PARAMETERS.items()
            if key not in DomainSettings().parameters()}
