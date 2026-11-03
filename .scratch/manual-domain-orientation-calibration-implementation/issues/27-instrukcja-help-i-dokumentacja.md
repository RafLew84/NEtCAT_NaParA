# 27 — Wydać instrukcję i dokumentację zintegrowaną z Help

**What to build:** Operator otwiera z menu Help wersjonowaną instrukcję zgodną z produkcyjnym Spatial Command Center. Istniejące drafty zostają zsynchronizowane z wdrożonymi nazwami, schematami i zachowaniem, otrzymują finalne screenshoty oraz potwierdzony clean-session walkthrough TTMAPP.

**Blocked by:** 26 — Przeprowadzić hard cutover i pełną akceptację TTMAPP.

**Status:** completed

- [x] Quick start przechodzi krok po kroku na czystej sesji i rzeczywistym przykładzie TTMAPP, a wynik, data i wersja aplikacji są zapisane.
- [x] Screenshoty pochodzą wyłącznie z produkcyjnego wariantu C, mają alt text i podpisy oraz nie pokazują kontrolek lub danych spoza wydania.
- [x] User guide, technical reference, formats, migration/troubleshooting, CONTEXT i indeks podają wdrożone wersje; znika suffix draft dopiero po pełnej walidacji.
- [x] Test Qt potwierdza właściwy link Help; kontrola lokalnych linków i wersji, typecheck, targeted tests, pełne `tests/moltrack`, code-size guard i code review przechodzą; powstaje jeden commit.
- [x] Dokumentacja utrwala limity 250–500 preferred, 800 hard, 30 definicji, 10 klas i 80 linii na funkcję oraz zasadę braku nowych lub rosnących wyjątków ratchetu.
