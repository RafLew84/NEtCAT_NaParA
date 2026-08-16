# 34 — Ponowić pełną akceptację TTMAPP i zsynchronizować Help

**What to build:** Po naprawie wykrytych luk operator przechodzi cały workflow wariantu C na rzeczywistym fixture TTMAPP przez produkcyjny `MainWindow`, a Help, format reference, screenshoty i walkthrough opisują dokładnie zweryfikowane zachowanie.

**Blocked by:** 28 — Udostępnić correction-aware export v10 w produkcyjnym UI; 29 — Wybrać fixed lub adaptive First-Shell Geometry w produkcyjnym workflow; 30 — Zachować audit kwarantanny po rerun i Save/Open; 31 — Publikować immutable child Reference Dataset Version z UI; 32 — Wyliczać Reference Readiness przez jeden domenowy seam; 33 — Zastąpić tuple jawnym typem Detection Identity.

**Status:** completed

- [x] Jeden test akceptacyjny używa rzeczywistego `MainWindow` i produkcyjnej kompozycji do obu backendów, korekt, review, Save/Open, exportu v10, publikacji root/child obu referencji, presetów oraz kampanii fixed/adaptive.
- [x] Testy nie wstrzykują własnego export callbacku, nie tworzą `_MolTrackM6Adapter`, nie wywołują `_save_as()` ani innych prywatnych seamów i obserwują wyłącznie publiczne snapshoty, raporty, pliki, zdarzenia oraz kontrolki operatora.
- [x] Help, user guide, technical reference, formats, troubleshooting, CONTEXT, screenshoty i release walkthrough zgadzają się z rzeczywistymi wersjami, readiness, exportem v10, child publication i geometry selection.
- [x] Lokalny link checker, version checker, typecheck, wszystkie targeted regressions, pełne `tests/moltrack` z Qt offscreen, code-size guard i dwa niezależne code review przechodzą; powstaje jeden commit.
- [x] Wszystkie findings audytu mają regresje, stare mylące oczekiwanie produkcyjnego v9 znika, nie powstają nowe ani rosnące wyjątki ratchetu, a tickety 18/19/21/24/26/27 mogą zostać ponownie oznaczone jako ukończone.
