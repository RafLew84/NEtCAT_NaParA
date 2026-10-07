# Kontrola jakości NanoTrack

Z katalogu repozytorium, w PowerShell:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\check_nanotrack.ps1
```

To ta sama komenda, której używa `.github/workflows/nanotrack-quality.yml`.
`ExecutionPolicy Bypass` dotyczy tylko tego procesu; pozwala wykonać lokalny
skrypt bez podpisu i nie zmienia zapisanej polityki PowerShell na komputerze.
Uruchamia środowisko Conda `netcat`; nie instaluje ani nie aktualizuje pakietów.
Wspólny [launcher UTF-8](../PYTHON_CHECKS.md) ustawia komunikację PowerShell–Python,
włącza tryb UTF-8 interpretera i przekazuje kod zakończenia kontroli.
Launcher szuka Condy przez `CONDA_EXE`, `PATH` i standardowe instalacje
Anaconda/Miniconda/Miniforge w katalogu użytkownika. Dla innej lokalizacji:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\check_nanotrack.ps1 -CondaExe 'D:\Conda\Scripts\conda.exe'
```

W aktywnym środowisku można też użyć `python -X utf8 scripts/check_nanotrack.py`.
Każdy błąd kontroli zwraca niezerowy kod zakończenia.

## Co jest sprawdzane

1. Import wymaganych zależności: pytest, NumPy, SciPy, scikit-image,
   PyQt6 (QtCore i QtWidgets), pyqtgraph, mypy oraz OpenCV (`cv2` z `findTransformECC`).
   Osobny proces sprawdza także renderowanie widgetu Qt przez platformę `offscreen`.
   Brak biblioteki, błąd DLL, awaria procesu lub przekroczenie 60 sekund przerywają
   kontrolę przed testami.
2. Mypy całego `nanotrack/`, w tym nowych plików, oraz narzędzi odbioru i kontroli
   typów. Nowa diagnostyka, zwiększenie dopuszczonej liczby błędów lub nieudane
   uruchomienie mypy przerywa kontrolę. Proces mypy ma limit 180 sekund; po jego
   przekroczeniu zostaje zatrzymany, a `types.json` zapisuje status `timeout`.
   Nadrzędny proces kontroli ma dodatkowy bezpiecznik 210 sekund.
3. Wszystkie testy w `tests/nanotrack/`.
4. Zawsze testy MolTrack w `tests/moltrack/test_stm_series_viewer.py`, aby sprawdzać
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

## Zastane błędy typów

Samą kontrolę typów można uruchomić krócej:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/run_python_utf8.ps1 -ScriptPath scripts/check_nanotrack_types.py
```

[Baza diagnostyk](../../scripts/nanotrack_mypy_baseline.json) powstała z kodu
`56ddf61`: 410 istniejących błędów w pełnym NanoTrack. Dawne 243 dotyczyły siedmiu
wybranych modułów; zwiększenie liczby wynika z szerszego zakresu kontroli.
Nowe narzędzia nie mają dopuszczonych błędów. Porównanie uwzględnia ścieżkę,
kod, treść i liczność każdej diagnostyki, a pomija zmieniające się numery wierszy.
Naprawiając błąd, usuń lub zmniejsz odpowiedni wpis bazy. Kontrola odrzuca
pozostawienie nieaktualnego wpisu oraz zwiększenie limitu względem wersji Git.

Lokalnie punktem odniesienia bazy jest `HEAD`. CI ustawia `NANOTRACK_RATCHET_REF`
na bazę PR lub poprzedni commit push i pobiera historię (`fetch-depth: 0`), aby
podniesienie limitu w tym samym commicie co nowy błąd również nie przeszło.
Mechanizm porównania jest współdzielony z kontrolą MolTrack w
`scripts/mypy_baseline.py`.

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
- `types.json`: zakres mypy, zastane/aktualne diagnostyki oraz przyczyna niepowodzenia;
- `summary.json`: wynik kontroli, oddzielne listy błędów i pominięć;
- `junit.xml`: wyniki testów dla narzędzi obsługujących JUnit.

Jeżeli proces preflight ulegnie awarii, `environment.json` może nie powstać;
`summary.json` nadal zapisuje niepowodzenie. Przy błędzie preflight nie ma JUnit,
ponieważ testy nie zostały uruchomione. CI publikuje dostępne raporty jako artefakt
także po błędzie (retencja 14 dni).

Błąd kontroli typów również zatrzymuje wykonanie przed pytest; wtedy
`summary.json` ma status `typecheck_failed`. Rzeczywisty BM3D i widoczne GUI
sprawdza osobny [runner odbioru](ACCEPTANCE.md), gdy wymaga tego zakres zmiany.

Workflow wymaga zarejestrowanego runnera z etykietami `self-hosted` i `Windows`.
Konto uruchamiające usługę runnera musi mieć dostęp do Condy i środowiska `netcat`.
W razie potrzeby należy ustawić dla niego `CONDA_EXE`. Lokalny poprawny wynik nie
potwierdza rejestracji runnera w GitHub ani dostępu do środowiska z konta usługi.

Weryfikacja lokalna z 2026-10-07: powyższa komenda zakończyła się kodem 0,
z wynikiem **608 passed, 3 skipped, 0 failures/errors** w 50,21 s.
Sprawdzono wspólny launcher UTF-8 oraz zapis raportów w ścieżce z polskim
znakiem i spacją.
Pominięto wyłącznie trzy zewnętrzne próby modeli opisane powyżej.
Sprawdzone środowisko `netcat`: Python 3.12.12, pytest 8.3.5, NumPy 2.2.5,
SciPy 1.15.2, scikit-image 0.25.2, PyQt6 6.9.1, pyqtgraph 0.13.7,
OpenCV 4.11.0; Qt renderował przez `offscreen`.
Conda nie była dostępna w `PATH`, ale launcher znalazł lokalną instalację Anaconda.
Nie potwierdzono wykonania workflow na zarejestrowanym runnerze GitHub;
wymaga to opublikowania zmian i uruchomienia workflow.

Weryfikacja po dołączeniu kontroli typów i runnera odbioru, 2026-10-08:
**635 passed, 3 skipped, 0 failures/errors** w 73,51 s (pytest).
Mypy: **410 zastanych diagnostyk, 0 nowych**. Pominięcia pozostają ograniczone
do trzech zewnętrznych prób modeli. Nie uruchamiano zdalnego workflow.
