"""Explain independent class, order and domain decisions in user-facing terms."""

from stmdomains.analysis.acceptance_settings import ClassAcceptanceSettings
from stmdomains.analysis.order_settings import OrderSettings
from stmdomains.core.analysis_result import FrameAnalysis
from stmdomains.ui.result_style import assignment_description


def assignment_details(result: FrameAnalysis | None, detection_id: str) -> str:
    summary = assignment_description(result, detection_id)
    if result is None or result.status != "complete":
        return summary
    member = result.assignments.get(detection_id)
    if member is None or not member.provisional_class_id:
        return summary
    data = member.metadata
    settings = ClassAcceptanceSettings.from_parameters(result.parameters)
    accepted = bool(data.get("class_reliable"))
    lines = [f"Klasa wstępna: {member.provisional_class_id} (najbliższy wzorzec)",
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
    lines.append(f"Domena końcowa: {member.domain_local_id}" if member.domain_local_id else
                 "Domena końcowa: brak — " + summary)
    score = data.get("class_confidence")
    if score is not None:
        lines.append(f"Miara podobieństwa klasy: {score:.4f}; nie jest prawdopodobieństwem poprawności.")
    return "\n".join(lines)
