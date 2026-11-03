"""Presentation of two estimates from one hybrid attempt, without ranking them."""

from dataclasses import replace

from stmviewer.deep_ecc import HybridDiagnostics
from stmviewer.pair_comparison import PairTrial


def hybrid_details_text(details: HybridDiagnostics) -> str:
    def xy(value: tuple[float, float]) -> str:
        return f'X: {value[0]:.3f} · Y: {value[1]:.3f} px'

    statuses = {'ok': 'OK backendu', 'low_confidence': 'niska pewność', 'manual_review': 'do sprawdzenia'}
    return (f'Start Deep: {xy(details.deep_shift_xy)}\n'
            f'Wynik ECC: {xy(details.final_shift_xy)}\n'
            f'Poprawka ECC − Deep: {xy(details.correction_xy)}\n'
            f'Deep: {statuses[details.deep_status]} ({details.deep_quality_score:.3f})\n'
            f'ECC: {statuses[details.ecc_status]} ({details.ecc_score:.3f})\n'
            'To miary backendów, bez niezależnej oceny. Oceń dopasowanie wizualnie.\n'
            '+X w prawo, +Y w dół; piksele oryginału.')


def deep_start_trial(trial: PairTrial) -> PairTrial:
    """Expose the exact starting estimate; no model or registration runs here."""
    details = trial.hybrid
    if details is None:
        return trial
    return replace(trial, method='deep_matcher_translation', label='Start Deep tej próby',
                   shift_xy=details.deep_shift_xy, status=details.deep_status,
                   quality_score=details.deep_quality_score, hybrid=None,
                   settings_text='Dokładny start tej samej próby, bez ponownego obliczania. '
                   + trial.settings_text)
