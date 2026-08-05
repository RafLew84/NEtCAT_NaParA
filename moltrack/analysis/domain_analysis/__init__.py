"""Public synchronous interface for unified M6-gated Domain Analysis."""

from .classifier_models import (
    ClassifierMoleculeInput,
    ClassifierMoleculePrediction,
    ClassifierOutcome,
    MoleculeClassification,
)
from .classifier_runner import (
    ClassifierAnalysisError,
    MoleculeClassifierAdapter,
)

from .geometry import (
    DomainAnalysisFrame,
    DomainAnalysisSeries,
    GeometryMode,
    M6AnalyzedMolecule,
    M6CanonicalFrame,
    M6FrameGeometry,
    M6PresentationProvenance,
    M6SourceAnnotation,
)
from .models import (
    DomainAnalysisEvent,
    DomainAnalysisEventStatus,
    DomainAnalysisFailure,
    DomainAnalysisRequest,
    DomainAnalysisResult,
    M6ComponentMembership,
    M6FrameComputation,
    M6FrameGate,
    M6Gate,
    M6PublishedComponent,
)
from .module import DomainAnalysisModule, M6Adapter, M6FrameAnalysisError
from .texture_abc_adapter import (
    ABC_ORIENTATION_CLASSIFIER_ID,
    TextureABCClassifierAdapter,
)

__all__ = [
    "DomainAnalysisFrame",
    "ABC_ORIENTATION_CLASSIFIER_ID",
    "ClassifierAnalysisError",
    "ClassifierMoleculeInput",
    "ClassifierMoleculePrediction",
    "ClassifierOutcome",
    "DomainAnalysisEvent",
    "DomainAnalysisEventStatus",
    "DomainAnalysisFailure",
    "DomainAnalysisModule",
    "DomainAnalysisRequest",
    "DomainAnalysisResult",
    "DomainAnalysisSeries",
    "GeometryMode",
    "M6Adapter",
    "M6AnalyzedMolecule",
    "M6CanonicalFrame",
    "M6ComponentMembership",
    "M6FrameComputation",
    "M6FrameAnalysisError",
    "M6FrameGate",
    "M6FrameGeometry",
    "M6Gate",
    "M6PublishedComponent",
    "M6PresentationProvenance",
    "M6SourceAnnotation",
    "MoleculeClassification",
    "MoleculeClassifierAdapter",
    "TextureABCClassifierAdapter",
]
