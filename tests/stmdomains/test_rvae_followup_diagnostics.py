"""Independent geometry checks for descriptive issue21a angle reporting."""
import numpy as np
import pytest
import torch

from stmdomains.experiments.training.models import RotationalVAE
from stmdomains.experiments.training.rvae_followup.diagnostics import (
    angle_parts, lattice_period_degrees, selected_indices, support_domain, wrap_degrees,
)
from stmdomains.experiments.training.rvae_followup.gallery import document_template


def test_lattice_period_is_computed_without_hexagonal_assumption():
    assert lattice_period_degrees([[12, 0], [0, 12]]) == 90
    assert lattice_period_degrees([[12, 0], [4.2, 12]]) == 180
    assert lattice_period_degrees([[1, 0], [.5, np.sqrt(3) / 2]]) == 60
    assert lattice_period_degrees([[12, 12], [0, 12]]) == 90  # same square lattice, different basis


@pytest.mark.parametrize("turn", [-1, 1])
def test_quarter_turn_sign_matches_spatial_decoder_convention(turn):
    torch.set_num_threads(1)
    torch.manual_seed(1)
    model = RotationalVAE(32)
    latent = torch.zeros(1, 35)
    latent[0, :32] = torch.linspace(-1, 1, 32)
    with torch.inference_mode():
        zero = model.decode(latent)
        latent[0, 32] = -turn * np.pi / 2
        rotated = model.decode(latent)
    torch.testing.assert_close(rotated, torch.rot90(zero, turn, (-2, -1)), rtol=1e-5, atol=1e-7)


def test_support_must_not_cross_a_domain_boundary():
    domains = np.ones((12, 12), dtype=int)
    domains[:, 6:] = 2
    truth = dict(domain_labels=domains, orientation_deg=np.where(domains == 1, 0., 27.),
                 evaluation_valid=np.ones((12, 12), bool))
    left = dict(available=True, support_xyxy=[1, 1, 5, 5])
    crossing = dict(available=True, support_xyxy=[4, 1, 8, 5])
    right = dict(available=True, support_xyxy=[7, 1, 11, 5])
    assert support_domain(left, truth) == (1, 0.)
    assert support_domain(crossing, truth) == (0, None)
    result = angle_parts(np.deg2rad([89, 500, 116]), [left, crossing, right], truth, 90.)
    assert len(result["parts"]) == 2
    assert result["lattice_difference_deg"] == pytest.approx(27.)
    assert result["lattice_difference_error_deg"] == pytest.approx(0.)


def test_missing_patches_and_periodic_residuals_are_explicit():
    assert selected_indices([]).size == 0
    assert selected_indices(np.arange(100)).tolist() == np.linspace(0, 99, 16, dtype=int).tolist()
    assert selected_indices([0, 1, 2], window_ids=["z", "a", "m"]).tolist() == [1, 2, 0]
    np.testing.assert_allclose(wrap_degrees([89, -89, 180], 90), [-1, 1, 0])


def test_gallery_names_all_variants_and_has_no_transductive_option():
    html = document_template()
    for name in ("rvae_lowkl", "rvae_fourier", "rvae_fourier_lowkl"):
        assert name in html
    assert '<option value="transductive">' not in html
    assert 'eksperyment 21a' in html
