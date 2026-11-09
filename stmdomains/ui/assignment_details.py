"""Explain independent class, order and domain decisions in user-facing terms."""

from stmdomains.analysis.acceptance_settings import ClassAcceptanceSettings
from stmdomains.analysis.order_settings import OrderSettings
from stmdomains.core.analysis_result import FrameAnalysis
from stmdomains.core.manual_domains import MANUAL_METHOD
from stmdomains.core.result_names import class_name, domain_name
from stmdomains.analysis.geometry_domain_settings import GeometryDomainSettings, METHOD
from stmdomains.analysis.freud_settings import FreudSettings, METHOD as FREUD_METHOD
from stmdomains.ui.result_style import assignment_description


def assignment_details(result: FrameAnalysis | None, detection_id: str) -> str:
    summary = assignment_description(result, detection_id)
    if result is None or result.status != "complete":
        return summary
    member = result.assignments.get(detection_id)
    if member is not None and result.parameters.get('domain_method') == MANUAL_METHOD:
        source = member.metadata.get('manual_source', {})
        return (summary + '\nKorekta ręczna nie zmienia oceny metody.\n'
                + f"Źródłowe ID klasy: {source.get('class_id', member.class_id) or 'brak'}. "
                + f"Źródłowe ID domeny: {source.get('domain_local_id', member.domain_local_id)}.\n"
                + f"Pierwotny powód odmowy: {member.rejection_reason or 'brak'}.\n"
                + 'Porównaj z „Automatyczny przed korektą”, aby obejrzeć pierwotną ocenę.')
    if member is not None and result.parameters.get('domain_method') in (METHOD, FREUD_METHOD):
        measured = member.metadata.get('geometry', {})
        geometric_settings = GeometryDomainSettings.from_parameters(result.parameters)
        axes = measured.get('axes', ())
        unit = result.parameters.get('calibration', {}).get('unit', 'px')
        lines = [summary, f'Użyte limity całego regionu: {geometric_settings.angle_degrees:g}°, {geometric_settings.spacing_percent:g}%.',
                 f'Minimum koherencji: {geometric_settings.minimum_coherence:g}; lokalnych punktów: {geometric_settings.minimum_local_count}.',
                 f"Pomiar: {measured.get('status', '—')}; punkty {measured.get('local_count', '—')}; "
                 f"efektywne {measured.get('effective_count', 0):.2f}."]
        lines.extend(f"Kierunek {i+1}: {a['row_angle_deg']:.2f}°; rozstaw {a['period']:.3f} {unit}; koherencja {a['coherence']:.3f}."
                     for i, a in enumerate(axes))
        if result.parameters.get('domain_method') == FREUD_METHOD:
            env = member.metadata.get('freud_environment', {})
            freud_settings = FreudSettings.from_parameters(result.parameters)
            lines.extend([f'Klasa otoczenia freud: {class_name(result, member.provisional_class_id)}.',
                f'Tolerancja: {freud_settings.tolerance:g} ×NN; zasięg: {freud_settings.radius_factor:g} ×NN; '
                f'rejestracja: {"obrót lub odbicie płaskiego otoczenia" if freud_settings.registration else "wyłączona"}.',
                f'NN klatki: {result.parameters.get("spacing_metric", 0):.4g} {unit}.',
                f'Sąsiedzi: {env.get("observed_count", 0)}/{freud_settings.neighbor_count}.',
                'ID i odległości: ' + ', '.join(f'{identity} ({distance:.3f} ×NN)'
                    for identity, distance in zip(env.get('neighbor_ids', ()), env.get('distances_nn', ()))),
                'Klasa opisuje podobne otoczenia. Dopasowanie obrotu nie usuwa warunku zgodnej orientacji domeny.'])
        lines.append('Typ nieznany. Zgodność fazy nie została sprawdzona. Brak przypisania nie dowodzi fizycznej granicy.')
        return '\n'.join(lines)
    if member is None or not member.provisional_class_id:
        return summary
    data = member.metadata
    settings = ClassAcceptanceSettings.from_parameters(result.parameters)
    accepted = bool(data.get("class_reliable"))
    lines = [f"Klasa wstępna: {class_name(result, member.provisional_class_id)} (najbliższy wzorzec)",
             "Akceptacja klasy: " + ("przyjęta" if accepted else "odrzucona")]
    if not data.get("descriptor_valid", True):
        lines.append("Opis otoczenia: niewystarczające dane.")
    if data.get("centroid_margin_applicable", True):
        margin = data.get("centroid_margin")
        if margin is not None:
            lines.append(f"Margines: {margin:.4f}; wymagane ≥ {settings.class_margin:g}."
                         + (" Zbyt mała przewaga nad drugą klasą." if not data.get("class_margin_passed", True) else ""))
    else:
        lines.append("Margines: nie dotyczy (K1 — brak drugiej klasy).")
    distance, limit = data.get("centroid_distance"), data.get("class_radius_limit")
    if distance is not None and limit is not None:
        lines.append(f"Odległość od wzorca: {distance:.4f}; dopuszczalna ≤ {limit:.4f} "
                     f"(mnożnik {settings.class_radius_multiplier:g}, jednostki cech)."
                     + (" Otoczenie poza promieniem klasy." if not data.get("class_radius_passed", True) else ""))
    if not data.get("order_support_sufficient"):
        order = "niewystarczające otoczenie do oceny"
    else:
        order = "potwierdzony" if data.get("order_supported") else "niepotwierdzony"
    lines.append(f"Porządek lokalny: {order} (test periodyczności metody).")
    order_settings = OrderSettings.from_parameters(result.parameters)
    if "local_point_count" in data:
        lines.append(f"Punkty lokalne: {data['local_point_count']}; wymagane ≥ {order_settings.order_minimum_local_count}.")
        lines.append(f"Punkty efektywne: {data['effective_point_count']:.3f}; "
                     f"wymagane ≥ {order_settings.order_minimum_effective_count:g}.")
        lines.append(f"Koherencja: {data['order_score']:.4f}; wymagane > próg kontroli {data['order_threshold']:.4f} "
                     f"(kwantyl {order_settings.order_quantile:g}).")
        lines.append(f"Otoczenie porządku: promień {order_settings.order_radius_factor:g} × d, "
                     f"sigma {order_settings.order_sigma_factor:.6g} × d; d = {result.parameters['spacing_px']:.3f} px.")
        lines.append("Kwantyl nie jest pewnością domeny. Jeden kierunek periodyczności nie potwierdza sieci 2D.")
    lines.append(f"Domena końcowa: {domain_name(result, member.domain_local_id)} (ID {member.domain_local_id})" if member.domain_local_id else
                 "Domena końcowa: brak — " + summary)
    score = data.get("class_confidence")
    if score is not None:
        lines.append(f"Miara podobieństwa klasy: {score:.4f}; nie jest prawdopodobieństwem poprawności.")
    return "\n".join(lines)
