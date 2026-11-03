"""Import boundary adapting the shared STP reader to Viewer's metadata contract."""

from pathlib import Path

from napara.io.stp_reader import MAX_HEADER_LINES, read_stp_file

from stmviewer.frame import ImageFrame
from stmviewer.s94 import open_s94
from stmviewer.quantities import CURRENT_A, LENGTH_NM, VOLTAGE_V, parse_quantity, scaled_quantity


def _header(source: Path) -> dict[str, str]:
    # The shared reader ignores invalid UTF-8 bytes, turning Latin-1 µm into m.
    # Preserve those units here; the shared reader still owns binary decoding.
    header: dict[str, str] = {}
    consumed = 0
    with source.open("rb") as stream:
        for _ in range(MAX_HEADER_LINES):
            raw = stream.readline(65537)
            consumed += len(raw)
            if len(raw) > 65536 or consumed > 1048576:
                raise ValueError("Nagłówek STP jest zbyt długi.")
            if not raw:
                break
            try:
                line = raw.decode("utf-8").strip()
            except UnicodeDecodeError:
                line = raw.decode("latin1").strip()
            if line == "[Header end]":
                return header
            if ":" in line:
                key, value = line.split(":", 1)
                header[key.strip()] = value.strip()
    raise ValueError("Brak [Header end] w nagłówku STP.")


def open_stp(path: str | Path) -> ImageFrame:
    """Read one STP. Data are already calibrated doubles, rotated by the reader.

    Use the raw header instead of STMImage's metadata defaults: zero and an
    inferred channel cannot express missing calibration or preserve source names.
    Z Amplitude supplies the signal unit only, never an extra gain.
    """
    source = Path(path).resolve()
    try:
        header = _header(source)
        data_type = header.get("Image Data Type", "double")
        if data_type.lower() != "double":
            raise ValueError(f"Nieobsługiwany typ danych STP: {data_type} (wymagany double).")
        images = read_stp_file(str(source))
    except (OSError, ValueError, OverflowError) as error:
        raise ValueError(f"{source}: {error}") from error
    if not images:
        raise ValueError(f"Brak obrazu w pliku {source}")
    image = images[0]
    amplitude = parse_quantity(header.get("Z Amplitude", ""))
    return ImageFrame(
        source=source,
        data=image.data,
        raw_header=header,
        channel=header.get("Acquisition channel") or header.get("Channel") or None,
        signal_unit=(amplitude[1] or None) if amplitude else None,
        size_x_nm=scaled_quantity(header.get("X Amplitude", ""), LENGTH_NM, positive=True),
        size_y_nm=scaled_quantity(header.get("Y Amplitude", ""), LENGTH_NM, positive=True),
        offset_x_nm=scaled_quantity(header.get("X-Offset", header.get("X Offset", "")), LENGTH_NM),
        offset_y_nm=scaled_quantity(header.get("Y-Offset", header.get("Y Offset", "")), LENGTH_NM),
        bias_v=scaled_quantity(header.get("Gap Voltage", header.get("Bias", "")), VOLTAGE_V),
        setpoint_a=scaled_quantity(header.get("Setpoint", header.get("Current", "")), CURRENT_A),
        scan_angle_deg=scaled_quantity(header.get("Angle", ""), {"": 1.0, "deg": 1.0, "°": 1.0}),
    )


def open_frame(path: str | Path) -> ImageFrame:
    """Read one supported image while retaining format-specific calibration."""
    source = Path(path)
    extension = source.suffix.lower()
    if extension == ".stp":
        return open_stp(source)
    if extension == ".s94":
        return open_s94(source)
    raise ValueError(f"{source}: nieobsługiwany format (wymagany STP lub S94).")
