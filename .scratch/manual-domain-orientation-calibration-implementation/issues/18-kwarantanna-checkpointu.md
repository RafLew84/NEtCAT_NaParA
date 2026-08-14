# 18 — Kwarantannować niereprodukowalny checkpoint po Open

**What to build:** Po Open loader ponownie liczy Effective Domain Projection i porównuje jej fingerprint z materializowanym checkpointem. Niezgodność zachowuje pełny payload do audytu, lecz nie aktywuje korekt ani nie pozwala traktować sesji jako reference-ready.

**Blocked by:** 17 — Migrować session v2 do pustej historii v3.

**Status:** completed

- [x] Zmieniony checkpoint, anchor revision, stabilne ID albo invariant prowadzą do ustrukturyzowanego `quarantined/conflicted`, nie do częściowej aktywacji.
- [x] Automatic snapshot i correction history pozostają dostępne diagnostycznie, a reference-ready export oraz publikacja datasetu są zablokowane.
- [x] Poprawny checkpoint przechodzi round-trip bez utraty stanu, a nieznane opaque audit data nie staje się aktywną semantyką.
- [x] Tracer RED–GREEN, typecheck, targeted tests, pełne `tests/moltrack`, code-size guard i code review przechodzą; zmiana tworzy jeden commit.
- [x] Quarantine policy ma jednego właściciela i nie jest duplikowana w UI lub eksporcie; pliki pozostają w twardych limitach.
