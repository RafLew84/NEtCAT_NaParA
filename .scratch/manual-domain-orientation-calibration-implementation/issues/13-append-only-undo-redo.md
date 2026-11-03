# 13 — Cofać i ponawiać korekty append-only

**What to build:** Operator cofa lub ponawia cały ostatni atom korekty, a historia zachowuje wszystkie wcześniejsze decyzje. Dostępność Undo/Redo wynika z append-only correction history, przetrwa Save/Open i nigdy nie zależy od pamięci widgetu.

**Blocked by:** 12 — Zatwierdzać atomowy polygon batch z konfliktami.

**Status:** completed

- [x] Undo/Redo dopisują rekordy wskazujące operation ID, obejmują cały batch i odtwarzają ten sam stabilny UUID oraz stan wszystkich punktów.
- [x] Nowy Apply po Undo zamyka gałąź Redo bez usuwania audytu; rerun/rebase pozostają twardą granicą historii.
- [x] Apply, Undo i Redo unieważniają tylko dotknięty target review, a cofnięcie nie przywraca starego sign-off.
- [x] Tracer RED–GREEN, typecheck, targeted tests, pełne `tests/moltrack`, code-size guard i code review przechodzą; zmiana tworzy jeden commit.
- [x] Replay i availability pozostają Implementation jednego Module; pliki celują w 250–500 i nie przekraczają limitów.
