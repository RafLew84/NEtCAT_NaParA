"""Short catalogue descriptions keep independent class labels distinguishable."""

from stmdomains.core.class_catalogue import ClassCatalogue


def catalogue_description(catalogue: ClassCatalogue | None) -> str:
    if catalogue is None:
        return "Brak dopasowanego katalogu"
    first, last = catalogue.frame_indices[0] + 1, catalogue.frame_indices[-1] + 1
    scope = (f"lokalny kl. {first}" if catalogue.scope == "current_frame" else
             f"wspólny, cała seria ({len(catalogue.frame_indices)} kl.)" if catalogue.scope == "whole_series" else
             f"wspólny kl. {first}–{last}")
    return f"K{catalogue.k} · {scope} · katalog {catalogue.identifier[:8]}"
