"""A large, deterministic pair for manually cancelling real Optical Flow.

Run from the repository root. Existing destinations are never overwritten.
The shift to apply to the second image is (+7, -5) pixels.
"""

import argparse
from pathlib import Path
import shutil
from tempfile import TemporaryDirectory

import numpy as np
from numpy.typing import NDArray
from scipy.ndimage import shift

from make_registration_fixtures import write_movie


def pair_frames(size: int) -> tuple[NDArray[np.float64], NDArray[np.float64]]:
    if not 128 <= size <= 4096:
        raise ValueError("Rozmiar wzorca musi mieścić się w zakresie 128–4096 px.")
    y, x = np.indices((size, size), dtype=np.float64)
    reference = (0.3 * np.sin(x / 7) + 0.2 * np.cos(y / 11)
                 + 0.15 * np.sin((x + 2 * y) / 17))
    reference += np.random.default_rng(20261028).normal(0, 0.025, reference.shape)
    reference[size // 8:size // 3, size // 7:size // 4] += 2.0
    reference[size // 2:3 * size // 4, 5 * size // 8:7 * size // 8] -= 1.5
    reference[3 * size // 4:7 * size // 8, size // 5:2 * size // 5] += 1.0
    moving = np.asarray(shift(reference, (5, -7), order=0, mode="nearest"), dtype=np.float64)
    return reference, moving


def generate(destination: Path, size: int = 1536) -> None:
    if destination.exists() or destination.is_symlink():
        raise FileExistsError(f"Wzorzec już istnieje; wybierz nową ścieżkę: {destination}")
    frames = pair_frames(size)
    destination.parent.mkdir(parents=True, exist_ok=True)
    # The existing fixture writer preserves the reader's source orientation.
    # Publish with exclusive creation, including when another process wins a race.
    with TemporaryDirectory(prefix="stmviewer-pair-fixture-") as temporary:
        staged = Path(temporary) / "pair.mpp"
        write_movie(staged, frames)
        with staged.open("rb") as source, destination.open("xb") as target:
            shutil.copyfileobj(source, target)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", nargs="?", type=Path,
                        default=Path("data/registration-pair-cancel.mpp"))
    parser.add_argument("--size", type=int, default=1536,
                        help="Długość boku w pikselach (128–4096); domyślnie 1536")
    args = parser.parse_args()
    generate(args.output, args.size)
    print(f"Zapisano {args.output}: 2 × {args.size} × {args.size}; XY do nałożenia: (+7, -5) px.")


if __name__ == "__main__":
    main()
