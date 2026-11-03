"""Publish a new export directory only after every selected frame has been written."""

from collections.abc import Callable
from contextlib import ExitStack
from dataclasses import asdict
from datetime import datetime, timezone
import csv
import os
from pathlib import Path
from tempfile import TemporaryDirectory

from stmdomains.core.export import ExportOptions
from stmdomains.core.frame_presentation import FramePresenter, PresentedFrame
from stmdomains.core.immutable import plain_metadata
from stmdomains.core.project import ProjectSnapshot
from stmdomains.io.export_tables import TABLE_FIELDS, identity, table_rows
from stmdomains.io.project_results import catalogue_record, validate_frame
from stmdomains.io.project_archive import checkpoint, json_bytes
from stmdomains.io.source_identity import source_digest


EXPORT_README = '''# Eksport STM Domains — wersja 1

CSV: UTF-8, przecinek, kropka dziesiętna, standardowe cytowanie tekstu.
Brak wartości liczbowej to puste pole; 0 jest rzeczywiście dostępnym zerem.
frames.csv: każda wybrana klatka, także bez analizy.
molecules.csv: dostępne oznaczenia i przypisania; domena 0 = nieprzypisana.
domains.csv: domeny lokalne dla klatki. classes.csv: klasy danego katalogu.
Nie sumujemy klatek i nie deklarujemy śledzenia molekuł ani domen.

working_index/source_index: od 0; working_number/source_number: od 1.
time_s: czas pomiaru, jeśli dostępny; time_status wyjaśnia brak. Nie używamy
tempa odtwarzania do obliczania czasu. input_count: liczba dostępnych oznaczeń;
pole puste przy niedostępnej/uszkodzonej sekcji.
frame_key: SHA-256 MPP i indeks źródłowy; analysis_id: wybrany przebieg;
catalogue_id: tożsamość katalogu, nie numer/kolor klasy.
center_*_raw_px: współrzędne środka bboxa w oryginalnym polu klatki.
included_in_analysis_denominator: 1/0 lub brak; active_count/active_denominator
wyklucza duplikaty i oznaczenia poza polem zgodnie z zapisanym wynikiem.
assigned_percent: 100 * assigned_count / active_count; nie procent wykrywalności.
counts_status/percentage_status: complete, partial, unavailable lub undefined
(mianownik 0). annotation_status opisuje dostępność oznaczeń niezależnie.
analysis_status zachowuje odmowę, not_run, error, unavailable; not_in_analysis
= klatka poza wybranym przebiegiem; unanalysed = eksport bez analizy.

field_area_px2: prostokąt oryginalnej klatki, bez paddingu wyrównania.
approx_area_px2: liczba pikseli przybliżonej maski domen, nie zwalidowana
powierzchnia fizyczna. approx_area_status: approximate lub unavailable.
approx_area_percent_field używa pełnego pola, także przy eksporcie wycinka.
touches_field_edge: maska dochodzi do brzegu; zasięg poza polem jest nieznany.
physical_area_nm2 i coverage_area_px2 pozostają niedostępne: obecna metoda
nie dostarcza zwalidowanej kalibracji fizycznej ani pokrycia/wysp materiału.
Nie ma tabeli wysp, ponieważ metoda ich nie wyznacza.

frame-*.json: rzeczywiste parametry/metadane wykonania, diagnostyka wejścia,
ustawienia PNG i zakres obrazu. Szkic następnej analizy nie zastępuje parametrów.
PNG: bieżący tryb, gamma i warstwy; legenda/liczniki dotyczą całej klatki.
Wyrównane płótno poza obramowaniem pola jest paddingiem, nie pomiarem.
Eksport nie wykonuje analizy i nie zastępuje projektu .stmdomains.
'''


def export_results(target: Path, snapshot: ProjectSnapshot, indices: tuple[int, ...], options: ExportOptions,
                   *, render_png: Callable[[PresentedFrame], bytes] | None = None,
                   cancelled: Callable[[], bool] = lambda: False,
                   progress: Callable[[str], None] = lambda text: None) -> Path:
    target = Path(target).absolute()
    if target.exists() or target.is_symlink():
        raise ValueError('Katalog eksportu już istnieje. Wybierz nową nazwę, aby zachować poprzedni eksport.')
    if (not indices or len(set(indices)) != len(indices) or
            any(type(i) is not int or not 0 <= i < snapshot.series.frame_count for i in indices)):
        raise ValueError('Niepoprawny zakres eksportu.')
    if options.png and render_png is None:
        raise ValueError('Brak renderera PNG.')
    def check():
        checkpoint(cancelled)
    check()
    presenter = FramePresenter(snapshot.series)
    analysis = snapshot.analysis
    with TemporaryDirectory(prefix='.stmdomains-export-', dir=target.parent) as temporary:
        root = Path(temporary)
        with ExitStack() as files:
            writers = {}
            if options.csv:
                for name, fields in TABLE_FIELDS.items():
                    stream = files.enter_context((root / f'{name}.csv').open('w', encoding='utf-8', newline=''))
                    writers[name] = csv.DictWriter(stream, fields)
                    writers[name].writeheader()
            for number, index in enumerate(indices, 1):
                check()
                progress(f'Eksport klatki {index + 1} · {number}/{len(indices)}…')
                result = analysis.frames.get(index) if analysis else None
                if result is not None:
                    if result.working_index != index:
                        raise ValueError("Wynik nie odpowiada eksportowanej klatce.")
                    validate_frame(result, snapshot.series, presenter)
                raw = presenter.analysis_input(index)
                if options.csv:
                    for name, rows in table_rows(snapshot, index, result, raw.annotations).items():
                        writers[name].writerows(rows)
                metadata = {**identity(snapshot, index, result), 'parameters': plain_metadata(result.parameters) if result else None,
                            'execution_metadata': plain_metadata(result.metadata) if result else None,
                            'classes': [asdict(item) for item in result.classes] if result else [],
                            'catalogue': catalogue_record(result.catalogue) if result and result.catalogue else None,
                            'view': plain_metadata(snapshot.view), 'export_options': asdict(options),
                            'annotation_diagnostics': raw.annotations.diagnostics,
                            'registration': presenter.registration.describe(index),
                            'field_rect_view_px': presenter.registration.field_rect(index, snapshot.view.get('mode', 'raw'))}
                (root / f'frame-{index+1:06d}.json').write_bytes(json_bytes(metadata))
                if options.png and render_png is not None:
                    view = presenter.present(index, snapshot.view.get('mode', 'raw'), snapshot.view.get('gamma', 1.), result=result)
                    (root / f'frame-{index+1:06d}.png').write_bytes(render_png(view))
                check()
        (root / 'README.md').write_text(EXPORT_README, encoding='utf-8')
        entries = {p.name: {'size': p.stat().st_size, 'sha256': source_digest(p, check)} for p in sorted(root.iterdir())}
        (root / 'manifest.json').write_bytes(json_bytes({'format': 'stmdomains-export', 'version': 1,
            'created_at': datetime.now(timezone.utc).isoformat(), 'analysis_id': analysis.identifier if analysis else None,
            'working_indices': indices, 'source_sha256': snapshot.series.source_sha256,
            'analysis_execution': plain_metadata(analysis.execution) if analysis else None,
            'catalogues': [catalogue_record(catalogue) for catalogue in analysis.catalogues] if analysis else [],
            'provenance': snapshot.series.provenance, 'view': plain_metadata(snapshot.view),
            'options': asdict(options), 'entries': entries}))
        check()
        # Reserve the final name exclusively; never replace someone else's directory.
        target.mkdir()
        try:
            os.replace(root, target)
        except OSError:
            try:
                target.rmdir()
            except OSError:
                pass
            raise
    return target
