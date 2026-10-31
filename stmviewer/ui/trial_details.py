"""Readable, complete scalar evidence from saved registration attempts."""
import json
from stmviewer.trial_document import TrialDocument


def trial_details_text(document: TrialDocument) -> str:
    p = document.payload
    outcomes = {'complete': 'zakończona', 'failed': 'przerwana błędem', 'cancelled': 'anulowana'}
    lines = [p['label'], f"Stan: {outcomes[p['outcome']]}",
             'Zakres: ' + ('cała seria' if p['kind'] == 'series' else 'para — diagnostyka'),
             f"Liczba oryginalnych klatek: {p['frame_count']}",
             f"Urządzenie: {p['device']}", f"Wersja kodu: {p.get('code_revision', 'unknown')}",
             'Kod miał zmiany robocze: ' + str(p.get('code_dirty', 'nieznane')),
             'Brak niezależnej oceny jakości (REG-06 odłożony).',
             'Odczyt próby nie zastępuje aktywnego aligned ani wyniku eksportu.']
    if p.get('error'):
        lines.append(f"Przyczyna przerwania: {p['error']}")
    lines.extend(['', 'Ustawienia:', p['settings_text'],
                  json.dumps(p['settings'], ensure_ascii=False, indent=2)])
    for record in p['records']:
        index = record['index']
        lines.extend(['', f"Klatka {index + 1} · {record['status']}",
                      f"XY pary: {record['shift_xy']}", f"XY skumulowane: {record['cumulative_xy']}",
                      'Jakość skumulowana: nieoceniona' if record['quality_score'] is None
                      else f"Wskaźnik skumulowany: {record['quality_score']} (bez niezależnej oceny)"])
        if record.get('pair_status') is not None:
            lines.append(f"Wynik samej pary: {record['pair_status']} · wskaźnik {record.get('pair_quality_score')}")
        manual = record.get('manual')
        if manual:
            lines.extend(['Pochodzenie: ręczne', f"Początkowe XY: {manual.get('start_xy')}",
                          f"Korekta XY: {manual.get('correction_xy')}",
                          f"Punkt startu: {manual.get('source_label') or 'bez przesunięcia'}"])
        if record.get('hybrid'):
            lines.append('Etapy Deep / ECC:\n' + json.dumps(record['hybrid'], ensure_ascii=False, indent=2))
        if record.get('local'):
            lines.append('Dowody lokalnego konsensusu:\n' + json.dumps(record['local'], ensure_ascii=False, indent=2))
    if p.get('manual_movie'):
        lines.append('\nZastosowane korekty filmu, baza i pochodzenie:\n'
                     + json.dumps(p['manual_movie'], ensure_ascii=False, indent=2))
    return '\n'.join(lines)
