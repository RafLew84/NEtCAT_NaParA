"""Viewer graph adapter: keep Tile+RANSAC numerics, propagate native failures."""

import numpy as np
from numpy.typing import NDArray
from nanotrack.registration.tile_correlation import TileCorrelationRansacBackend


# The shared backend is outside the Viewer typing boundary.
class GraphTileBackend(TileCorrelationRansacBackend):  # type: ignore[misc]
    """Only the shared tile loop's broad exception swallowing is replaced.

    Texture/mask filtering, tile positions, phase settings and the inherited
    consensus stay identical. A library fault or malformed vector is not evidence
    that the sample lacks matching features.
    """

    def _estimate_local_shifts(self, reference: NDArray[np.float64], moving: NDArray[np.float64],
                               reference_mask: NDArray[np.bool_], moving_mask: NDArray[np.bool_],
                               ) -> NDArray[np.float64]:
        from skimage.registration import phase_cross_correlation

        shifts: list[tuple[float, float]] = []
        size = self.config.tile_size
        for y0 in self._tile_positions(reference.shape[0]):
            for x0 in self._tile_positions(reference.shape[1]):
                tile = np.s_[y0:y0 + size, x0:x0 + size]
                ref_mask, mov_mask = reference_mask[tile], moving_mask[tile]
                if (self._valid_fraction(ref_mask) < self.config.min_tile_valid_fraction
                        or self._valid_fraction(mov_mask) < self.config.min_tile_valid_fraction):
                    continue
                ref = self._fill_invalid_with_tile_median(reference[tile], ref_mask)
                mov = self._fill_invalid_with_tile_median(moving[tile], mov_mask)
                if (float(np.std(ref)) <= self.config.min_texture_std
                        or float(np.std(mov)) <= self.config.min_texture_std):
                    continue
                shift_yx, _, _ = phase_cross_correlation(  # type: ignore[no-untyped-call]
                    ref - float(np.mean(ref)), mov - float(np.mean(mov)),
                    upsample_factor=self.config.upsample_factor,
                    normalization=self.config.normalization,
                )
                shift = np.asarray(shift_yx, dtype=np.float64)
                if shift.shape != (2,) or not np.isfinite(shift).all():
                    raise ValueError('Tile+RANSAC: skimage zwrócił nieprawidłowy wektor XY fragmentu.')
                shifts.append((float(shift[1]), float(shift[0])))
        return np.asarray(shifts, dtype=np.float64).reshape((-1, 2))
