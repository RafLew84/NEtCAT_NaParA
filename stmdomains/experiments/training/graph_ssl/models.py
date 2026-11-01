"""Small GraphMAE-inspired geometry experiment; not an STM detector.

All geometry is prepared inside each bounded ego window. The network receives
only node descriptors, binary adjacency and availability, never XY coordinates,
edge distances, domain labels or an unmasked copy of the reconstruction target.
"""
from __future__ import annotations

import numpy as np
import torch
from torch import nn
from torch.nn import functional as F


ARCHITECTURE = {
    "name": "graphmae_inspired_mean_geometry_v1",
    "input_dimension": 57,
    "input": "48 soft polar channels; 4 nearest distances /24; count /10; 4 presence flags",
    "hidden": 64,
    "encoder_layers": 2,
    "latent_dimension": 32,
    "decoder_layers": 1,
    "aggregation": "Separate self transform plus row-normalized binary adjacency mean; supplied adjacency includes self",
    "activation": "GELU after each hidden encoder block",
    "normalization": "No feature-wise, graph-wise or Layer/Batch normalization; fixed physical input units",
    "mask_fraction": .5,
    "masking": "Whole node descriptor to learned token; floor(N/2), bounded to [1,N-1]; decoder latent remasking",
    "losses": {
        "sce": "mean((1-cos(reconstruction,target))**2) on masked valid nodes with nonzero target; zero targets counted separately",
        "sce_scale": "SCE plus weight1 MSE on observed distance channels48:52, presence flags53:57",
    },
    "inference": "Unmasked encoder, central node index0; no decoder use",
    "absolute_xy_input": False,
    "edge_geometry_input": False,
    "rotation_or_scale_augmentation": False,
    "source": "https://github.com/THUDM/GraphMAE; custom mean-GNN/geometry adaptation, not paper reproduction",
}


class MeanBlock(nn.Module):
    def __init__(self, input_dim: int, output_dim: int):
        super().__init__()
        self.self_linear = nn.Linear(input_dim, output_dim)
        self.neighbor_linear = nn.Linear(input_dim, output_dim, bias=False)

    def forward(self, x, adjacency, valid):
        mean = torch.bmm(adjacency, x)
        result = self.self_linear(x) + self.neighbor_linear(mean)
        return result * valid.unsqueeze(-1)


class GraphSSL(nn.Module):
    def __init__(self, input_dim=57, hidden=64, latent_dim=32):
        super().__init__()
        self.input_dim, self.hidden, self.latent_dim = input_dim, hidden, latent_dim
        self.encoder1 = MeanBlock(input_dim, hidden)
        self.encoder2 = MeanBlock(hidden, hidden)
        self.latent = nn.Linear(hidden, latent_dim)
        self.encoder_to_decoder = nn.Linear(latent_dim, hidden, bias=False)
        self.decoder = MeanBlock(hidden, input_dim)
        self.mask_token = nn.Parameter(torch.zeros(input_dim))

    @staticmethod
    def normalized_adjacency(adj, valid, dtype):
        adjacency = adj.to(dtype) * valid.unsqueeze(1) * valid.unsqueeze(2)
        return adjacency / adjacency.sum(-1, keepdim=True).clamp_min(1.)

    def _encode(self, x, adjacency, valid):
        value = F.gelu(self.encoder1(x * valid.unsqueeze(-1), adjacency, valid))
        value = F.gelu(self.encoder2(value, adjacency, valid))
        return self.latent(value) * valid.unsqueeze(-1)

    def encode(self, x, adj, valid):
        adjacency = self.normalized_adjacency(adj, valid, x.dtype)
        return self._encode(x, adjacency, valid)

    def forward(self, x, adj, valid, masked):
        masked = masked & valid
        adjacency = self.normalized_adjacency(adj, valid, x.dtype)
        corrupted = torch.where(masked.unsqueeze(-1), self.mask_token, x)
        embedding = self._encode(corrupted, adjacency, valid)
        decoder_input = self.encoder_to_decoder(embedding)
        decoder_input = decoder_input.masked_fill(masked.unsqueeze(-1), 0.)
        reconstruction = self.decoder(decoder_input, adjacency, valid)
        return {"reconstruction": reconstruction, "embedding": embedding}


def sample_mask(valid, rng: np.random.Generator):
    """CPU mask RNG is checkpointed separately from the sample-order RNG."""
    array = valid.detach().cpu().numpy() if isinstance(valid, torch.Tensor) else np.asarray(valid)
    result = np.zeros(array.shape, dtype=bool)
    for row, flags in enumerate(array):
        available = np.flatnonzero(flags)
        if len(available) < 2:
            continue
        count = min(len(available) - 1, max(1, len(available) // 2))
        result[row, rng.permutation(available)[:count]] = True
    return torch.from_numpy(result)


def reconstruction_loss(prediction, target, masked, valid, loss_name="sce_scale"):
    if loss_name not in ("sce", "sce_scale"):
        raise ValueError("Unknown frozen graph loss")
    selected = masked & valid
    predicted, expected = prediction[selected], target[selected]
    if not len(expected):
        raise ValueError("No masked valid nodes for graph reconstruction")
    informative = expected.norm(dim=-1) > 1e-10
    cosine = (F.normalize(predicted[informative], dim=-1, eps=1e-8) *
              F.normalize(expected[informative], dim=-1, eps=1e-8)).sum(-1).clamp(-1., 1.)
    sce = (1. - cosine).square().mean() if bool(informative.any()) else prediction.sum() * 0.
    observed = expected[:, 53:57] > .5
    observed_count = observed.sum()
    squared = (predicted[:, 48:52] - expected[:, 48:52]).square()
    scale_mse = (squared * observed).sum() / observed_count.clamp_min(1)
    return {"loss": sce + scale_mse if loss_name == "sce_scale" else sce,
            "sce": sce, "scale_mse": scale_mse,
            "masked_nodes": selected.sum(), "masked_informative_nodes": informative.sum(),
            "masked_zero_target_nodes": (~informative).sum(),
            "observed_distance_slots": observed_count}


@torch.inference_mode()
def predict_features(model, graphs, *, batch_size=64, device="cpu"):
    """Encode every supplied graph; availability selection belongs to caller."""
    output = []
    was_training = model.training
    model.eval()
    try:
        for start in range(0, len(graphs), batch_size):
            batch = graphs[start:start + batch_size]
            arrays = {key: torch.as_tensor(np.stack([g[key] for g in batch]), device=device)
                      for key in ("x", "adj", "valid")}
            value = model.encode(arrays["x"].float(), arrays["adj"], arrays["valid"].bool())
            roots = torch.tensor([g.get("root_index", 0) for g in batch], device=device)
            output.append(value[torch.arange(len(batch), device=device), roots].cpu().numpy())
    finally:
        model.train(was_training)
    return np.concatenate(output) if output else np.empty((0, model.latent_dim), dtype=np.float32)
