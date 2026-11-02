# REG-12: karta sprawdzeń i przeglądu

Data: 2026-11-02. Baza `1c30ef5`, implementacja `b4d9441`.
`git diff 1c30ef5...b4d9441`; `git log 1c30ef5..b4d9441 --oneline`.
Status **ready-for-review**; ręczny odbiór niewykonany.
[Wyniki modelu i filmów](../matchanything-results.md), [ręczna próba](../matchanything-manual.md).

## TDD i automatyczne sprawdzenia

Uzgodnione granice: konfiguracja/korespondencje→XY;
dostępność/zadanie→wynik lub odmowa; para/seria/graf/sesja→zastosowanie/eksport.
Testy powstawały w kolejnych cyklach RED/GREEN. Osobno rzeczywisty model,
sprawdzenia przygotowania z kodem autorów oraz GUI Qt offscreen.
Przykładowe logi: `/tmp/reg12-gui-red.log`,
`/tmp/reg12-preprocessing-reference-red.log`,
`/tmp/reg12-author-reference-green.log`, `/tmp/reg12-author-gui.log`.

- Pełne repo: **2570 passed, 14 failed, 42 skipped**, 294,30 s.
  `/tmp/stmviewer-reg12-full-final.log`. Wszystkie 14 identyfikatorów błędów
  występują w poprzednim `/tmp/stmviewer-reg11-full-importlib.log`;
  nowe identyfikatory: **0**, błędy STM Viewer: **0**.
  Porównanie: `/tmp/reg12-baseline-failures.json`.
- Pozostające problemy: 11 MolTrack/SAM2, 2 okna/sesje NanoTrack,
  1 normalizacja ścieżki checkpointu SAM2 w NanoTrack. Nie zmieniano tych
  modułów ani nie ogłaszamy pełnego repo zielonym.
- Rzeczywiste testy dodatkowe: **9 CPU/CUDA**, **3 referencyjne preprocessing**,
  **2 Qt offscreen** zaliczone. Nie utożsamiamy ich z ręczną oceną jakości.
- Sprawdzone całe oba filmy, sesje i małe eksporty, z ograniczeniami
  opisanymi w raporcie wyników. Dopasowania wzorców i rzeczywistego STM
  nie są idealne; ich błędy/ostrzeżenia nie są ukryte.
- Mypy: **96 modułów, bez błędów**; regularnie uruchamiany podczas zmian.
  `git diff --check` czyste. Największy zmieniony plik Python:
  `stmviewer/ui/main_window.py`, **982 linie**; wszystkie poniżej 1500.

Pełny zestaw uruchomiono końcowo poleceniem:

```bash
PYTHONPATH=.:tests/moltrack:tests/stmviewer QT_QPA_PLATFORM=offscreen \
  OMP_NUM_THREADS=4 MKL_NUM_THREADS=4 OPENBLAS_NUM_THREADS=4 \
  python -m pytest -q --import-mode=importlib --continue-on-collection-errors
```

Wcześniejszy przebieg przerwano po zmianie roboczej konfiguracji modelu;
nie jest zaliczany jako pełny test. Poprawna podstawa końcowa to log `full-final`.

```bash
python -m mypy --config-file stmviewer/mypy.ini --cache-dir /tmp/stmviewer-reg12-mypy
STMVIEWER_TEST_MATCHANYTHING_ROOT=/home/rlew/.cache/stmviewer/matchanything \
  PYTHONPATH=.:tests/stmviewer python -m pytest -q \
  tests/stmviewer/test_matchanything_real_integration.py \
  tests/stmviewer/test_matchanything_preprocessing_reference.py
STMVIEWER_TEST_MATCHANYTHING=1 QT_QPA_PLATFORM=offscreen \
  PYTHONPATH=.:tests/stmviewer python -m pytest -q tests/stmviewer/test_matchanything_real_gui.py
```

## Standards

Przegląd `1c30ef5…b4d9441`: **0 naruszeń udokumentowanych zasad,
0 istotnych problemów utrzymania kodu**. Zmiany pozostają w zakresie
STM Viewer. Wagi i kod pozostają lokalne, import modelu jest odroczony.
Podział przygotowania obrazów, runtime, konsensusu i metadanych jest czytelny.
Wspólny fragment konfiguracji grafu wydzielono zamiast kopiować po raz trzeci.

## Spec

Przegląd `1c30ef5…b4d9441`: **0 uwag** dotyczących brakującej/błędnej
implementacji lub rozszerzenia zakresu. Preset autorów, przeliczenie
współrzędnych, wspólny konsensus/graf, obsługa błędów i anulowania oraz
wersjonowana tożsamość sesji/MPP odpowiadają REG-12. Odtworzenie wyników
nie wymaga uruchomienia modelu. Niewykonany ręczny odbiór i próby sprzętu
nie pozwalają oznaczyć ticketu jako `done`.

Oba przeglądy były niezależne i wyłącznie odczytowe. Łącznie: Standards 0,
Spec 0; bez wymaganych poprawek kodu po przeglądzie.

## Do odbioru ręcznego

Rzeczywista aplikacja, oba pełne filmy, ocena struktur i resztkowego tearingu;
VLC dla MJPG/FFV1; Windows 11; stanowisko z 16 GB wolnego RAM i NVIDIA
8 GB VRAM. Test lokalnej RTX 5090 nie zastępuje tych prób. Instrukcja i
materiały są przygotowane, decyzja użytkownika pozostaje otwarta.
