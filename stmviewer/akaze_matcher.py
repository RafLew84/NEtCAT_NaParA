"""Local CPU AKAZE/MLDB correspondences and original-pixel translation consensus."""
from dataclasses import asdict, replace
from hashlib import sha256
from typing import Any, Callable

import numpy as np
from numpy.typing import NDArray

from stmviewer.method_parameters import AkazeParameters, ContrastParameters
from stmviewer.feature_preparation import prepare_feature_image
from stmviewer.feature_provenance import akaze_detector_text, profile_text
from nanotrack.core import RegistrationFrameResult
from stmviewer.correspondence_consensus import CorrespondenceConfig, estimate_correspondence_translation
from stmviewer.correspondence_types import CorrespondenceDiagnostics, CorrespondenceRefusal, ImagePreparation

AKAZE_METHOD = 'akaze'
AKAZE_LABEL = 'AKAZE'
ADAPTER_VERSION = 'akaze-mldb-crosscheck-v1'
DETECTOR_CONFIG = ('AKAZE; descriptor_type=MLDB; descriptor_size=0; descriptor_channels=3; '
                   'threshold=0.001; nOctaves=4; nOctaveLayers=4; diffusivity=DIFF_PM_G2; max_points=-1')
MATCHER_CONFIG = 'BFMatcher; NORM_HAMMING; crossCheck=True'
NORMALIZATION = 'minmax-uint8-round-v1'


def prepare_akaze_image(data: NDArray[np.float64], contrast: ContrastParameters = ContrastParameters()) -> tuple[NDArray[np.uint8], ImagePreparation]:
    """Map finite measurement values to uint8, preserving the original pixel grid."""
    normalized, preparation = prepare_feature_image(data, contrast, uint8=True)
    return np.asarray(normalized, dtype=np.uint8), preparation


class AkazeBackend:
    """One detector/matcher per task; no neural runtime, network, or CUDA state."""

    def __init__(self, *, parameters: AkazeParameters = AkazeParameters(),
                 cancelled: Callable[[], bool] | None = None,
                 progress: Callable[[str], None] | None = None) -> None:
        self._cancelled, self._progress = cancelled, progress
        self.parameters = parameters
        self.config = CorrespondenceConfig(inlier_radius=parameters.radius)
        self.device = 'CPU'
        self.last_diagnostics: CorrespondenceDiagnostics | None = None
        self._checkpoint()
        import cv2
        factory = getattr(cv2, 'AKAZE_create', None)
        if not callable(factory) or not callable(getattr(cv2, 'BFMatcher', None)):
            raise ValueError('OpenCV: brak AKAZE_create lub BFMatcher.')
        self._detector: Any = factory(
            descriptor_type=cv2.AKAZE_DESCRIPTOR_MLDB, descriptor_size=0, descriptor_channels=3,
            threshold=parameters.threshold, nOctaves=4, nOctaveLayers=4, diffusivity=cv2.KAZE_DIFF_PM_G2, max_points=-1)
        self._matcher: Any = cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=True)
        self.provenance = tuple(sorted({
            'model': AKAZE_LABEL, 'adapter_version': ADAPTER_VERSION,
            'detector': akaze_detector_text(parameters), 'matcher': MATCHER_CONFIG,
            'parameter_profile': profile_text(AKAZE_METHOD, parameters),
            'selection': 'all mutual matches; no distance cutoff or score weighting',
            'preprocessing': parameters.contrast.normalization(uint8=True) + '; native; no padding',
            'coordinate_mapping': 'original-pixels; scale_xy=1,1',
            'aggregation': 'translation-consensus-v2',
            'requested_device': 'cpu', 'actual_device': 'CPU',
            'library_opencv': cv2.__version__,
            'opencv_build_sha256': sha256(cv2.getBuildInformation().encode()).hexdigest(),
        }.items()))
        self.settings_text = ('AKAZE; CPU; ' + akaze_detector_text(parameters) + '; ' + MATCHER_CONFIG
                              + '; ' + profile_text(AKAZE_METHOD, parameters) + '; rozmiar original; bez paddingu; '
                              'translation-consensus-v2; Hamming nie jest oceną pewności dryfu; '
                              + '; '.join(f'{k}={v}' for k, v in asdict(self.config).items()))
        self._checkpoint()

    def _checkpoint(self) -> None:
        if self._cancelled is not None and self._cancelled():
            from stmviewer.registration import RegistrationCancelled
            raise RegistrationCancelled

    def _report(self, text: str) -> None:
        self._checkpoint()
        if self._progress is not None:
            self._progress('AKAZE: ' + text)
        self._checkpoint()

    def estimate(self, reference_frame: NDArray[np.float64], moving_frame: NDArray[np.float64],
                 *, moving_frame_index: int) -> RegistrationFrameResult:
        self.last_diagnostics = None
        self._checkpoint()
        if self._detector is None or self._matcher is None:
            raise ValueError('AKAZE: zasoby zadania zostały zwolnione.')
        reference, rp = prepare_akaze_image(reference_frame, self.parameters.contrast)
        moving, mp = prepare_akaze_image(moving_frame, self.parameters.contrast)
        self._report('punkty i deskryptory obrazu odniesienia')
        k0, d0 = (self._detector.detectAndCompute(reference, None)
                  if min(reference.shape) >= 2 and reference.min() != reference.max() else ((), None))
        self._report('punkty i deskryptory obrazu przesuwanego')
        k1, d1 = (self._detector.detectAndCompute(moving, None)
                  if min(moving.shape) >= 2 and moving.min() != moving.max() else ((), None))
        self._report('wzajemne dopasowanie Hamming')
        if d0 is None or d1 is None or not len(d0) or not len(d1):
            p0 = p1 = np.empty((0, 2), dtype=np.float64)
        else:
            if d0.dtype != np.uint8 or d1.dtype != np.uint8:
                raise ValueError('AKAZE: oczekiwano binarnych deskryptorów MLDB.')
            matches = self._matcher.match(d0, d1)
            p0 = np.asarray([k0[m.queryIdx].pt for m in matches], dtype=np.float64).reshape(-1, 2)
            p1 = np.asarray([k1[m.trainIdx].pt for m in matches], dtype=np.float64).reshape(-1, 2)
        self._report('konsensus przesunięcia w pikselach original')
        try:
            evidence = estimate_correspondence_translation(
                p0, p1, rp.original_shape, mp.original_shape,
                config=self.config, cancelled=self._cancelled)
        except CorrespondenceRefusal as error:
            evidence = replace(error.diagnostics, preparation=(rp, mp), model_provenance=self.provenance)
            self.last_diagnostics = evidence
            raise CorrespondenceRefusal(evidence) from error
        evidence = replace(evidence, preparation=(rp, mp), model_provenance=self.provenance)
        self.last_diagnostics = evidence
        assert evidence.final_shift_xy is not None
        return RegistrationFrameResult(moving_frame_index, evidence.final_shift_xy,
                                       AKAZE_METHOD, status=evidence.status)

    def close(self) -> None:
        self._detector = self._matcher = None
