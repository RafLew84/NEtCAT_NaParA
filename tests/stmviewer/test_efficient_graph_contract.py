"""Stored correspondence evidence must describe the same graph sources."""
from dataclasses import replace

import pytest

from test_efficient_session import efficient_graph
from test_manual_movie import cpu_result
from stmviewer.graph_application import apply_graph_to_movie
from stmviewer.registration import RegistrationError


def test_application_refuses_preparation_from_another_original_geometry():
    frames = tuple(item.original for item in cpu_result().frames)
    graph = efficient_graph(frames)
    edge = graph.edges[0]
    diagnostic = edge.correspondence_diagnostics
    preparation = diagnostic.preparation[0]
    h, w = preparation.original_shape
    left, top, right, bottom = preparation.padding_ltrb
    wrong = replace(preparation, original_shape=(h - 1, w),
                    padding_ltrb=(left, top, right, bottom + 1))
    changed = replace(diagnostic, preparation=(wrong, diagnostic.preparation[1]))
    graph = replace(graph, edges=(replace(edge, correspondence_diagnostics=changed),) + graph.edges[1:])
    with pytest.raises(RegistrationError, match='orygina'):
        apply_graph_to_movie(frames, graph)


@pytest.mark.parametrize('changed_field', ['missing_diagnostic', 'missing_preparation', 'certainty'])
def test_application_rejects_lost_evidence_or_invented_model_certainty(changed_field):
    frames = tuple(item.original for item in cpu_result().frames)
    graph = efficient_graph(frames)
    edge = graph.edges[0]
    if changed_field == 'missing_diagnostic':
        edge = replace(edge, correspondence_diagnostics=None)
    elif changed_field == 'missing_preparation':
        edge = replace(edge, correspondence_diagnostics=replace(edge.correspondence_diagnostics, preparation=()))
    else:
        edge = replace(edge, status='ok', quality_score=.95)
    graph = replace(graph, edges=(edge,) + graph.edges[1:])
    with pytest.raises(RegistrationError):
        apply_graph_to_movie(frames, graph)
