# REG-08e — karta wykonania i odbioru

Data: 2026-11-02. Status: **ready-for-review**; ręczny odbiór użytkownika niewykonany.
Gałąź: `viewer/registration-difficult-movies`.
Baza: `a631c79661dff5cb5d7b1bc387edcb22a4a490d6`.
Implementacja: `2626588`; poprawka po przeglądzie: `c0c5abc`.
[Ticket](../issues/08e-multiframe-methods.md),
[instrukcja manualna](../multiframe-methods-manual.md),
[próby i gotowe sesje](../multiframe-methods-results.md).

## Standards

Niezależny przegląd `a631c79…2626588`: **0 naruszeń udokumentowanych zasad**,
jedna uwaga heurystyczna P3 — powielone zbieranie wersji bibliotek i skrótu
kodu w `graph_provenance.py`. W `c0c5abc` wydzielono dwie małe wspólne funkcje,
zachowując listy zależności, kolejność hashowania i format. Recenzent potwierdził
zamknięcie uwagi i brak nowych problemów w delcie. **0 otwartych uwag Standards**.

Lokalny adapter Tile+RANSAC jest uzasadniony zakazem zmian wspólnych modułów
w sesji Viewera. Handoff opisuje potrzebną zmianę integracyjną; matematyka
dopasowania pozostaje taka sama. Testy dotyczą uzgodnionych publicznych granic.

## Spec

Niezależny przegląd `a631c79…2626588`: **0 ustaleń** o brakujących wymaganiach,
błędnym zachowaniu lub rozszerzeniu zakresu. Obejmuje osiem metod,
LS/Huber, brak mieszania pomiarów, walidację wyników i odmów, źródła par,
diagnostyki, prawdziwe etykiety oraz wersje zapisów i ich zgodność.
REG-08d nie został przywrócony. Przegląd delty `2626588..c0c5abc` potwierdził
zachowanie kontraktu. **0 otwartych ustaleń Spec**.

## Testy automatyczne

Środowisko `netcat`, Qt offscreen, `OPENBLAS_NUM_THREADS=1`.

- Pełne repo uruchomiono **raz**, po zamrożeniu implementacji:
  **2452 passed, 14 failed, 16 skipped**, 283,31 s; proces zakończył się kodem 1.
  Wszystkie 14 identyfikatorów błędów dokładnie odpowiada wcześniejszemu
  `/tmp/reg08b-full-suite.log` (MolTrack SAM2 i NanoTrack); **brak nowych błędów**.
- Z tego STM Viewer: **666 passed, 2 skipped**, bez błędów. Dwa pominięte
  testy są opcjonalnymi próbami rzeczywistego LoFTR CPU/CUDA wymagającymi
  ustawienia ścieżki wag w środowisku testów. Osobne próby rzeczywistych
  modeli z lokalnymi wagami na CUDA wykonano i opisano w raporcie danych.
- **37 nowych przypadków REG-08e** obejmuje rzeczywiste CPU bez Torch/Kornia,
  cache według metody, znane XY i nawroty, odmowę versus awarię, nieprawidłowe
  wektory, zachowanie `manual_review`, diagnostykę metod złożonych, wybór
  metody i etykiety GUI, anulowanie, LS/Huber→zastosowanie→sesję/MPP,
  korekty, przywrócenie i zgodność starszych zapisów.
- TDD wykonywano kolejnymi scenariuszami RED→GREEN: wybór backendu CPU,
  nieocenione XY, zapis konfiguracji, UI i odmowy, diagnostyki, błędy natywne
  oraz źródła par po usunięciu początku filmu. Podmiany dotyczyły zewnętrznych
  bibliotek/modeli, plików i okien systemowych; nie prywatnych helperów.
- Po refaktorze przeglądu: **37 passed**, 3,19 s; nie powtarzano pełnego repo.
  Sprawdzono ponownie publiczne pomiary, cache, pochodzenie, GUI i zapis.
- Strict mypy: **84 moduły bez błędów**, również po poprawce. Ruff zmienionego
  kodu i `git diff --check`: bez błędów. 31 plików Python w zmianie,
  największy `ui/pair_dialog.py`: **662 linie**, poniżej celu 1000 i limitu 1500.

Logi: `/tmp/reg08e-full-suite.log`, `/tmp/reg08e-full-suite.xml`,
`/tmp/reg08e-suite-summary.json`, `/tmp/reg08e-review-fix-tests.log`.
Pełne polecenie (w `netcat`):

```bash
PYTHONDONTWRITEBYTECODE=1 QT_QPA_PLATFORM=offscreen OPENBLAS_NUM_THREADS=1 \
PYTHONPATH=.:tests/moltrack:tests/stmviewer python -m pytest --import-mode=importlib -q -p no:cacheprovider -o faulthandler_timeout=120 --junitxml=/tmp/reg08e-full-suite.xml
```

## Dane i GUI

Próby wszystkich ośmiu metod na znanym ruchu dla okien 3/5 oraz pełnych
MOVIE_4 (bez źródłowych klatek 1–2) i MOVIE_8 są opisane osobno.
Powstały gotowe sesje do odbioru; niekompletny Huber nie był stosowany ani
zastępowany automatycznie przez LS. Zapis/odczyt, MPP i AVI sprawdzono.

Qt offscreen i obejrzenie zrzutów 1260×740 potwierdziły czytelność wyboru
metody oraz rozdzielenie kandydata od aktywnego aligned. Zrzuty:
`/tmp/reg08e-ui-{mixed-results,cpu-selection,active-optical-flow,relations}.png`.
To weryfikacja automatyczna i audyt obrazu, **nie odbiór manualny użytkownika**.
Nie deklarujemy poprawy fizycznego dopasowania MOVIE_4/MOVIE_8 na podstawie
samej zbieżności. Windows 11, zewnętrzny VLC i stanowisko docelowe nie były
odebrane ręcznie. REG-10–12 pozostają nierozpoczęte.

Przeglądy: Standards — 0 otwartych uwag po poprawce; Spec — 0 ustaleń.
