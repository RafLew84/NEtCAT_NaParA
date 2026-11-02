"""Small exported graph provenance; detailed measurements belong only to sessions."""
from dataclasses import asdict, dataclass
from typing import TYPE_CHECKING

from stmviewer.graph_types import GraphConfig, XY

if TYPE_CHECKING:
    from stmviewer.manual_movie_types import MovieHistory
    from stmviewer.registration import RegistrationResult


@dataclass(frozen=True)
class GraphMovieProvenance:
    graph_revision: str
    robust_revision: str | None
    config: GraphConfig
    solver: str
    solver_settings: tuple[tuple[str, str], ...]
    final_positions: tuple[XY, ...]
    settings_version: int = 1


def movie_history(result: 'RegistrationResult') -> 'MovieHistory':
    """Freeze base, overrides and final coordinates without any image buffers."""
    from stmviewer.manual_movie_types import MovieHistory
    from stmviewer.manual_movie_metadata import manual_frame_state

    history = MovieHistory(result.revision, result.settings_version, result.baseline, result.corrections)
    application = result.graph_application
    if application is None:
        return history
    graph = application.graph
    settings: tuple[tuple[str, str], ...] = ()
    if application.robust_revision is not None:
        variant = next(item for item in graph.robust_trials if item.revision == application.robust_revision)
        settings = tuple((key, str(value)) for key, value in asdict(variant.config).items())
    provenance = GraphMovieProvenance(
        graph.revision, application.robust_revision, graph.config, application.solver, settings,
        tuple(manual_frame_state(history, index).shift_xy for index in range(len(history.baseline))))
    return MovieHistory(history.revision, history.settings_version, history.baseline,
                        history.corrections, provenance)


def decode_graph_movie_provenance(value: object) -> GraphMovieProvenance:
    from stmviewer.graph_metadata import decode_graph_config
    from stmviewer.metadata_values import json_object, optional_number, optional_text

    record = json_object(value, {'graph_revision', 'robust_revision', 'config', 'solver',
                                 'solver_settings', 'final_positions', 'settings_version'})
    revision = optional_text(record, 'graph_revision')
    robust_revision = optional_text(record, 'robust_revision')
    solver = optional_text(record, 'solver')
    if not revision or not revision.strip() or '\x00' in revision:
        raise ValueError('Graf: brak identyfikatora pochodzenia.')
    if robust_revision is not None and (not robust_revision.strip() or '\x00' in robust_revision):
        raise ValueError('Graf: nieprawidłowy wariant pochodzenia.')
    expected_solver = 'equal-ls-v1' if robust_revision is None else 'block-huber-irls-v1'
    if solver != expected_solver or type(record['settings_version']) is not int or record['settings_version'] != 1:
        raise ValueError('Graf: nieobsługiwana wersja pochodzenia lub solvera.')
    coordinates = record['final_positions']
    if not isinstance(coordinates, (list, tuple)) or len(coordinates) < 2:
        raise ValueError('Graf: wymagane pełne końcowe pozycje.')
    positions = []
    for coordinate in coordinates:
        if not isinstance(coordinate, (list, tuple)) or len(coordinate) != 2:
            raise ValueError('Graf: pozycja wymaga dwóch współrzędnych.')
        x, y = (optional_number({'n': number}, 'n') for number in coordinate)
        if x is None or y is None:
            raise ValueError('Graf: pozycja nie może być null.')
        positions.append((x, y))
    settings = record['solver_settings']
    if not isinstance(settings, (list, tuple)):
        raise ValueError('Graf: nieprawidłowe ustawienia solvera.')
    pairs = []
    for item in settings:
        if (not isinstance(item, (list, tuple)) or len(item) != 2
                or any(not isinstance(text, str) or not text.strip() for text in item)):
            raise ValueError('Graf: nieprawidłowe ustawienie solvera.')
        pairs.append((str(item[0]), str(item[1])))
    if len(dict(pairs)) != len(pairs) or (robust_revision is None and pairs):
        raise ValueError('Graf: sprzeczne ustawienia solvera.')
    if robust_revision is not None:
        from stmviewer.robust_graph_types import RobustConfig
        expected_keys = set(asdict(RobustConfig()))
        mapping = dict(pairs)
        if set(mapping) != expected_keys or mapping['solver'] != solver:
            raise ValueError('Graf: niekompletne ustawienia Hubera.')
        for key in expected_keys - {'solver', 'condition_method'}:
            try:
                number = float(mapping[key])
            except ValueError as error:
                raise ValueError('Graf: nieprawidłowe ustawienie Hubera.') from error
            optional_number({'n': number}, 'n', positive=True)
        if (not mapping['max_iterations'].isdigit()
                or mapping['condition_method'] != RobustConfig().condition_method):
            raise ValueError('Graf: nieobsługiwane ustawienie Hubera.')
    return GraphMovieProvenance(revision, robust_revision, decode_graph_config(record['config']),
                                expected_solver, tuple(pairs), tuple(positions))
