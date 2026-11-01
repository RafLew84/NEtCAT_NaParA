# REG-08d — karta testów i przeglądu

Data: 2026-11-01. Gałąź `viewer/registration-difficult-movies`.
Status: **ready-for-review**; decyzja użytkownika i ręczna ocena jakości oczekują.
Baza: `38d2cb6612b7daf5bf731f049f030bd7aa92c8fd`.
Kod: `4c4ffa9`; refaktoryzacja przeglądu: `a811636`.
Specyfikacja: [REG-08d](../issues/08d-long-range-references.md).
[Instrukcja](../long-references-manual.md), [wyniki i ograniczenia](../long-references-results.md).

## Testy automatyczne

TDD RED→GREEN na uzgodnionych publicznych granicach:

- Plan par i nowy graf: zachowanie istniejących pomiarów/odmów, kierunku,
  konfiguracji i kotwicy; poprawne dalekie relacje, brak i spójny alias okresowy.
- Pomiar nowych par z kontrolowanym zewnętrznym matcherem, lokalna odmowa,
  awaria zasobów/anulowanie, identyfikacja źródeł i wersji estymatora.
- Publiczne kontrolki GUI: plan i źródła, obliczenie LS/Hubera, porównanie bazy,
  blokady MainWindow, anulowanie/błąd/zamknięcie, niepełny Huber po odczycie.
- Sesja i eksport: aktywny film/kandydat/poprzednik oddzielnie, ręczne nadpisania,
  odczyt bez modelu i solvera, przenośne źródła, usunięcie klatek, uszkodzone
  dane, stare formaty, MPP NaN oraz finite-fill.

Celowane zestawy przechodziły podczas implementacji: 73 testy silnika,
38 GUI, 110 persistence. Zakresy częściowo się pokrywają — nie sumujemy ich.
Po przeglądzie 74 testy silnika zaliczone, w tym dodatkowy test publicznego API
odmowy bez komunikatu; nie powtarzano pełnego repo.

Pełny zestaw uruchomiony jeden raz na kodzie `4c4ffa9`:

```bash
PYTHONDONTWRITEBYTECODE=1 QT_QPA_PLATFORM=offscreen OPENBLAS_NUM_THREADS=1 PYTHONPATH=.:tests/moltrack:tests/stmviewer python -m pytest --import-mode=importlib -q -p no:cacheprovider -o faulthandler_timeout=120 --junitxml=/tmp/reg08d-full-suite.xml
```

**2450 passed, 14 failed, 16 skipped**, 320,66 s. Viewer: **664 passed,
2 skipped**, bez niepowodzeń. Zbiór wszystkich 14 błędów jest identyczny
z `/tmp/reg08b-full-suite.log` i `/tmp/stmviewer-session-full-suite.log`:
MolTrack/SAM2 oraz NanoTrack (stan okna/sesji i ścieżki checkpointów).
Żaden błąd nie dotyczy zmienionego kodu Viewera. To nie jest zielony wynik
całego repo. Diagnostyczny zrzut stosu po 120 s w teście MolTrack nie przerwał
przebiegu; zestaw zakończył się normalnie. Log i JUnit:
`/tmp/reg08d-full-suite.log`, `/tmp/reg08d-full-suite.xml`.

Mypy strict: cały STM Viewer, 88 modułów, bez błędów. Ruff zmienionych plików i
`git diff --check` czyste. Największy zmieniony plik kodu: 462 linie,
poniżej celu 1000 oraz limitu 1500. Wspólne aplikacje i konfiguracja niezmienione.

## Próby z danymi i GUI

Wzorzec znanego ruchu, alias i brak; rzeczywisty Deep outdoor CUDA na
MOVIE_4 i MOVIE_8; pełny render, sesja, zastosowanie, demonstracyjna korekta,
przywrócenie i mały MPP/AVI. Szczegóły, SHA, numery klatek, czasy i zasoby
w [raporcie](../long-references-results.md). Wszystkie kompletne warianty
przeszły te kontrole. Niekompletny Huber MOVIE_8 pozostał diagnostyką.

Zrzuty Qt offscreen na wzorcu i MOVIE_4 oceniono pod kątem czytelności
kontrolek i źródeł. Nie wykonano ręcznego odbioru przez użytkownika,
Windows 11 ani próby na docelowym GPU 8 GB. Nie ogłaszamy poprawy jakości
rzeczywistych struktur na podstawie zmian XY lub reszt.

## Standards

Niezależny recenzent sprawdził `git diff 38d2cb6...4c4ffa9` względem AGENTS,
instrukcji aplikacji, zasad wykonania/odbioru, słownika i protokołu prób.
Nie znalazł naruszeń udokumentowanych zasad.

Jedna heurystyczna uwaga **P3 — możliwy Duplicated Code**: `extend_graph`
powielał politykę pomiaru pary z `register_graph` (wyjątki, anulowanie,
confidence, `GraphEdge`), z różnym zapisem pustej odmowy. W `a811636`
wydzielono wspólny `measure_graph_pair`, pozostawiając plan/cache/postęp
w dotychczasowych funkcjach. Dodano go do pełnego hasha kodu.
Recenzent niezależnie potwierdził zamknięcie uwagi po ponownym przeglądzie.
**0 otwartych uwag Standards.**

## Spec

Drugi niezależny recenzent: **0 ustaleń**. Potwierdził plan nowych par,
zachowanie bazowych pomiarów i konfiguracji, porównanie z oknem,
tożsamość źródeł, trwałość sesji, rozdzielenie kandydata od aktywnego filmu
oraz ochronę przy błędzie/anulowaniu. Ponownie sprawdził `4c4ffa9..a811636`:
wspólny helper zachowuje kontrakt i jawne przyczyny odmów.
Ręczny odbiór pozostaje osobnym etapem.

Wynik: Standards — jedna zamknięta uwaga P3, 0 otwartych;
Spec — 0 ustaleń. REG-10 nie rozpoczęto; brak publikacji i scalenia.
