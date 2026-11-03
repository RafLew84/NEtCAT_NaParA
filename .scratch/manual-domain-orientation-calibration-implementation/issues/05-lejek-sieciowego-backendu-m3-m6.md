# 05 — Zachować lejek sieciowego backendu M3/M6

**What to build:** Backend `m3_m6_lattice_network` wypełnia ten sam Funnel własnym natywnym evidence z istniejącego pipeline'u: local M3/M6, edge decisions, seed/growth, core/halo/boundary, domain size i QC. Implementacja deleguje do istniejących analiz i nie kopiuje ich algorytmów.

**Blocked by:** 04 — Zachować lejek klasycznego backendu M6.

**Status:** completed

- [x] Każdy natywnie obsługiwany etap zachowuje wersjonowane evidence i fingerprint producenta; brak danych jest `null` z reason, nie zerem lub pustą kolekcją.
- [x] Wynik raw A/B/C pozostaje dostępny po threshold, post-processingu i manual override, a suma terminalnych funnel misses jest spójna z późniejszą ewaluacją.
- [x] UI czyta backend-neutralny Funnel i otwiera właściwy typ native evidence wyłącznie na podstawie capability.
- [x] Tracer RED–GREEN oraz regresje obu backendów przechodzą razem z typecheck, pełnym `tests/moltrack`, code-size guard i code review; zmiana tworzy jeden commit.
- [x] Nie powstaje drugi pipeline ani shallow pass-through Module; nowe pliki celują w 250–500 i nie przekraczają twardych limitów.
