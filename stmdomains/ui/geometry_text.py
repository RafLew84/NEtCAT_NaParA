"""Human-facing geometry explanations, independent of widget layout."""
from html import escape
from stmdomains.analysis.geometry_summary import summarize_axes
from stmdomains.core.frame_presentation import PresentedFrame
from stmdomains.core.result_names import domain_name

STATUS = {'lattice_2d': 'Sieć 2D — dwa kierunki', 'rows_1d': 'Rzędy — jeden kierunek',
          'insufficient': 'Niewystarczające dane', 'unresolved': 'Nierozstrzygnięte'}


def geometry_text(view: PresentedFrame | None, selected: str | None, domain: bool) -> str:
    if view is None or view.geometry is None:
        return 'Pomierz geometrię bieżącej klatki, a następnie kliknij molekułę na obrazie.'
    geometry = view.geometry
    if selected is None or selected not in geometry.molecules:
        counts = {status: sum(m.status == status for m in geometry.molecules.values()) for status in STATUS}
        return ('<b>Klatka '+str(geometry.working_index+1)+'</b><br>'
                + '<br>'.join(f'{label}: {counts[key]}' for key, label in STATUS.items())
                + '<br><br>Kliknij molekułę, aby zobaczyć pomiar lub podsumowanie jej domeny.'
                + '<br>'+escape(geometry.message))
    record = geometry.molecules[selected]
    unit = geometry.calibration.unit
    if domain:
        result = view.result
        assignment = result.assignments.get(selected) if result else None
        domain_id = assignment.domain_local_id if assignment else None
        if not domain_id or result is None:
            return 'Ta molekuła nie należy do domeny w wyświetlanym wyniku. Podsumowanie pomiarów wymaga przypisanej domeny.'
        members = [geometry.molecules[key] for key, a in result.assignments.items()
                   if a.domain_local_id == domain_id and key in geometry.molecules]
        summary = summarize_axes(members)
        parts = [f'<b>Domena {escape(domain_name(result, domain_id))}</b> (ID {domain_id})',
                 f'Poprawne pomiary: {summary["valid_count"]} / {summary["total_count"]}']
        for index, axis in enumerate(summary['axes'], 1):
            angle = 'niejednoznaczny' if axis['angle_deg'] is None else f'{axis["angle_deg"]:.1f}°'
            dispersion = '—' if axis['dispersion_deg'] is None else f'{axis["dispersion_deg"]:.1f}°'
            parts.extend([f'<b>Rodzina {index}: {angle}</b>', f'Rozrzut osiowy: {dispersion} · n={axis["count"]}',
                          f'Rozstaw: mediana {axis["period_median"]:.2f} {unit}',
                          f'Zakres {axis["period_min"]:.2f}–{axis["period_max"]:.2f} {unit}'])
        parts += ['Średnia osiowa z 2θ; orientacja nie oznacza typu domeny.']
        return '<br>'.join(parts)
    parts = [f'<b>{STATUS[record.status]}</b>']
    if unit == 'nm':
        parts.append('nm według nagłówka MPP; skala niezweryfikowana.')
    for index, axis in enumerate(record.axes, 1):
        parts.extend([f'<br><b>Rzędy {index}: {axis.row_angle_deg:.1f}°</b>',
                      f'<b>Rozstaw poprzeczny: {axis.period:.2f} {unit}</b>',
                      f'Normalna częstości: {axis.normal_angle_deg:.1f}°',
                      f'Koherencja: {axis.coherence:.3f}'])
    if not record.axes:
        parts.append('Kierunek i rozstaw: —')
    parts.append('<br>'+escape(record.reason))
    parts.append('Rozstaw wzdłuż rzędów: nie wyznaczono.')
    parts.append(f'Punkty otoczenia: {record.local_count} · efektywne: {record.effective_count:.1f}')
    if record.radius is not None:
        parts.append(f'Promień otoczenia: {record.radius:.2f} {unit}')
    if record.touches_edge:
        parts.append('Otoczenie ucięte krawędzią obrazu.')
    if record.angle_stability_deg is not None and record.period_stability_fraction is not None:
        parts.append(f'Stabilność: Δθ ≤ {record.angle_stability_deg:.2f}°; Δd ≤ {100*record.period_stability_fraction:.1f}%')
    parts.extend(['Zmiana promienia ±10%, stałe ważenie Gaussa. To stabilność, nie przedział ufności.',
                  'Koherencja nie jest prawdopodobieństwem poprawności.',
                  'Kąt od poziomu obrazu, przeciwnie do wskazówek zegara, modulo 180°.',
                  escape(geometry.calibration.source)])
    return '<br>'.join(parts)
