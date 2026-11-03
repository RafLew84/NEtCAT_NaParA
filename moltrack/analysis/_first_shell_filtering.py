from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


_FirstShellPairClassification = Literal[
    "geometry_duplicate",
    "physical_duplicate",
    "short_non_shell_pair",
    "first_shell",
    "long_non_shell_pair",
]


@dataclass(frozen=True)
class _FirstShellDistancePolicy:
    geometry_collision_epsilon_nm: float
    duplicate_detection_enabled: bool
    duplicate_max_distance_nm: float
    first_shell_r_min_nm: float
    first_shell_r_max_nm: float

    def __post_init__(self) -> None:
        if self.geometry_collision_epsilon_nm >= self.first_shell_r_min_nm:
            raise ValueError(
                "geometry_collision_epsilon_nm must be less than "
                "first_shell_r_min_nm."
            )
        if self.duplicate_detection_enabled and not (
            self.geometry_collision_epsilon_nm
            < self.duplicate_max_distance_nm
            < self.first_shell_r_min_nm
        ):
            raise ValueError(
                "Active duplicate detection requires geometry_collision_epsilon_nm "
                "< duplicate_max_distance_nm < first_shell_r_min_nm."
            )

    def classify(self, distance_nm: float) -> _FirstShellPairClassification:
        if distance_nm <= self.geometry_collision_epsilon_nm:
            return "geometry_duplicate"
        if self.duplicate_detection_enabled and distance_nm <= self.duplicate_max_distance_nm:
            return "physical_duplicate"
        if distance_nm < self.first_shell_r_min_nm:
            return "short_non_shell_pair"
        if distance_nm <= self.first_shell_r_max_nm:
            return "first_shell"
        return "long_non_shell_pair"
