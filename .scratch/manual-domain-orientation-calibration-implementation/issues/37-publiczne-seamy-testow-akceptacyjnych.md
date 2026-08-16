# 37 — Usunąć prywatne seamy z testów akceptacyjnych

**What to build:** Wszystkie testy klasyfikowane jako acceptance lub release obserwują produkcyjny workflow przez publiczne kontrolki, snapshoty, zdarzenia i pliki, bez prywatnych adapterów oraz wstrzykiwania testowej kompozycji.

**Blocked by:** 34 — Ponowić pełną akceptację TTMAPP i zsynchronizować Help.

**Status:** completed

- [x] Testy acceptance/release nie wywołują `_save_as()`, nie tworzą `_MolTrackM6Adapter` i nie wstrzykują własnego session restorera, composition factory ani export callbacku.
- [x] Scenariusze wymagające pełnej integracji używają rzeczywistego `MolTrackMainWindow` oraz produkcyjnej kompozycji; testy faktycznie jednostkowe są jednoznacznie nazwane i odseparowane.
- [x] Dotychczasowe pokrycie Save/Open, presetów, obu backendów, korekt, review, eksportu v10, publikacji referencji i kampanii pozostaje zachowane.
- [x] Automatyczny guard obejmuje suite acceptance/release i zgłasza ponowne użycie uzgodnionych prywatnych seamów.
- [x] Release manifest, targeted tests, pełne `tests/moltrack`, typecheck, code-size guard i code review przechodzą; powstaje jeden commit.
