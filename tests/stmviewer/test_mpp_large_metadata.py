"""Large-movie metadata contract on narrow frames, without a multi-GB fixture."""

from dataclasses import replace
from pathlib import Path

import numpy as np

from stmviewer.frame import ImageFrame
from stmviewer.mpp_export import save_original_mpp
from stmviewer.mpp_metadata import mpp_sidecar_path
from stmviewer.series import open_frame_series


def test_thousand_frame_movie_restores_drift_borders_and_long_source_header(tmp_path):
    # One missing border per scan row: 512,000 runs, as in 1000 expanded 512px frames.
    data = np.column_stack((np.arange(512, dtype=np.float64), np.full(512, np.nan)))
    header = {
        "Frames Synchronization": {
            f"Frame {i:04d}": f"{i * 1.5} s" for i in range(1000)
        }
    }
    base = ImageFrame(
        source=Path("source.mpp"),
        data=data,
        raw_header=header,
        channel="Topo",
        signal_unit="nm",
        size_x_nm=2.0,
        size_y_nm=512.0,
        offset_x_nm=None,
        offset_y_nm=None,
        bias_v=None,
        setpoint_a=None,
        scan_angle_deg=None,
    )
    frames = tuple(
        replace(base, source_frame_index=i, measurement_time_s=i * 1.5)
        for i in range(1000)
    )
    path = save_original_mpp(
        tmp_path / "large-metadata.mpp", frames, wsxm_compatible=True
    )
    loaded = open_frame_series([path])
    assert len(loaded) == 1000
    assert mpp_sidecar_path(path).stat().st_size <= 64 * 1024 * 1024
    for i, frame in enumerate(loaded):
        assert frame.data.tobytes() == data.tobytes()
        assert frame.raw_header == header
        assert frame.measurement_time_s == i * 1.5
        assert frame.provenance.source_frame_index == i
        assert "wczytano" in frame.metadata_note
