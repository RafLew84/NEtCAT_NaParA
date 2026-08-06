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
from .classifier_contract import (
    ABC_DOMAIN_SUMMARY_CONSERVATIVE_V1,
    ClassifierConfiguration,
    ClassifierIdentity,
    DomainAggregationPreset,
    DomainLabelReason,
    DomainLabelSummary,
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
    "ABC_DOMAIN_SUMMARY_CONSERVATIVE_V1",
    "ABC_ORIENTATION_CLASSIFIER_ID",
    "ClassifierAnalysisError",
    "ClassifierConfiguration",
    "ClassifierIdentity",
    "ClassifierMoleculeInput",
    "ClassifierMoleculePrediction",
    "ClassifierOutcome",
    "DomainAggregationPreset",
    "DomainAnalysisFrame",
    "DomainAnalysisEvent",
    "DomainAnalysisEventStatus",
    "DomainAnalysisFailure",
    "DomainAnalysisModule",
    "DomainAnalysisRequest",
    "DomainAnalysisResult",
    "DomainAnalysisSeries",
    "DomainLabelSummary",
    "DomainLabelReason",
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
