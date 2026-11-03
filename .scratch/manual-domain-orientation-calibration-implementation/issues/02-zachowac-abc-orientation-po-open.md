# 02 — Zachować capability `abc_orientation` po Open

**What to build:** Operator może otworzyć draft zapisany bez aktywnego A/B/C, później włączyć `abc_orientation`, zapisać sesję i ponownie ją otworzyć. Restore odtwarza wybór sesji, ale nigdy nie zastępuje runtime capability catalog niepełną listą aktywnych konfiguracji.

**Blocked by:** 01 — Ustanowić zielone bramki implementacyjne Domain Analysis.

**Status:** completed

- [x] Tracer Open bez A/B/C → enable `abc_orientation` → Save → Open rozpoczyna jako RED z rozpoznanej regresji i przechodzi przez produkcyjny seam kompozycji.
- [x] Restore zachowuje pełny runtime capability catalog, a brakujący adapter jest raportowany jawnie zamiast rekonstruowany lub usuwany.
- [x] Bieżące scenariusze Save/Open z A/B/C włączonym i wyłączonym pozostają zgodne.
- [x] Typecheck, targeted tests, pełne `tests/moltrack` z Qt offscreen, code-size guard i code review przechodzą; zmiana tworzy jeden commit.
- [x] Nowe pliki celują w 250–500 i nie przekraczają 800 linii; nie rośnie żaden wyjątek ratchetu ani plik objęty istniejącym wyjątkiem.
