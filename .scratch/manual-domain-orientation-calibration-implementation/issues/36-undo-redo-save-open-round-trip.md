# 36 — Zachować aktywną historię Undo/Redo przez Save/Open

**What to build:** Session v3 zachowuje niepustą historię korekt wraz z pozycją kursora, dzięki czemu operator może kontynuować Undo i Redo po zapisaniu oraz ponownym otwarciu sesji.

**Blocked by:** 13 — Utrzymywać append-only historię Undo/Redo; 16 — Zapisywać pełny stan w Session v3.

**Status:** completed

- [x] Scenariusz akceptacyjny tworzy co najmniej dwie korekty, wykonuje Undo przed zapisem i zapisuje jednocześnie niepusty stos Undo oraz Redo bez wykonywania rebase.
- [x] Po Save/Open kolejność rekordów historii, identyfikatory operacji, revision, cursor oraz wartości `can_undo` i `can_redo` są semantycznie identyczne.
- [x] Redo po otwarciu i następujące po nim Undo odtwarzają właściwe domeny, projekcje, konflikty oraz osobne stany review M6 i orientation.
- [x] Test przechodzi przez publiczny workflow produkcyjnego `MainWindow`; nie podmienia serializatora, session restorera ani kontrolera historii.
- [x] Tracer RED–GREEN, typecheck, targeted tests, pełne `tests/moltrack`, code-size guard i code review przechodzą; powstaje jeden commit.
