"""Launch real GUI with an opt-in delay or one allocation failure during correction.

Run from repo root with PYTHONPATH=. This diagnostic changes only the external
interpolator in this process; ordinary application launches and sources are intact.
"""

import argparse
import sys
import time

from PyQt6.QtCore import QThread
from scipy import ndimage

from stmviewer.app import main
from stmviewer.ui.manual_movie_job import ManualMovieJob


def run():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--delay', type=float, default=0, help='Seconds per corrected frame (0–2)')
    parser.add_argument('--fail-at', type=int, default=0, help='Fail once on this corrected frame, 0 disables')
    args = parser.parse_args()
    if not 0 <= args.delay <= 2 or args.fail_at < 0:
        parser.error('Use delay 0–2 seconds and nonnegative fail-at.')
    original = ndimage.affine_transform
    count = 0

    def controlled_transform(*values, **options):
        nonlocal count
        if isinstance(QThread.currentThread(), ManualMovieJob):
            count += 1
            time.sleep(args.delay)
            if count == args.fail_at:
                raise MemoryError('Kontrolowany błąd alokacji podczas ręcznej korekty filmu')
        return original(*values, **options)

    ndimage.affine_transform = controlled_transform
    sys.argv = [sys.argv[0]]  # Qt need not interpret diagnostic flags.
    try:
        return main()
    finally:
        ndimage.affine_transform = original


if __name__ == '__main__':
    raise SystemExit(run())
