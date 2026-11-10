"""Literal 9/7-member controls for class editing; no detector-quality claims."""

import argparse
from pathlib import Path

import numpy as np

from stmdomains.analysis.descriptor_settings import DescriptorSettings
from stmdomains.analysis.manual_regions import manual_regions
from stmdomains.analysis.provenance import input_fingerprint
from stmdomains.core.analysis_result import FrameAnalysis, MoleculeAssignment, ResultClass
from stmdomains.core.class_catalogue import ClassCatalogue
from stmdomains.core.frame_presentation import FramePresenter
from stmdomains.core.project import ProjectAnalysis, ProjectSnapshot
from stmdomains.io.moltrack_import import ImportCandidate, prepare_import
from stmdomains.io.project import save_project
from stmdomains.tools.analysis_demo import molecule_image, write_analysis_annotations
from stmdomains.tools.demo_inputs import write_mpp, write_session


def create_class_operations_demo(directory: Path) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    a = [(150, 180), (174, 180), (150, 204), (174, 204)]
    b = [(300, 180), (324, 180), (312, 204)]
    points = [np.array(a + b + [(150, 228), (174, 228)], dtype=float),
              np.array(a + b, dtype=float), np.array(a + b, dtype=float)]
    images = np.stack([molecule_image(p) for p in points])
    source = write_mpp(directory / 'class-controls.mpp', images[:, ::-1, ::-1])
    session = write_session(directory / 'class-controls.moltrack.json', source, [0, 1, 2])
    write_analysis_annotations(session, points, duplicate=False)
    imported = prepare_import(session)
    if not isinstance(imported, ImportCandidate):
        raise ValueError('Nie udało się otworzyć kontroli klas.')
    series = imported.series
    presenter = FramePresenter(series)
    # A literal valid catalogue for storage/identity checks, not a fitted detector.
    width = DescriptorSettings().dimension
    state = {'k': 2, 'projection': 'identity', 'pca_mean': [], 'pca_components': [],
             'pca_components_count': 0, 'centers': [np.zeros(width).tolist(), np.ones(width).tolist()],
             'class_radius95': [1., 1.], 'synthetic_control': True}
    shared = ClassCatalogue(series.identity, 'selected_range', (0, 1), state, {'synthetic_control': True}, {})
    foreign = ClassCatalogue(series.identity, 'current_frame', (2,), state, {'synthetic_control': True}, {})
    results = {}
    for index in range(3):
        data = presenter.analysis_input(index)
        catalogue = shared if index < 2 else foreign
        assignments = {}
        for i, d in enumerate(data.annotations.detections):
            domain = 1 if i < 4 else 2 if i < 7 else 0
            assignments[d.detection_id] = MoleculeAssignment(d.detection_id, domain,
                'A' if domain == 1 else 'B' if domain == 2 else '', status='domain' if domain else 'unassigned')
        regions, _ = manual_regions(data.annotations.detections, assignments, (512, 512))
        results[index] = FrameAnalysis(series.identity, index, index, 'complete',
            'Kontrola syntetyczna: zadane klasy i domeny, nie wynik detektora.', assignments,
            (ResultClass('A', '#5cb8ff'), ResultClass('B', '#ff9a53')),
            metadata={'synthetic_control': True, 'analysis_id': 'class-operation-controls',
                      'model_id': catalogue.identifier, 'input_sha256': input_fingerprint(data)},
            domain_labels=regions, catalogue=catalogue)
    analysis = ProjectAnalysis('class-operation-controls', (0, 1, 2), results,
        {i: {'status': 'complete'} for i in results}, (shared, foreign))
    path = directory / 'class-controls.stmdomains'
    save_project(path, ProjectSnapshot(series, {'current_index': 0, 'mode': 'raw', 'gamma': 1.}, analysis=analysis))
    (directory / 'README.txt').write_text(
        'SD-V4-23a — kontrola UI, nie wynik detektora.\n'
        'Uruchom python -m stmdomains.tools.class_operations_demo --open.\n'
        'Launcher otwiera ten projekt i przez operacje 23 przypisuje dwa punkty bez domeny do A.\n'
        'Stan startowy w RAM: klatka 1 A=6 B=3 (2 domeny, 2 punkty bez domeny), klatka 2 A=4 B=3.\n'
        'Klatka 3 ma inny katalog i pozostaje poza wspólnym zakresem.\n'
        'Sam plik projektu ma na klatce 1 A=4 B=3 i dwa punkty nieprzypisane.\n'
        'Launcher przygotowuje korekty w sesji; zapisz je przez Plik → Zapisz projekt….\n', encoding='utf-8')
    return path


def initialize_class_operations_demo(window) -> None:
    """Prepare the class-only members through existing user operations (ticket 23)."""
    c, m = window.controller, window.controller.manual
    if c.current_index != 0 or c.result is None or not c.result.metadata.get('synthetic_control'):
        raise ValueError('Najpierw otwórz pierwszą klatkę kontroli klas.')
    m.set_editing(True)
    m.select_molecules(tuple(k for k, a in c.result.assignments.items() if not a.domain_local_id))
    m.preview_classes('assign', target='A')
    if m.preview_result is None:
        raise ValueError(m.message)
    m.apply()
    m.selection = ()
    m.set_editing(False)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=Path('.scratch/stmdomains-ui-23a/demo'))
    parser.add_argument('--open', action='store_true', help='Otwórz kontrolę i przygotuj A=6/B=3 w pamięci sesji.')
    args = parser.parse_args()
    path = create_class_operations_demo(args.output)
    print(path)
    if args.open:
        from PyQt6.QtCore import QTimer
        from PyQt6.QtWidgets import QApplication
        from stmdomains.ui.main_window import STMDomainsMainWindow
        app = QApplication([])
        window = STMDomainsMainWindow()
        window.show()
        window.controller.open_session(path)
        def finish():
            if window.controller.is_busy:
                QTimer.singleShot(50, finish)
            else:
                initialize_class_operations_demo(window)
        QTimer.singleShot(50, finish)
        app.exec()
        window._finish_background_work()


if __name__ == '__main__':
    main()
