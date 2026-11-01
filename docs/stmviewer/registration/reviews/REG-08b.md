# REG-08b — karta wykonania i odbioru

Data: 2026-11-01. Status: **ready-for-review**; ręczny odbiór oczekuje.
Baza przeglądu: `3f6fd5a32105b79a1143551fa1541c5c97ab5d66`.
Kod: `2802837`; poprawki po przeglądzie: `417c107`.
Gałąź: `viewer/registration-difficult-movies`.

[Ticket](../issues/08b-robust-graph.md), [instrukcja manualna](../robust-graph-manual.md),
[wyniki obliczeń i gotowe sesje](../robust-graph-results.md).

## Standards

Niezależny przegląd objął wszystkie 17 plików kodu i testów w `3f6fd5a…2802837`.
Wskazano jedno naruszenie P3 zasad TDD: test odczytu podmieniał własny solver.
Usunięto tę podmianę; sprawdzenie nadal blokuje biblioteki modelu, SciPy
oraz funkcje solvera NumPy na granicy zewnętrznej. Druga, heurystyczna uwaga
czytelności dotyczyła 16 pozycyjnych argumentów diagnostyki. Trzy konstruktory
zastąpiono wywołaniami z nazwanymi argumentami, bez zmiany wartości.

Recenzent potwierdził zamknięcie obu uwag w `417c107` i brak nowych ustaleń.
**0 otwartych ustaleń Standards.** Zakres aplikacji, publiczne granice testów,
podział odpowiedzialności i limity plików zachowane.

## Spec

Niezależny przegląd `3f6fd5a…2802837`: **0 ustaleń**. Sprawdzono blokowy
Huber 2D, identyczne pomiary i braki, kotwicę, warunki zbieżności i odmowy,
wersjonowanie sesji bez ponownej optymalizacji, podgląd na żądanie i wspólny
widok, zachowanie aktywnego aligned, korekt i eksportu oraz anulowanie.
Dodatkowy jawny limit iteracji pozostaje w zakresie kontroli solvera.
Odmowa kompletnego wyniku MOVIE_4/3 odpowiada kontraktowi numerycznemu.

Przegląd delty `2802837..417c107` potwierdził zachowanie kontraktu i brak
nowych ustaleń. **0 otwartych ustaleń Spec.** Ręczny odbiór pozostaje osobnym,
niewykonanym sprawdzeniem, nie zastępuje go przegląd kodu.

## Testy automatyczne

Środowisko: lokalny `netcat`, Qt offscreen, `OPENBLAS_NUM_THREADS=1`.

- Pełny zestaw repo uruchomiono raz na kodzie `2802837`:
  **2381 passed, 14 failed, 16 skipped**, 283,89 s.
  W tym STM Viewer: **595 passed, 0 failed, 2 skipped**.
  Log `/tmp/reg08b-full-suite.log`, JUnit `/tmp/reg08b-full-suite.xml`.
- Wszystkie 14 błędów dokładnie odpowiada wcześniejszemu zestawowi z
  `/tmp/stmviewer-session-full-suite.log`: 11 MolTrack/SAM2 i 3 NanoTrack.
  Porównano pełne identyfikatory przypadków; brak nowych błędów.
  Nie zmieniano wspólnych aplikacji w ramach tej sesji.
- Nowe testy REG-08b: **45 przypadków**, w pełnym zestawie zaliczone.
  Obejmują analityczne optimum 2D różne od komponentowego Hubera, zwroty
  ruchu, pojedynczy błąd, most/drzewo/rozłączenie, spójny alias i złą większość,
  identyfikację pomiarów, kontrolę numeryczną, błędy zasobów i anulowanie.
- Sesje: wiele progów, ścisła walidacja przypisania pomiarów i diagnostyk,
  zapis nieukończonej próby bez pełnych pozycji, zgodność starych sesji,
  odczyt bez modelu/SciPy i ponownego solvera, symulowany transfer ścieżek
  Linux–Windows. To nie zastępuje uruchomienia aplikacji na Windows.
- GUI: obliczenia bez wag, zachowanie poprzednich wariantów, wagi i różnice XY,
  limit iteracji, anulowanie/zamknięcie/błędy, wspólny kadr i skala źródłowych
  pikseli po rozszerzeniu obszaru, blokowanie działań głównego okna oraz
  zapis/odczyt sesji i MPP z niezmienionym aktywnym ręcznym dopasowaniem.
- Po poprawkach `417c107` powtórzono zakres dotknięty zmianą:
  **28 testów solvera i 7 testów sesji — wszystkie zaliczone**.
  Pełnego zestawu nie powtarzano. Poprawki zmieniły nazwy argumentów oraz
  usunęły wewnętrzną podmianę testową, bez zmiany obliczeń i formatu sesji.
- Końcowy strict mypy: **73 moduły bez błędów**. Ruff zmienionego kodu
  i `git diff --check`: bez błędów. Największy zmieniony plik:
  `ui/graph_dialog.py`, **382 linie**, poniżej celu 1000 i limitu 1500.
- Kolejne publiczne przypadki rozwijano RED→GREEN. Kontrolowane awarie
  dotyczą zewnętrznych bibliotek i plików; solver, serializacja i akcje
  aplikacji działają rzeczywiście. Sprawdzono również brak SciPy podczas
  zadania Qt: komunikat błędu, zachowanie wyniku i ponowna dostępność akcji.

Polecenie pełnego zestawu:

```bash
PYTHONDONTWRITEBYTECODE=1 QT_QPA_PLATFORM=offscreen OPENBLAS_NUM_THREADS=1 \
PYTHONPATH=.:tests/moltrack:tests/stmviewer python -m pytest --import-mode=importlib \
-q -p no:cacheprovider -o faulthandler_timeout=120 --junitxml=/tmp/reg08b-full-suite.xml
```

## Materiały i odbiór manualny

30 rozwiązań rozwojowych służyło doborowi domyślnych parametrów. Osobne nowe
sceny odbiorcze obejmują pojedynczy błąd i ograniczenia identyfikowalności.
Dla MOVIE_4/MOVIE_8 wczytano zachowane pomiary REG-08a, bez Deep i importów
modelu, obliczono oba progi, zapisano/odczytano sesje i wyrenderowano pełne
filmy dostępnych wariantów. Szczegóły w raporcie; odmowy zbieżności również
zachowano. Nie wnioskowano o jakości STM ze spadku kosztu.

Zrzuty Qt offscreen obejrzano pod kątem układu, nazw i dostępności kontrolek
(`/tmp/reg08b-window-{top,huber,table}.png`). To automatyczne sprawdzenie
prezentacji, nie ręczny odbiór programu ani wizualnej poprawy filmów.

**Ręczny odbiór użytkownika: niewykonany.** Windows 11 i docelowe stanowisko
nie zostały sprawdzone. REG-08c pozostaje nierozpoczęty; oglądanie Hubera
nadal nie zmienia aktywnego filmu ani eksportowanych MPP/AVI.

Przeglądy: Standards — 0 otwartych ustaleń po poprawkach; Spec — 0 ustaleń.
