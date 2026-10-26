"""AVI inputs from a complete aligned result, retaining per-frame calibration."""
from dataclasses import replace

from stmviewer.frame import ImageFrame
from stmviewer.registration import RegistrationResult


def aligned_movie_frames(originals: tuple[ImageFrame, ...],
                         result: RegistrationResult | None) -> tuple[ImageFrame, ...] | None:
    """Keep the full canvas and sample arrays; scale selection belongs to AVI planning.

    A mixed registration has no common preview scale. Individual originals can
    still calibrate a homogeneous export range, without changing that preview.
    """
    if (result is None or len(result.frames) != len(originals)
            or any(aligned.original is not original
                   or aligned.image.data.shape != result.canvas_shape
                   for original, aligned in zip(originals, result.frames))):
        return None
    height, width = result.canvas_shape
    return tuple(replace(
        aligned.image,
        size_x_nm=(original.size_x_nm / original.data.shape[1] * width
                   if original.size_x_nm is not None else None),
        size_y_nm=(original.size_y_nm / original.data.shape[0] * height
                   if original.size_y_nm is not None else None),
    ) for original, aligned in zip(originals, result.frames))
