# Kontrola jakości NanoTrack

Z katalogu repozytorium, w PowerShell:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\check_nanotrack.ps1
```

To ta sama komenda, której używa `.github/workflows/nanotrack-quality.yml`.
`ExecutionPolicy Bypass` dotyczy tylko tego procesu; pozwala wykonać lokalny
skrypt bez podpisu i nie zmienia zapisanej polityki PowerShell na komputerze.
Uruchamia środowisko Conda `netcat`; nie instaluje ani nie aktualizuje pakietów.
Launcher szuka Condy przez `CONDA_EXE`, `PATH` i standardowe instalacje
Anaconda/Miniconda/Miniforge w katalogu użytkownika. Dla innej lokalizacji:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\check_nanotrack.ps1 -CondaExe 'D:\Conda\Scripts\conda.exe'
```

W aktywnym środowisku można też użyć `python scripts/check_nanotrack.py`.
Każdy błąd kontroli zwraca niezerowy kod zakończenia.

## Co jest sprawdzane

1. Import wymaganych zależności: pytest, NumPy, SciPy, scikit-image,
   PyQt6 (QtCore i QtWidgets), pyqtgraph oraz OpenCV (`cv2` z `findTransformECC`).
   Osobny proces sprawdza także renderowanie widgetu Qt przez platformę `offscreen`.
   Brak biblioteki, błąd DLL, awaria procesu lub przekroczenie 60 sekund przerywają
   kontrolę przed testami.
2. Wszystkie testy w `tests/nanotrack/`.
3. Zawsze testy MolTrack w `tests/moltrack/test_stm_series_viewer.py`, aby sprawdzać
   obu odbiorców wspólnego viewera również przy zmianach po stronie NanoTrack.

CI uruchamia się po zmianach NanoTrack, jego testów, używanych komponentów
`napara/core`, `napara/io`, `napara/gui/widgets` oraz części MolTrack wymaganych
przez testy viewera. Obejmuje też zmiany skryptów kontroli, tego dokumentu i samego
workflow. Można uruchomić workflow ręcznie (`workflow_dispatch`).

Testy loadera i głównego okna korzystają z deterministycznego, tymczasowego MPP
generowanego przez `tests/nanotrack/nanotrack_test_fixtures.py`.
Nie wymagają prywatnego `data/MOVIE_3.MPP`. Ten fixture służy testom obecnego
loadera i GUI; nie jest sprawdzianem jakości rejestracji rzeczywistych filmów
ani zgodności przyszłego eksportera z WSxM.

## Błędy i pominięcia

Raport rozdziela poprawne testy, błędy asercji (`FAIL`), błędy kolekcji/konfiguracji
(`ERROR`) i pominięcia (`SKIP`). Każde nieoczekiwane pominięcie powoduje niepowodzenie
kontroli, nawet gdy sam pytest uznałby uruchomienie za poprawne.
Dotyczy to w szczególności pominięć GUI, pyqtgraph i ECC z powodu brakujących
zależności.

Dozwolone wyjątki są jawnie zapisane w `scripts/check_nanotrack.py`:

- Trzy próby rzeczywistych, zewnętrznych modeli DAM4SAM, SAMURAI i MuGE.
  Standardowa kontrola pomija je niezależnie od lokalnej instalacji modeli.
  Testy logiki i protokołów tych backendów nadal działają.
- Testy GUI wymagające prywatnych modeli YOLO, jeśli modeli nie ma.
- Test przewijania panelu, jeśli dany układ Qt nie powoduje przepełnienia panelu.

Opcjonalne pominięcia są widoczne z nazwą testu i powodem. Rozszerzone sprawdzenie
z rzeczywistymi modelami uruchamia się świadomie:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\check_nanotrack.ps1 -RuntimeSmoke
```

W tym wariancie brak runtime'u dla którejkolwiek z trzech prób modeli jest błędem.
Nie jest to domyślny zakres CI.

## Raporty i przygotowanie runnera

Domyślnie każde uruchomienie tworzy osobny katalog
`.scratch/nanotrack-quality/<identyfikator>/`. `-ReportDir` pozwala wskazać inny
nowy lub pusty katalog. Raporty nie są nadpisywane:

- `environment.json`: interpreter, wersje bibliotek, platforma Qt i błędy preflight;
- `summary.json`: wynik kontroli, oddzielne listy błędów i pominięć;
- `junit.xml`: wyniki testów dla narzędzi obsługujących JUnit.

Jeżeli proces preflight ulegnie awarii, `environment.json` może nie powstać;
`summary.json` nadal zapisuje niepowodzenie. Przy błędzie preflight nie ma JUnit,
ponieważ testy nie zostały uruchomione. CI publikuje dostępne raporty jako artefakt
także po błędzie (retencja 14 dni).

Workflow wymaga zarejestrowanego runnera z etykietami `self-hosted` i `Windows`.
Konto uruchamiające usługę runnera musi mieć dostęp do Condy i środowiska `netcat`.
W razie potrzeby należy ustawić dla niego `CONDA_EXE`. Lokalny poprawny wynik nie
potwierdza rejestracji runnera w GitHub ani dostępu do środowiska z konta usługi.

Weryfikacja lokalna z 2026-10-06: powyższa komenda zakończyła się kodem 0,
z wynikiem **608 passed, 3 skipped, 0 failures/errors** w 52,93 s.
Pominięto wyłącznie trzy zewnętrzne próby modeli opisane powyżej.
Sprawdzone środowisko `netcat`: Python 3.12.12, pytest 8.3.5, NumPy 2.2.5,
SciPy 1.15.2, scikit-image 0.25.2, PyQt6 6.9.1, pyqtgraph 0.13.7,
OpenCV 4.11.0; Qt renderował przez `offscreen`.
Conda nie była dostępna w `PATH`, ale launcher znalazł lokalną instalację Anaconda.
Nie potwierdzono wykonania workflow na zarejestrowanym runnerze GitHub;
wymaga to opublikowania zmian i uruchomienia workflow.
