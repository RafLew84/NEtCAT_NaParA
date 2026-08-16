# 07 — Nawigować hierarchią domen bez zmiany selection

**What to build:** Operator rozwija Domain → A-Z/Unknown, wybiera Small ordered islands albo Unassigned i podświetla odpowiadającą geometrię na canvasie. Highlight jest wyłącznie nawigacją; selection i prepared command pozostają niezależnymi stanami jednego workspace.

**Blocked by:** 06 — Otworzyć Spatial Command Center nad jednym workspace.

**Status:** completed

- [x] Kliknięcie domeny, podobszaru lub grupy pomocniczej aktualizuje właściwy highlight i nigdy nie tworzy selection ani korekty.
- [x] Neutralne obrysy domen, żółty highlight i redundantne kolor+kształt markerów A-Z są zgodne z zatwierdzonym prototypem.
- [x] Hierarchia, ledger summary i overlay są projekcjami tego samego snapshotu, a zmiana klatki usuwa niepoprawne frame-local wskazania.
- [x] Tracer Qt RED–GREEN, typecheck, targeted tests, pełne `tests/moltrack`, code-size guard i code review przechodzą; zmiana tworzy jeden commit.
- [x] Widgety pozostają cienkimi Adapterami, nowe pliki celują w 250–500 i nie przekraczają limitów 800/30/10/80.
