"""E2 readout invariants and historical-training membership boundaries."""
from copy import deepcopy

import numpy as np
import pytest

from stmdomains.experiments import e2_features as module
from stmdomains.experiments.training.partition import fit_feature_adapter, neighbor_edges


def test_geometry_is_unordered_axial_and_missing_is_not_imputed():
    basis = np.array([[[6., 0.], [0., 12.]], [[np.nan, np.nan], [0., 6.]]])
    description = dict(basis_vectors=basis, available=np.ones(2, bool),
                       valid=np.ones(2, bool), acf_score=np.array([.8, 0.]),
                       second_direction_ratio=np.array([.5, .1]))
    first = module.geometry_features(description)
    np.testing.assert_allclose(first[0], [0., 0., 1., 0., 6/48, 12/48, .8, .5], atol=1e-14)
    assert np.isnan(first[1]).all()
    description["basis_vectors"] = basis[:, ::-1] * np.array([-1., 1.])[None, :, None]
    np.testing.assert_allclose(module.geometry_features(description), first, atol=1e-14)


def test_photometry_alignment_and_anchor_preserve_constant_brightness():
    cache = dict(available_indices=np.array([2, 0]),
                 patches=np.stack([np.full((64, 64), .8), np.full((64, 64), .2)]))
    result = module.photometry_features(cache, 3)
    np.testing.assert_allclose(result[[0, 2]], [[1., .2, 0.], [1., .8, 0.]], atol=1e-14)
    assert np.isnan(result[1]).all()
    normalized = result[[0, 2]] / np.linalg.norm(result[[0, 2]], axis=1, keepdims=True)
    assert np.linalg.norm(normalized[0] - normalized[1]) > .1
    cache["available_indices"] = np.array([0, 0])
    with pytest.raises(ValueError, match="alignment"):
        module.photometry_features(cache, 3)


@pytest.fixture
def bank(monkeypatch, tmp_path):
    """Tiny reader fixture with explicit train, heldout and synthetic groups."""
    class Reader:
        def __init__(self, source, e1):
            self.source_root, self.output_root = source, e1
            self.source_hashes, self.external_hashes, self._verified_stats = {}, {}, {}
            self.freeze_hash = "frozen"
            self.groups, self.row_sets, self.arrays = {}, {}, {}
            for sample, kind, splits in [("train", "measurement", ["train"]*3 + ["test"]),
                                         ("test", "measurement", ["test"]*4),
                                         ("control", "synthetic", [None]*4)]:
                key = f"{sample}/grid/s48"
                self.groups[key] = dict(group_id=key, sampler="grid", scale_px=48,
                                        record=dict(sample_id=sample, kind=kind))
                self.row_sets[key] = [dict(window_id=f"{sample}/grid/g{i}/s48",
                                           raw_edge_xy=[16.*i, 8.], available=True,
                                           transfer_split=split) for i, split in enumerate(splits)]
                content = np.arange(4*32, dtype=np.float32).reshape(4, 32) + 1
                angle = np.array([0., np.pi/2, np.pi, 2*np.pi], dtype=np.float32)
                full = np.column_stack((content / np.linalg.norm(content, axis=1, keepdims=True),
                                        np.cos(angle), np.sin(angle))) / np.sqrt(2)
                self.arrays[key] = dict(features=full, content=content, angle_radians=angle)
            ids = [r["window_id"] for r in self.row_sets["train/grid/s48"][:3]]
            self.train_edges = neighbor_edges([[0, 8], [16, 8], [32, 8]], ids)
            self.old_adapter = fit_feature_adapter(self.arrays["train/grid/s48"]["features"][:3],
                                                   self.train_edges, ids, scope=dict(
                                                       regime="transfer", sampler="grid", scale_px=48,
                                                       feature_id="transfer/rvae/z32/seed-20261101"))
            self.old_adapter["fit_window_ids"] = ids

        def verify_provenance(self):
            return {}

        def group(self, value):
            return self.groups[value] if isinstance(value, str) else value

        def rows(self, value):
            return self.row_sets[self.group(value)["group_id"]]

        def read_json(self, relative):
            return deepcopy(self.old_adapter)

        def load_npz(self, relative):
            for key, arrays in self.arrays.items():
                if relative.endswith(key + ".npz"):
                    return arrays
            raise AssertionError(relative)

    e1 = tmp_path / "e1"
    e1.mkdir()
    (e1 / "input-audit.json").write_text("{}")
    monkeypatch.setattr(module, "Inputs", Reader)
    return module.FeatureBank(tmp_path / "source", e1)


def test_baseline_is_bit_exact_and_angle_readout_preserves_full_circle(bank):
    assert len(bank.runs) == 30
    assert len({run["run_id"] for run in bank.runs}) == 30
    full = bank.features("transfer/rvae_full/z32/seed-20261101", "train/grid/s48")
    assert full is bank.inputs.arrays["train/grid/s48"]["features"]
    assert not full.flags.writeable
    angle = bank.features("transfer/rvae_angle/z32/seed-20261101", "train/grid/s48")
    np.testing.assert_allclose(angle[0], [1., 0.], atol=1e-6)
    np.testing.assert_allclose(angle[2], [-1., 0.], atol=1e-6)
    assert not angle.flags.writeable
    assert bank.adapter("transfer/rvae_full/z32/seed-20261101", "grid") == bank.inputs.old_adapter


def test_new_adapter_keeps_exact_train_rows_and_within_frame_edges(bank):
    graph = bank.training_graph("transfer", "grid")
    assert graph["window_ids"] == tuple(f"train/grid/g{i}/s48" for i in range(3))
    np.testing.assert_array_equal(graph["edges"], [[0, 1], [1, 2]])
    assert not graph["edges"].flags.writeable
    adapter = bank.adapter("transfer/rvae_content/z32/seed-20261101", "grid")
    assert adapter["training_elements"] == 3
    assert adapter["fit_window_ids"] == list(graph["window_ids"])
    assert adapter["input_dimension"] == 32
    assert len(bank._features) == 1  # No heldout or control data entered fitting.
    before = sorted(p.relative_to(bank.inputs.output_root) for p in bank.inputs.output_root.rglob("*"))
    audit = bank.audit()
    after = sorted(p.relative_to(bank.inputs.output_root) for p in bank.inputs.output_root.rglob("*"))
    assert before == after
    assert audit["writes_source_or_e1"] is False
    assert audit["adapters"]["transfer/rvae_content/z32/seed-20261101/grid"]["reused_exact"] is False


def test_historical_membership_mismatch_is_rejected(bank):
    bank.inputs.old_adapter["fit_window_ids"] = list(reversed(bank.inputs.old_adapter["fit_window_ids"]))
    with pytest.raises(ValueError, match="historical"):
        bank.training_graph("transfer", "grid")
