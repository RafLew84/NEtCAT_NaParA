# 06 — Otworzyć Spatial Command Center nad jednym workspace

**What to build:** Produkcyjny Domain Analysis otwiera wariant C: centralny canvas, pionowy rail etapów i kontekstowy dolny arkusz. Analyze oraz diagnostyka działają nad jednym `DomainAnalysisWorkspaceController`; przełączenie etapu nie tworzy kopii wyniku ani drugiego controllera.

**Blocked by:** 05 — Zachować lejek sieciowego backendu M3/M6.

**Status:** completed

- [x] Qt offscreen potwierdza strukturę Spatial Command Center i zachowanie bieżącej analizy po otwarciu, zmianie klatki oraz przełączeniu stage.
- [x] Canvas, rail i bottom sheet wyłącznie renderują jeden immutable snapshot i wysyłają typowane akcje przez `dispatch(...)`.
- [x] Istniejące Analyze, cancel, run status i diagnostics pozostają działające po zastąpieniu starego układu.
- [x] Tracer RED–GREEN, typecheck, targeted UI tests, pełne `tests/moltrack`, code-size guard i code review przechodzą; zmiana tworzy jeden commit.
- [x] Główny window i inne wyjątki ratchetu nie rosną; routing trafia do cienkiej kompozycji, a nowe pliki nie przekraczają 800 linii.
