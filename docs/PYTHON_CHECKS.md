# Uruchamianie kontroli Python z UTF-8

W PowerShell używaj [scripts/run_python_utf8.ps1](../scripts/run_python_utf8.ps1).
Domyślnie uruchamia Pythona w Condzie `netcat`. Wszystkie ścieżki względne
interpretuje od katalogu głównego repozytorium.

## Plik kontroli

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/run_python_utf8.ps1 scripts/check_wayfinder_plan.py .scratch/nanotrack-registration-export
```

Opcje launchera podaje się **przed** plikiem `.py` albo `-Module nazwa`.
Wszystko po celu jest argumentem uruchamianego programu, również `-p`, `-s`
i `--report-dir`. Opcjonalny separator `--` bezpośrednio po celu jest pomijany.
Ścieżki ze spacjami ujmuj w cudzysłowy.

Do wyboru interpretera służą:

- `-PythonExe <ścieżka lub nazwa polecenia>` — bezpośrednio wskazany Python;
- `-CondaExe <ścieżka>` — wskazana Conda;
- `-CondaEnv <nazwa>` — środowisko Condy inne niż domyślne `netcat`.

Przykład bez Condy, po aktywowaniu wybranego środowiska:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/run_python_utf8.ps1 -PythonExe python scripts/check_wayfinder_plan.py tests/wayfinder/fixtures/closed
```

Bez `-PythonExe` launcher szuka Condy przez `CONDA_EXE`, `PATH` oraz standardowe
instalacje Anaconda/Miniconda/Miniforge w katalogu użytkownika. Nie instaluje
pakietów ani nie zmienia konfiguracji środowiska.

## Moduły testowe

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/run_python_utf8.ps1 -Module unittest discover -s tests/wayfinder -p "test_*.py" -v
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/run_python_utf8.ps1 -Module pytest tests/nanotrack/test_ecc_translation_backend.py -q -p no:cacheprovider
```

Pełna kontrola NanoTrack korzysta z tego samego launchera; jej komenda pozostaje:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/check_nanotrack.ps1
```

## Kodowanie i kod zakończenia

Launcher ustawia `$OutputEncoding`, `[Console]::InputEncoding` i
`[Console]::OutputEncoding` na UTF-8 bez BOM. Dla procesu Pythona ustawia
`PYTHONUTF8=1`, `PYTHONIOENCODING=utf-8` i przekazuje `-X utf8`.
Po zakończeniu przywraca wcześniejsze ustawienia środowiska, konsoli i katalog
roboczy. Parametr `ExecutionPolicy Bypass` działa tylko w uruchomionym procesie.

Kod Pythona zapisuj w pliku `.py` w UTF-8 i przekazuj jego ścieżkę. Launcher
przyjmuje pliki lub nazwy modułów; nie wykonuje kodu przez `python -c` ani
`python -`. Sam bootstrap `.ps1` używa ASCII, dzięki czemu Windows PowerShell
5.1 poprawnie odczytuje go również bez BOM. Czytając lub zapisując pliki tekstowe
cmdletami PowerShell, podawaj `-Encoding utf8`; kodowanie plików przez `>`
w zewnętrznym terminalu nie jest ustawieniem kontrolowanym przez launcher.

Skrypt zwraca kod zakończenia uruchomionego procesu, także przy komunikatach
na stderr. Błąd przygotowania uruchomienia, np. brak skryptu lub interpretera,
daje kod 1. W nadrzędnym skrypcie PowerShell zachowaj ten wynik:

```powershell
& ./scripts/run_python_utf8.ps1 scripts/check_wayfinder_plan.py tests/wayfinder/fixtures/closed
exit $LASTEXITCODE
```

Zasady kodowania opisują dokumentacje
[PowerShell](https://learn.microsoft.com/en-us/powershell/module/microsoft.powershell.core/about/about_character_encoding)
i [Pythona](https://docs.python.org/3.12/using/cmdline.html#envvar-PYTHONUTF8).

## Testy launchera

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/run_python_utf8.ps1 -Module unittest discover -s tests/tooling -p "test_*.py" -v
```

Testy wykonują zapisane w repo skrypty z polskimi znakami w treści, nazwie pliku,
argumentach, stdout i stderr. Sprawdzają tryb UTF-8, zachowanie kodu 37,
przekazywanie opcji modułów oraz przywracanie wcześniejszych ustawień przy
wywołaniu z innego skryptu PowerShell. Wymagają PowerShell; osobny
[workflow Windows](../.github/workflows/python-tooling.yml) wykonuje je na runnerze
GitHub bez zależności NanoTrack. Testy walidatora planów na Linuxie używają
bezpośrednio Pythona z `-X utf8` i tymi samymi zmiennymi kodowania.
