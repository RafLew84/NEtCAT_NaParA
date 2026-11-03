# 35 — Objąć całe Domain Analysis automatyczną bramką mypy

**What to build:** Jedna powtarzalna bramka `mypy` automatycznie obejmuje wszystkie produkcyjne moduły Domain Analysis, także pliki dodawane w kolejnych ticketach, bez ręcznie utrzymywanej listy ścieżek.

**Blocked by:** 34 — Ponowić pełną akceptację TTMAPP i zsynchronizować Help.

**Status:** completed

- [x] Jedna lokalna i CI-owa komenda automatycznie wykrywa wszystkie produkcyjne pliki Python w uzgodnionym zakresie Domain Analysis i nie wymaga ręcznego dopisywania nowych modułów.
- [x] Istniejące błędy typów w objętym zakresie są naprawione albo jawnie przeniesione do udokumentowanego, nierosnącego baseline'u z właścicielem i uzasadnieniem.
- [x] Test bramki dowodzi, że nowy plik produkcyjny zostaje automatycznie objęty analizą, a kontrolowany błąd typu powoduje niezerowy kod wyjścia.
- [x] `QUALITY_GATES.md`, konfiguracja CI i komendy developerskie wskazują dokładnie tę samą bramkę oraz jednoznacznie opisują jej zakres.
- [x] Nowa bramka, targeted tests, pełne `tests/moltrack`, code-size guard i code review przechodzą; powstaje jeden commit.
