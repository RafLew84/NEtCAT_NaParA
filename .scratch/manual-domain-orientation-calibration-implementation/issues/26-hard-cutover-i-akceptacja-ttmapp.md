# 26 — Przeprowadzić hard cutover i pełną akceptację TTMAPP

**What to build:** Na zamrożonym rzeczywistym fixture TTMAPP operator przechodzi cały workflow: oba backendy, korekty punktowe i polygon, niezależny review, Save/Open, export v10, publikację obu referencji, presety oraz kampanię. Dopiero po GREEN usuwane są stare ścieżki i pola zastąpione nowym kontraktem.

**Blocked by:** 09 — Bezpiecznie zarządzać working copy i importem presetów; 22 — Publikować osobny Orientation Reference Dataset v2; 25 — Jednokrotnie otworzyć Validation i opublikować report v2.

**Status:** completed

- [x] Jeden test akceptacyjny przechodzi pełny workflow wariantu C na TTMAPP i potwierdza zgodne fingerprinty od automatic snapshotu do campaign input.
- [x] Usunięte zostają stare dataset-level `reviewed/reviewed_by`, bez-backendowe snapshoty i nieużywane ścieżki UI; nie pozostaje dual-write, fallback ani feature flag starej semantyki.
- [x] Rzeczywisty raport porównuje oba backendy na tych samych referencjach; wartości demonstracyjne nie wybierają defaultu ani first-shell policy.
- [x] Typecheck, wszystkie targeted regressions, pełne `tests/moltrack` z Qt offscreen, code-size guard i niezależne code review przechodzą; cutover tworzy jeden celowy commit.
- [x] Żaden istniejący wyjątek ratchetu nie rośnie, nie powstaje nowy; code review stosuje deletion test i odrzuca shallow pass-through Modules.
