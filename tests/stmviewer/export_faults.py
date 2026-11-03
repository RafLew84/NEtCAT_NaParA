"""Controlled failures at filesystem/codec boundaries of the opt-in GUI measurement."""

from contextlib import contextmanager
import os
from pathlib import Path
from unittest.mock import patch


@contextmanager
def export_failure(kind, target, frame_count):
    if kind == "mpp":
        replace = os.replace
        sidecar = target.with_name(target.name + ".stmviewer.json")

        def fail_second_publication(source, destination):
            if Path(destination) == sidecar and Path(source).name == "metadata.part":
                raise OSError("ticket19 controlled write failure")
            return replace(source, destination)

        with patch.object(os, "replace", fail_second_publication):
            yield "ticket19 controlled write failure"
    else:
        import cv2

        writer = cv2.VideoWriter

        class LimitedWriter:
            def __init__(self, *args, **kwargs):
                self.stream = writer(*args, **kwargs)
                self.count = 0

            def __getattr__(self, key):
                return getattr(self.stream, key)

            def write(self, raster):
                self.count += 1
                if self.count > max(1, frame_count // 4):
                    raise MemoryError("ticket19 controlled allocation failure")
                return self.stream.write(raster)

        with patch.object(cv2, "VideoWriter", LimitedWriter):
            yield "ticket19 controlled allocation failure"
