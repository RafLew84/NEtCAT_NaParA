"""Identity and ordered provenance of the current preprocessing result."""

from __future__ import annotations

from dataclasses import dataclass, field
from uuid import uuid4


@dataclass(frozen=True)
class PreprocessingStep:
    """An open-ended operation, rather than an enum of supported pipelines."""

    method: str
    label: str
    parameters: dict[str, float | int | str] = field(default_factory=dict)


@dataclass(frozen=True)
class PreprocessingProvenance:
    steps: tuple[PreprocessingStep, ...] = ()
    history_known: bool = True
    revision: str = field(default_factory=lambda: uuid4().hex)

    def append(self, step: PreprocessingStep) -> PreprocessingProvenance:
        return PreprocessingProvenance(self.steps + (step,), self.history_known)

    def description(self) -> str:
        parts = ["Oryginał" if self.history_known else "Nieznane pochodzenie (starszy wynik)"]
        for step in self.steps:
            params = ", ".join(f"{key}={value}" for key, value in step.parameters.items())
            parts.append(f"{step.label} ({params})" if params else step.label)
        return " → ".join(parts)
