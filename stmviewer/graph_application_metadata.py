"""Session-only applied graphs and their bindings to frozen movie baselines."""
from typing import Callable

from stmviewer.frame import ImageFrame
from stmviewer.graph_application_types import GraphApplication
from stmviewer.graph_metadata import decode_graph, encode_graph
from stmviewer.manual_movie_types import MovieBaselineFrame, MovieSource
from stmviewer.metadata_values import json_object, optional_text


def encode_graph_application(application: GraphApplication | None) -> dict[str, object] | None:
    if application is None:
        return None
    return {'graph': encode_graph(application.graph),
            'robust_revision': application.robust_revision,
            'settings_version': application.settings_version}


def decode_graph_application(value: object, frames: tuple[ImageFrame, ...],
                             baseline: tuple[MovieBaselineFrame, ...],
                             check_cancelled: Callable[[], None], *,
                             allow_subset: bool = False) -> GraphApplication | None:
    if value is None:
        return None
    record = json_object(value, {'graph', 'robust_revision', 'settings_version'})
    if type(record['settings_version']) is not int or record['settings_version'] != 1:
        raise ValueError('Graf: nieobsługiwana wersja zastosowania.')
    graph = decode_graph(record['graph'], frames, check_cancelled, allow_subset=allow_subset)
    application = GraphApplication(graph, optional_text(record, 'robust_revision'))
    positions = application.positions
    expected_sources = tuple(MovieSource(source.source, source.source_frame_index) for source in graph.sources)
    if (tuple(item.source for item in baseline) != expected_sources
            or tuple(item.shift_xy for item in baseline) != positions
            or any(item.status != 'manual_review' or item.quality_score is not None
                   or item.inherited_uncertainty for item in baseline)):
        raise ValueError('Graf: zamrożona baza nie odpowiada zastosowanemu rozwiązaniu.')
    return application
