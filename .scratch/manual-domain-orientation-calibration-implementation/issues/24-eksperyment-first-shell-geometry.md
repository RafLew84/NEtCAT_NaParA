# 24 — Wybrać i zamrozić First-Shell Geometry Policy

**What to build:** Kampania porównuje na Calibration stały zakres fizyczny z deterministyczną polityką adaptacyjną wyznaczaną z `g(r)`. Operator wybiera i zamraża jedną policy z parametrami, fingerprintem, evidence oraz jawnym fixed fallback przed klasyfikacyjnym sweepem.

**Blocked by:** 23 — Rankingować kandydatów M6 source-aligned objective.

**Status:** completed

- [x] Fixed i adaptive policy używają ręcznych first-shell edges oraz raportują P/R/F1 per measurement group i symmetry bez otwierania Validation.
- [x] Adaptive `g(r)` jest deterministyczna, wersjonowana i zawsze zapisuje fixed fallback z reason; brak capability nie prowadzi do cichego defaultu.
- [x] Zmiana geometry fingerprint unieważnia dalszy search i shortlistę, a promienie nie trafiają ukradkiem do tego samego sweepu co q/seed/grow/domain-size.
- [x] Tracer RED–GREEN, typecheck, targeted tests, pełne `tests/moltrack`, code-size guard i code review są zweryfikowane; zmiana tworzy jeden commit. Pełny run: 1156 passed, 1 niezależny failure w niestage’owanych `test_domain_analysis_documentation.py` / `DOMAIN_ANALYSIS_FORMATS_DRAFT.md` (oczekiwane session v3, dokument nadal wskazuje v2).
- [x] Geometry Module ma mały Interface i nie powiększa istniejących wyjątków ratchetu; nowe pliki pozostają poniżej twardych limitów.
