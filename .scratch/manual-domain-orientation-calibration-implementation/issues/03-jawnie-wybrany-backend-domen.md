# 03 — Uruchamiać jawnie wybrany backend domen

**What to build:** Operator jawnie wybiera `m6_orientation_components` albo `m3_m6_lattice_network` dla Domain Analysis. Jeden głęboki Module rozwiązuje właściwy Adapter, publikuje backend-qualified automatic snapshot i izoluje cache; brak wyboru lub adaptera kończy się czytelnym błędem zamiast cichego defaultu.

**Blocked by:** 01 — Ustanowić zielone bramki implementacyjne Domain Analysis.

**Status:** completed

- [x] Ten sam wspólny podział zwrócony przez dwa Adaptery ma różne fingerprinty przez pełną backend identity i zachowuje typowane native evidence.
- [x] Request bez jawnego backendu jest odrzucany, a UI pozwala wybrać oba stabilne backend IDs bez nazywania ich względnie `legacy/new`.
- [x] Cache nigdy nie trafia cross-backend; identyczny pełny key z różnym result fingerprintem pozostaje błędem integralności.
- [x] Tracer RED–GREEN obserwuje `DomainAnalysisModule.run(...)`; typecheck, targeted tests, pełne `tests/moltrack`, code-size guard i code review przechodzą, a zmiana tworzy jeden commit.
- [x] Nie jest powiększany żaden plik ratchetu; nowe Modules mają mały Interface, celują w 250–500 i nie przekraczają 800 linii.
