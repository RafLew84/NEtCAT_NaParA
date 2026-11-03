# 01 — Ustanowić zielone bramki implementacyjne Domain Analysis

**What to build:** Maintainer ma jeden powtarzalny zestaw bramek dla implementacji Domain Analysis: zielony typecheck uzgodnionego obszaru, testy, code-size ratchet i jawne limity zrozumiałe dla każdego kolejnego ticketu. Bieżący błąd typecheck w kanonizacji geometrii zostaje naprawiony bez zmiany zachowania.

**Blocked by:** None — can start immediately.

**Status:** completed

- [x] Uzgodnione polecenie typecheck obejmuje Domain Analysis i cienką kompozycję Qt, przechodzi w bieżącym checkoutcie i jest zapisane w quality gates.
- [x] Testy istniejącego zachowania pozostają zielone, a naprawa typecheck nie zmienia runtime result ani fingerprintów.
- [x] Quality gates podają: preferowane 250–500 i twarde 800 linii na plik produkcyjny, preferowane 40 i twarde 80 linii na funkcję/metodę, maksymalnie 30 funkcji/metod, 10 klas, 1000 linii i 40 testów w pliku testowym.
- [x] Code-size guard przechodzi; nie powstaje ani nie rośnie wyjątek ratchetu, a żaden istniejący plik ponad limitem nie zwiększa chronionej metryki.
- [x] Zmiana przechodzi targeted tests, pełne `tests/moltrack` z Qt offscreen i code review oraz jest zapisana w jednym celowym commicie.
