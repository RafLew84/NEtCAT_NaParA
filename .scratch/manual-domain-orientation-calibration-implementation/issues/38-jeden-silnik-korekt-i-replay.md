# 38 — Współdzielić jeden silnik Apply, Replay, Undo i Redo

**What to build:** Wykonywanie i odtwarzanie korekt korzysta z jednego właściciela przejść stanu, zamiast dwóch równoległych implementacji w `domain_correction.py` i `domain_correction_replay.py`.

**Blocked by:** 36 — Zachować aktywną historię Undo/Redo przez Save/Open.

**Status:** completed

- [x] Apply i Replay delegują walidację, wybór manualnej domeny, zmianę projekcji oraz budowę wyniku do jednego domenowego silnika przejść stanu.
- [x] Duplikacja `_manual_domain_index` i rozbieżne gałęzie obsługi typów operacji zostają usunięte bez pass-through wrapperów.
- [x] Testy kontraktowe dowodzą, że bezpośrednie Apply oraz Replay tego samego logu dają identyczny stan, revision, konflikty i readiness.
- [x] Undo/Redo, rebase, session round-trip i quarantine zachowują dotychczasową semantykę oraz jawne błędy domenowe.
- [x] Typecheck, targeted tests, pełne `tests/moltrack`, code-size guard i code review przechodzą bez nowych wyjątków ratchetu; powstaje jeden commit.
