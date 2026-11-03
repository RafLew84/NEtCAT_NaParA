"""Parameters defining the native descriptor method and its class catalogue."""

from typing import Any
from stmdomains.analysis.acceptance_settings import ClassAcceptanceSettings
from stmdomains.analysis.domain_settings import DomainSettings
from stmdomains.analysis.order_settings import OrderSettings
from stmdomains.analysis.descriptor_settings import DescriptorSettings

PARAMETERS: dict[str, Any] = {
    "method_version": "stm-domains-local-1", "k": 5, "seed": 24,
    **DescriptorSettings().parameters(),
    **DomainSettings().parameters(),
    **ClassAcceptanceSettings().parameters(), "class_radius_quantile": .95,
    **OrderSettings().parameters(),
    "order_frequency_range_in_inverse_spacings": [.5, 2.], "order_frequency_count": 22,
    "order_angle_count": 48,
    "maximum_input_detections": 3000,
    "maximum_image_pixels": 4_194_304,
}
COLORS = ("#10b9bd", "#f5b343", "#e366b6", "#9075db", "#66c26d", "#5b9de3", "#e77b54", "#c5c94d")


def model_parameters(k: int, descriptor_settings: DescriptorSettings = DescriptorSettings()) -> dict[str, Any]:
    return {key: k if key == "k" else value for key, value in {**PARAMETERS, **descriptor_settings.parameters()}.items()
            if key not in DomainSettings().parameters() and key not in ClassAcceptanceSettings().parameters()
            and key not in OrderSettings().parameters()}
