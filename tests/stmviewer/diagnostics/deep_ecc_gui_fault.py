"""Launch the real GUI with a delayed or failing external ECC call.

Only this diagnostic process is affected. Open a series, first register with
Deep Matcher, then choose Deep Matcher + ECC (v1) to inspect cancellation or
retention of the previous aligned result after the controlled ECC error.
"""

import argparse
import sys
import time

import cv2

from stmviewer.app import main


def run():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--delay', type=float, default=0, help='Seconds before each ECC call (0–10)')
    parser.add_argument('--fail-at', type=int, default=0, help='Fail once on this ECC call, 0 disables')
    args = parser.parse_args()
    if not 0 <= args.delay <= 10 or args.fail_at < 0:
        parser.error('Use delay 0–10 seconds and nonnegative fail-at.')
    original = cv2.findTransformECC
    count = 0

    def controlled_ecc(*values, **options):
        nonlocal count
        count += 1
        time.sleep(args.delay)
        if count == args.fail_at:
            raise cv2.error('REG-04: kontrolowana odmowa ECC w narzędziu diagnostycznym')
        return original(*values, **options)

    cv2.findTransformECC = controlled_ecc
    sys.argv = [sys.argv[0]]
    try:
        return main()
    finally:
        cv2.findTransformECC = original


if __name__ == '__main__':
    raise SystemExit(run())
