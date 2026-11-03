"""Controlled external LoFTR and textured original pairs with real image borders."""

from dataclasses import dataclass, field

import numpy as np
import pytest
from scipy.ndimage import gaussian_filter, map_coordinates

from make_registration_fixtures import frames_with_data


def textured_pair(shift_xy=(18.25, -12.5)):
    field = gaussian_filter(np.random.default_rng(430).normal(size=(224, 288)), 1.4)
    yy, xx = np.mgrid[48:176, 48:240].astype(float)
    reference = map_coordinates(field, [yy, xx], order=1)
    moving = map_coordinates(field, [yy + shift_xy[1], xx + shift_xy[0]], order=1)
    return frames_with_data(reference, moving)


@dataclass
class MatcherControl:
    shifts: list = field(default_factory=lambda: [(19.0, -12.0)])
    calls: int = 0
    loaded: int = 0
    error: str | None = None
    weak: bool = False
    invalid: bool = False


@pytest.fixture
def controlled_loftr(monkeypatch, tmp_path):
    import torch
    import kornia.feature

    control = MatcherControl()

    class ControlledLoFTR(torch.nn.Module):
        def __init__(self, pretrained):
            super().__init__()
            assert pretrained is None
            self.scale = torch.nn.Parameter(torch.ones(1))
            control.loaded += 1

        def forward(self, images):
            index = control.calls
            control.calls += 1
            if control.error:
                raise RuntimeError(control.error)
            points = torch.tensor([[30, 30], [50, 30], [70, 30], [90, 30],
                                   [30, 60], [50, 60], [70, 60], [90, 60]],
                                  dtype=torch.float32, device=self.scale.device)
            shift = points.new_tensor(control.shifts[min(index, len(control.shifts) - 1)])
            moving = points - shift
            if control.weak:
                extra = points[:1].repeat(12, 1)
                extra_moving = extra - torch.arange(12, device=points.device)[:, None] * 10 - 50
                points, moving = torch.cat([points, extra]), torch.cat([moving, extra_moving])
            if control.invalid:
                moving[:] = float('nan')
            return {'keypoints0': points, 'keypoints1': moving,
                    'confidence': torch.ones(len(points), device=self.scale.device)}

    def forbidden(*args, **kwargs):
        pytest.fail('Hybrid path attempted a model download')

    monkeypatch.setattr(torch.hub, 'load_state_dict_from_url', forbidden)
    monkeypatch.setattr(torch.hub, 'download_url_to_file', forbidden)
    monkeypatch.setattr(kornia.feature, 'LoFTR', ControlledLoFTR)
    path = tmp_path / 'local.ckpt'
    torch.save({'state_dict': {'scale': torch.ones(1)}}, path)
    return control, path
