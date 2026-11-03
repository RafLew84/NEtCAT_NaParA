# 41 — Ujednolicić i walidować statusy ticketów

**What to build:** Plan implementacyjny używa jednego jawnego słownika statusów, a automatyczny validator wykrywa literówki, niespójne statusy i sprzeczność między statusem a checklistą.

**Blocked by:** 35 — Objąć całe Domain Analysis automatyczną bramką mypy.

**Status:** completed

- [x] Zostaje zdefiniowany zamknięty zestaw statusów oraz reguła przejścia ticketu z `pending` do `completed`.
- [x] Ticket 28 i wszystkie pozostałe istniejące tickety używają kanonicznych wartości bez równoległych form `done` i `completed`.
- [x] Validator skanuje wszystkie pliki w katalogu `issues` i odrzuca nieznany status, brak statusu, zduplikowany numer oraz `completed` z niezaznaczonym kryterium.
- [x] Validator jest częścią lokalnej dokumentacji jakości i tej samej bramki CI, a komunikat błędu wskazuje konkretny plik oraz naruszoną regułę.
- [x] Testy validatora, pełna walidacja planu, targeted tests i code review przechodzą; powstaje jeden commit.
