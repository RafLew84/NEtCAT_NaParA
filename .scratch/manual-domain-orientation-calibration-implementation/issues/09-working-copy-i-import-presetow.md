# 09 — Bezpiecznie zarządzać working copy i importem presetów

**What to build:** Operator może edytować, kopiować, porównywać, importować i usuwać presety bez przypadkowego nadpisania aktywnej konfiguracji. Built-in jest read-only, dirty working copy wymaga Save/Discard/Cancel, a nieznana schema, brak parametru lub backendu blokuje aktywację.

**Blocked by:** 08 — Zapisać, aktywować i zamrozić preset M6.

**Status:** completed

- [x] Save As, Duplicate, Rename, Delete i porównanie różnic zachowują jeden aktywny kompatybilny preset oraz nie zmieniają istniejących runów.
- [x] Built-in można aktywować lub skopiować, lecz nie nadpisać ani usunąć; przełączenie dirty working copy pokazuje Save/Discard/Cancel.
- [x] Import conflict daje Rename/Overwrite/Cancel, a starsza znana schema otwiera się jako working copy wymagająca Save As; nieznana nowsza schema fail-closed.
- [x] Tracery RED–GREEN, typecheck, targeted tests, pełne `tests/moltrack`, code-size guard i code review przechodzą; zmiana tworzy jeden commit.
- [x] Nie powstaje historia rewizji ani approval workflow poza zakresem; nowe pliki pozostają w limitach 800/30/10/80 bez nowych wyjątków.
