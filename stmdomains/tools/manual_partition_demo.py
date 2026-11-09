"""Synthetic source domains for exercising split/merge UI, not detector results."""

import argparse
from pathlib import Path

import numpy as np

from stmdomains.analysis.manual_regions import manual_regions
from stmdomains.analysis.provenance import input_fingerprint
from stmdomains.core.analysis_result import FrameAnalysis, MoleculeAssignment, ResultClass
from stmdomains.core.frame_presentation import FramePresenter
from stmdomains.core.project import ProjectAnalysis, ProjectSnapshot
from stmdomains.io.moltrack_import import ImportCandidate, prepare_import
from stmdomains.io.project import save_project
from stmdomains.tools.analysis_demo import molecule_image, write_analysis_annotations
from stmdomains.tools.demo_inputs import write_mpp, write_session


def create_partition_demo(directory: Path) -> Path:
    """Three literal controls: one parent, adjacent classes, a physical gap."""
    directory.mkdir(parents=True, exist_ok=True)
    grid = np.array([(128 + 12*x, 176 + 12*y) for y in range(6) for x in range(8)], dtype=float)
    far = np.array([(360 + 12*x, 320 + 12*y) for y in range(3) for x in range(3)], dtype=float)
    gap = grid.copy()
    gap[np.arange(len(grid)) % 8 >= 4, 0] += 48
    points = [np.vstack((grid, far)), np.vstack((grid, far)), np.vstack((gap, far))]
    images = np.stack([molecule_image(frame) for frame in points])
    source = write_mpp(directory / 'partition-controls.mpp', images[:, ::-1, ::-1])
    session = write_session(directory / 'partition-controls.moltrack.json', source, [0, 1, 2])
    write_analysis_annotations(session, points, duplicate=False)
    candidate = prepare_import(session)
    if not isinstance(candidate, ImportCandidate):
        raise ValueError('Nie udało się odczytać wygenerowanego przykładu.')
    presenter = FramePresenter(candidate.series)
    results = {}
    for index in range(3):
        data = presenter.analysis_input(index)
        assignments = {}
        for i, detection in enumerate(data.annotations.detections):
            domain = 11 if i >= 48 else 9 if index > 0 and i % 8 >= 4 else 7
            assignments[detection.detection_id] = MoleculeAssignment(detection.detection_id,
                domain_local_id=domain, class_id='A' if domain == 7 else 'B', status='domain')
        labels, _ = manual_regions(data.annotations.detections, assignments, (512, 512))
        results[index] = FrameAnalysis(candidate.series.identity, index, index, 'complete',
            'Kontrola syntetyczna: zadane domeny i klasy, nie wynik detektora.', assignments,
            (ResultClass('A', '#5cb8ff'), ResultClass('B', '#ff9a53')),
            metadata={'analysis_id': 'synthetic-partition-controls', 'synthetic_control': True,
                      'input_sha256': input_fingerprint(data)}, domain_labels=labels)
    analysis = ProjectAnalysis('synthetic-partition-controls', (0, 1, 2), results,
                               {i: {'status': 'complete'} for i in results})
    path = directory / 'partition-controls.stmdomains'
    save_project(path, ProjectSnapshot(candidate.series, {'current_index': 0, 'mode': 'raw', 'gamma': 1.},
                                       analysis=analysis))
    (directory / 'README.txt').write_text(
        'SD-V4-22 — kontrola edycji ręcznej, nie wynik detektora.\n'
        'W netcat uruchom python -m stmdomains.main i otwórz partition-controls.stmdomains.\n'
        'Klatka 1: D7 ma 48 molekuł klasy A; D11 to osobny obszar 9 molekuł klasy B.\n'
        'Podziel D7 lassem, zatwierdź, wskaż po jednym członku obu części i Połącz do D7.\n'
        'Powraca dokładnie początkowy obszar. D11 pozostaje niezmieniona.\n'
        'Klatka 2: sąsiadujące D7 (24, A), D9 (24, B). Połącz daje 48 członków, klasę nieustaloną.\n'
        'Klatka 3: D7 i D9 dzieli przerwa. Połącz odmawia, nie dorysowując mostu.\n'
        'W każdej klatce 57 przypisań. Cofnij/Ponów przywraca całą operację.\n'
        'Korekty pozostają tylko w sesji. Oryginał kontrolny służy wyłącznie testom UI.\n',
        encoding='utf-8')
    return path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('directory', type=Path, nargs='?', default=Path('.scratch/stmdomains-ui-22/demo'))
    print(create_partition_demo(parser.parse_args().directory))


if __name__ == '__main__':
    main()
