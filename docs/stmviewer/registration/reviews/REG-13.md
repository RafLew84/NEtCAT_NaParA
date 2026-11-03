# REG-13: karta sprawdzeń i przeglądu

Data: 2026-11-02. Baza `d86baba`, implementacja `243f83a`,
końcowe testy i harness AVI `811d765`.
Status **done**; odbiór manualny użytkownika potwierdzony 2026-11-02.
Potwierdzenie nastąpiło po diagnozie odmowy 2/32; wyniki testów i ograniczenia
pozostają bez zmian. Odbiór zapisano bez zmian kodu i ponawiania testów.
[Raport modelu i filmów](../lightglue-results.md),
[instrukcja ręczna](../lightglue-manual.md),
[zasoby i środowisko](../lightglue-environment.md).

## TDD i automatyczne sprawdzenia

Testowano uzgodnione granice: obrazy/konfiguracja → korespondencje/XY;
dostępność/zadanie → wynik lub odmowa; para/seria/graf/sesja → zastosowanie
i eksport. Cykle RED/GREEN obejmowały m.in. drugą ścieżkę wag w GUI,
wybór nowej metody dla grafu oraz zachowanie aktywnej i zapamiętanej
konfiguracji przy odczycie sesji. Osobno sprawdzono prawdziwe modele.

- **Końcowy cały STM Viewer: 814 passed, 36 skipped**, 75,17 s.
  `/tmp/stmviewer-reg13-viewer-final.log`. Pominięcia obejmują opcjonalne
  próby modeli; rzeczywisty LightGlue uruchomiono dodatkowo poniżej.
- **Pełne repo: 2595 passed, 19 failed, 50 skipped**, 293,08 s.
  `/tmp/stmviewer-reg13-full.log`. Pięć błędów Viewera dotyczyło starej
  oczekiwanej listy 11 metod. Uzupełniono ją o LightGlue i ponownie wykonano
  cały zestaw Viewera z wynikiem powyżej. Nie uruchamiano ponownie pełnego
  repo po tej zmianie samych oczekiwań testów.
- Pozostałe **14 identyfikatorów błędów występuje już w REG-12**:
  11 MolTrack/SAM2, 2 okna/sesje NanoTrack i 1 normalizacja ścieżki
  checkpointu SAM2 w NanoTrack. Porównanie:
  `/tmp/stmviewer-reg13-baseline-failures.json` z
  `/tmp/stmviewer-reg12-full-final.log`. Nie zmieniano tych modułów;
  pełnego repo nie opisujemy jako zaliczonego.
- Rzeczywiste modele: **4 próby backendu CPU + 1 CUDA**, **1 integracja
  pary/łańcucha/grafu/sesji CPU** oraz **2 Qt offscreen CPU/CUDA** zaliczone.
  Qt obejmuje sprawdzenie modelu, znane XY, zachowanie wybranej klatki,
  anulowanie oraz osobne uszkodzenie obu wag z zachowaniem starego aligned.
  Zrzuty: `/tmp/stmviewer-reg13-gui/lightglue-{cpu,cuda}-aligned.png`.
- Odczyt zapisanej pracy sprawdzono także w osobnym procesie bez importu
  Torch/Kornia/LightGlue/torchvision/OpenCV. Sesja zachowuje obie ścieżki,
  również gdy podczas zapisu wybrano inną metodę.
- Rzeczywisty pilotaż: **54 próby tych samych par STM**, **27 prób wzorców**,
  pełne łańcuchy/grafy obu STM oraz oddzielny kompletny cykl na `cpu.mpp`.
  Ten ostatni obejmuje LS/Hubera, korektę/cofnięcie, sesję, MPP i cztery AVI.
  Szczegóły, odmowy i zasoby w raporcie wyników; VLC nie było używane.
- Mypy: **99 modułów, bez błędów**; wykonywany regularnie.
  `/tmp/stmviewer-reg13-mypy.log`.
- `git diff --check` czyste. Największy zmieniony plik Python:
  `stmviewer/ui/main_window.py`, **987 linii**; wszystkie poniżej 1500.

Polecenia końcowych zestawów:

```bash
PYTHONPATH=.:tests/moltrack:tests/stmviewer QT_QPA_PLATFORM=offscreen \
  OMP_NUM_THREADS=4 MKL_NUM_THREADS=4 OPENBLAS_NUM_THREADS=4 \
  python -m pytest -q --import-mode=importlib --continue-on-collection-errors
PYTHONPATH=.:tests/stmviewer QT_QPA_PLATFORM=offscreen \
  OMP_NUM_THREADS=4 MKL_NUM_THREADS=4 OPENBLAS_NUM_THREADS=4 \
  python -m pytest -q tests/stmviewer
python -m mypy --config-file stmviewer/mypy.ini --cache-dir /tmp/stmviewer-reg13-mypy
```

Dodatkowe testy z lokalnymi wagami:

```bash
STMVIEWER_TEST_LIGHTGLUE_ROOT=/home/rlew/.cache/stmviewer/lightglue \
  PYTHONPATH=.:tests/stmviewer python -m pytest -q \
  tests/stmviewer/test_lightglue_real_backend.py
STMVIEWER_TEST_LIGHTGLUE=1 PYTHONPATH=.:tests/stmviewer \
  python -m pytest -q tests/stmviewer/test_lightglue_real_integration.py
STMVIEWER_TEST_LIGHTGLUE=1 QT_QPA_PLATFORM=offscreen PYTHONPATH=.:tests/stmviewer \
  python -m pytest -q tests/stmviewer/test_lightglue_real_gui.py
```

CPU/CUDA uruchomiono w `netcat`; GPU wymaga dostępu procesu do sterownika.
Próby CUDA wykonano poza izolacją odcinającą urządzenie, na lokalnej RTX 5090.

## Standards

Niezależny przegląd `d86baba…243f83a`: **0 naruszeń udokumentowanych
zasad, 0 problemów utrzymania wymagających poprawy**. Zmiany pozostają
w katalogach Viewera; modele są lokalne, import odroczony, wykonanie
izolowane w procesie. Ponowne wykorzystanie transportu RoMa zachowuje jego
domyślne zachowanie; nazwa modelu i prefiks plików są osobnymi parametrami.

Dodatkowy odczytowy przegląd końcowych trzech plików testów/harnessu
zapisanych w `811d765`: **0 uwag**. Eksport korzysta z publicznych API;
oczekiwania list metod rozszerzono bez osłabiania wcześniejszych asercji.

## Spec

Niezależny przegląd `d86baba…243f83a`: **0 uwag** o brakującej lub błędnej
implementacji ani rozszerzeniu zakresu. Lokalna kontrola dwóch checkpointów,
natywne współrzędne, konsensus v2, para/film/graf, ostrzeżenia i odmowy,
anulowanie, wersjonowane sesje/MPP oraz istniejące operacje zastosowania,
korekty i eksportu odpowiadają REG-13.

Dodatkowy przegląd diffu testów/harnessu w `811d765`: **0 uwag**.
AVI jest eksportowane z ponownie odczytanych sesji po korekcie LS/Hubera;
`save_avi` faktycznie weryfikuje dekodowanie, parametry i piksele FFV1.
Oba przeglądy były oddzielne i tylko do odczytu.

## Odbiór ręczny i ograniczenia

**Potwierdzony przez użytkownika 2026-11-02**, po diagnozie odmowy 2/32.
REG-13 zamknięto jako `done`, REG-14 odblokowano. Automatyczne Qt offscreen
i oględziny tablic przez agenta pozostają osobnymi sprawdzeniami.

LightGlue dał wynik dla **12/18 par STM**. Pełne grafy MOVIE_4/MOVIE_8 są
rozłączne, więc nie powstał z nich kompletny aligned. Na kompletnym małym
wzorcu sprawdzono cały cykl; nie przypisujemy tego wyniku odmówionym filmom.
Brak niezależnego prawdziwego dryfu na STM, a znane filmy są zbiorem
rozwojowym. Wszystkie trzy porównane metody podążyły za silnym nieruchomym
artefaktem w jednym wzorcu. Nie stwierdzono przewagi jakościowej LightGlue.

Potwierdzenie użytkownika nie określa osobno Windows 11, VLC ani stanowiska
z kartą 8 GB VRAM; nie dopisujemy tych prób jako zaliczonych.
Lokalne CPU/RTX 5090 nie zastępują tych prób. Brak zmian wspólnych,
instalowania pakietów, scalania i publikowania gałęzi.
