# 15 — Porównać rerun i wykonać atomowy Correction Rebase

**What to build:** Zakończony rerun tworzy pending automatic candidate i nie zastępuje aktywnej skorygowanej projekcji. Operator wykonuje Compare & Rebase, rozstrzyga changed geometry, brakujące ID oraz split/merge i atomowo promuje nową bazę do kolejnej immutable correction revision.

**Blocked by:** 14 — Reviewować M6 i Orientation niezależnie.

**Status:** completed

- [x] Identyczny pełny fingerprint jest no-op; inny backend lub wynik pozostaje pending do jawnej promocji całego zamrożonego zakresu.
- [x] Bezpieczny rebase mapuje po `physical_frame_id`, `source_id` i zgodnych fingerprintach, nigdy wyłącznie po współrzędnych lub snapshot-local domain ID.
- [x] Changed geometry, split/merge i brak targetu wymagają jawnego `reapplied`, `remapped` albo `dropped` z reason; stale/conflicted nie zasila efektywnej projekcji.
- [x] Tracery RED–GREEN, typecheck, targeted tests, pełne `tests/moltrack`, code-size guard i code review przechodzą; zmiana tworzy jeden commit.
- [x] Policy rebase pozostaje jednym głębokim Module, a nowe pliki celują w 250–500 i nie przekraczają twardych limitów.
