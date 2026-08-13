# 12 — Zatwierdzać atomowy polygon batch z konfliktami

**What to build:** Point/multi oraz jeden lub kilka polygonów przygotowują zamrożony, deduplikowany batch `source_id`. Preview pokazuje skutki na wybranej osi oraz ustrukturyzowane konflikty, a Apply wykonuje wszystko albo nic i wymaga jawnego potwierdzenia high impact.

**Blocked by:** 11 — Zarządzać ręczną domeną ze stabilnym UUID.

**Status:** completed

- [x] Polygon wybiera molekuły po centroidzie, nie staje się trwałym regionem i zachowuje widoczny selection do Apply lub Clear.
- [x] Policy rozróżnia `blocked`, `confirmation_required` i `informational`; blokady są nieomijalne, a potwierdzenie wiąże dokładnie jeden prepared preview.
- [x] Zmiana selection, osi, targetu, reason, fingerprintu lub workspace revision unieważnia preview; nie zapisuje się bezkonfliktowego podzbioru.
- [x] Potwierdzony batch dopisuje jeden atom i unieważnia właściwy review; tracery RED–GREEN, typecheck, targeted tests, pełne `tests/moltrack`, code-size guard i code review przechodzą; powstaje jeden commit.
- [x] UI nie odtwarza polityki konfliktów; nowe pliki pozostają poniżej 800 linii i pozostałych limitów bez wzrostu ratchetu.
