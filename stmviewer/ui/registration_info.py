"""Descriptions and warnings for the active registration, without window state."""
from stmviewer.registration import RegistrationResult
from stmviewer.ui.hybrid_details import hybrid_details_text
from stmviewer.ui.local_details import local_details_text


def registration_warnings(result: RegistrationResult) -> tuple[str, ...]:
    return tuple(
        (("Do sprawdzenia: pewność niezweryfikowana"
          + (" (niepewność odziedziczona)" if frame.inherited_uncertainty else ""))
         if frame.quality_score is None
         else "Do sprawdzenia: niepewność odziedziczona" if frame.inherited_uncertainty
         else "Do sprawdzenia: niska pewność") if frame.status != "ok" else ""
        for frame in result.frames
    )


def registration_info(result: RegistrationResult, index: int, pixel_proportions: bool) -> str:
    current = result.frames[index]
    origin = result.reference.source.name
    if result.reference.source_frame_index is not None:
        origin += f" · MPP {result.reference.source_frame_index + 1}"
    height, width = result.canvas_shape
    quality = ("⚠ Do sprawdzenia — pewność niezweryfikowana" if current.quality_score is None
               else "OK" if current.status == "ok" else "⚠ Do sprawdzenia")
    inherited = " (niepewność odziedziczona)" if current.inherited_uncertainty else ""
    scale = "piksele — brak wspólnej skali" if result.pixel_size_nm is None else "wspólna skala źródłowa"
    if pixel_proportions:
        scale = "piksele — opcja Proporcje pikselowe"
    return (
        f"{result.method} · {quality}{inherited}\nUrządzenie: {result.device}\n"
        + (f"Ręczne korekty filmu: {len(result.corrections)} · jakość nieoceniona\n"
           if result.corrections else "")
        + f"ΔX: {current.shift_xy[0]:g} px · ΔY: {current.shift_xy[1]:g} px\n"
        f"Aligned: {width} × {height} px\nSkala aligned: {scale}\nOdniesienie: {origin}"
        + _pair_frame_info(result, index)
    )


def _pair_frame_info(result: RegistrationResult, index: int) -> str:
    if result.local_diagnostics:
        local = result.local_diagnostics[index]
        if local is None:
            return '\nPierwsza klatka jest odniesieniem; nie wymaga estymacji fragmentów.'
        return ('\nAutomatyczna estymata pary (przed ręcznymi korektami i usuwaniem):\n'
                + local_details_text(local) + '\n' + local.settings_text)
    if not result.pair_diagnostics:
        return ''
    details = result.pair_diagnostics[index]
    if details is None:
        return '\nHybryda: pierwsza klatka jest odniesieniem; nie wymaga estymacji pary.'
    return ('\nAutomatyczna estymata pary (przed ręcznymi korektami i usuwaniem):\n'
            + hybrid_details_text(details) + '\n' + details.settings_text)
