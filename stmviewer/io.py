"""Import boundary adapting the shared STP reader to Viewer's metadata contract."""

import math
from pathlib import Path
import re

from napara.io.stp_reader import MAX_HEADER_LINES, read_stp_file

from stmviewer.frame import ImageFrame

_NUMBER_UNIT = re.compile(r"([-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][-+]?\d+)?)\s*(.*?)")
_LENGTH_NM = {"m": 1e9, "mm": 1e6, "um": 1e3, "µm": 1e3, "μm": 1e3,
              "nm": 1.0, "pm": 1e-3, "Å": 0.1, "angstrom": 0.1}
_VOLTAGE = {"V": 1.0, "mV": 1e-3, "uV": 1e-6, "µV": 1e-6, "μV": 1e-6}
_CURRENT = {"A": 1.0, "mA": 1e-3, "uA": 1e-6, "µA": 1e-6, "μA": 1e-6,
            "nA": 1e-9, "pA": 1e-12}


def _quantity(text: str) -> tuple[float, str] | None:
    match = _NUMBER_UNIT.fullmatch(text.strip())
    if match is None:
        return None
    value = float(match[1])
    return (value, match[2]) if math.isfinite(value) else None


def _scaled(text: str, factors: dict[str, float], *, positive: bool = False) -> float | None:
    quantity = _quantity(text)
    if quantity is None or quantity[1] not in factors:
        return None
    value = quantity[0] * factors[quantity[1]]
    if not math.isfinite(value) or (positive and value <= 0):
        return None
    return value


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
    amplitude = _quantity(header.get("Z Amplitude", ""))
    return ImageFrame(
        source=source,
        data=image.data,
        raw_header=header,
        channel=header.get("Acquisition channel") or header.get("Channel") or None,
        signal_unit=(amplitude[1] or None) if amplitude else None,
        size_x_nm=_scaled(header.get("X Amplitude", ""), _LENGTH_NM, positive=True),
        size_y_nm=_scaled(header.get("Y Amplitude", ""), _LENGTH_NM, positive=True),
        offset_x_nm=_scaled(header.get("X-Offset", header.get("X Offset", "")), _LENGTH_NM),
        offset_y_nm=_scaled(header.get("Y-Offset", header.get("Y Offset", "")), _LENGTH_NM),
        bias_v=_scaled(header.get("Gap Voltage", header.get("Bias", "")), _VOLTAGE),
        setpoint_a=_scaled(header.get("Setpoint", header.get("Current", "")), _CURRENT),
        scan_angle_deg=_scaled(header.get("Angle", ""), {"": 1.0, "deg": 1.0, "°": 1.0}),
    )
