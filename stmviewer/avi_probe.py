"""Disposable native codec probe: a broken encoder must not terminate the GUI."""
from pathlib import Path
import sys


def main() -> None:
    if sys.platform != 'win32':
        import resource
        resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    import cv2
    import numpy as np

    source, destination, codec, fps = sys.argv[1:]
    raster = np.load(Path(source), allow_pickle=False)
    height, width = raster.shape[:2]
    writer = cv2.VideoWriter(destination, cv2.CAP_FFMPEG,
                             int.from_bytes(codec.encode('ascii'), 'little'), int(fps), (width, height))
    try:
        if not writer.isOpened():
            raise ValueError(f'Kodek {codec} niedostępny w OpenCV/FFmpeg.')
        writer.write(raster)
    finally:
        writer.release()


if __name__ == '__main__':
    main()
