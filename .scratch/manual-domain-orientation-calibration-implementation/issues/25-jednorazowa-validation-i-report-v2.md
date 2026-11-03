# 25 — Jednokrotnie otworzyć Validation i opublikować report v2

**What to build:** Po zakończeniu Calibration operator zamraża dokładnie jednego eligible kandydata każdego backendu, a następnie otwiera Validation tylko raz. Immutable receipt i atomowy campaign report v2 zachowują wynik pozytywny albo ważny wynik negatywny bez automatycznej aktywacji presetu.

**Blocked by:** 24 — Wybrać i zamrozić First-Shell Geometry Policy.

**Status:** completed

- [x] Shortlista fingerprintuje dataset/epoch, oba backendy, kandydatów, geometrię, objective i tie-break; mismatch blokuje cały odczyt Validation.
- [x] Pierwszy odczyt tworzy receipt z `open_count=1`; drugi odczyt albo zmiana datasetu, objective, geometrii czy shortlisty jest odrzucana.
- [x] Report v2 zachowuje capability availability, per-group metrics, funnel misses, shortlistę, receipt oraz rekomendację lub legalny `validation_failed`; `preset_modified=false`.
- [x] Atomowy katalog JSON/Markdown/CSV/receipt przechodzi tracer RED–GREEN, typecheck, targeted tests, pełne `tests/moltrack`, code-size guard i code review; powstaje jeden commit. Pełny run: 1160 passed, 1 niezależny failure w `test_domain_analysis_documentation.py` — tabela `DOMAIN_ANALYSIS_FORMATS_DRAFT.md` nadal podaje session v2, a bieżący kontrakt wymaga v3.
- [x] Report writer i Validation guard są głębokimi Modules, nie rosną istniejące wyjątki, a nowe pliki mieszczą się w limitach.
