"""Explain independent class, order and domain decisions in user-facing terms."""

from stmdomains.analysis.acceptance_settings import ClassAcceptanceSettings
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
    lines.append(f"Domena końcowa: {member.domain_local_id}" if member.domain_local_id else
                 "Domena końcowa: brak — " + summary)
    score = data.get("class_confidence")
    if score is not None:
        lines.append(f"Miara podobieństwa klasy: {score:.4f}; nie jest prawdopodobieństwem poprawności.")
    return "\n".join(lines)
