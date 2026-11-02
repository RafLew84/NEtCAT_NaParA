"""Versioned feature profiles in portable evidence; no model runtime is imported."""
from dataclasses import asdict
import json

from stmviewer.metadata_values import json_object
from stmviewer.method_parameters import AkazeParameters, LightGlueParameters, FeatureParameters, decode_profile


def profile_text(method: str, parameters: FeatureParameters) -> str:
    return json.dumps({'version': 1, 'method': method, 'values': asdict(parameters)},
                      sort_keys=True, separators=(',', ':'), allow_nan=False)


def recorded_profile(method: str, provenance: tuple[tuple[str, str], ...]) -> FeatureParameters:
    text = dict(provenance).get('parameter_profile')
    if text is None:
        from stmviewer.method_parameters import MethodProfiles
        return MethodProfiles().get(method)
    record = json_object(json.loads(text), {'version', 'method', 'values'})
    if type(record['version']) is not int or record['version'] != 1 or record['method'] != method:
        raise ValueError('Nieobsługiwana wersja lub metoda profilu parametrów.')
    return decode_profile(method, record['values'])


def akaze_detector_text(parameters: AkazeParameters) -> str:
    return ('AKAZE; descriptor_type=MLDB; descriptor_size=0; descriptor_channels=3; '
            f'threshold={parameters.threshold:g}; nOctaves=4; nOctaveLayers=4; '
            'diffusivity=DIFF_PM_G2; max_points=-1')


def lightglue_identity(parameters: 'LightGlueParameters') -> dict[str, str]:
    depth, width = ((-1., -1.) if parameters.full_computation else (.95, .99))
    return {
        'extractor_config': ('SuperPoint; '
            f'max_num_keypoints={parameters.max_keypoints}; detection_threshold={parameters.detection_threshold:g}; '
            f'nms_radius={parameters.nms_radius}; remove_borders=4; descriptor_dim=256'),
        'model_config': ('LightGlue; features=superpoint; n_layers=9; '
            f'filter_threshold={parameters.filter_threshold:g}; depth_confidence={depth:g}; '
            f'width_confidence={width:g}; flash=True; mp=False; compile=False'),
        'max_keypoints': str(parameters.max_keypoints),
        'preprocessing': parameters.contrast.normalization(uint8=False) + '; native; no padding',
        'parameter_profile': profile_text('lightglue_superpoint', parameters),
    }
