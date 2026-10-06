# Rozwój NanoTrack

Polecenia wykonuj w PowerShell z katalogu głównego repozytorium
`NEtCAT_NaParA`, zawierającego `nanotrack/`, `tests/` i `scripts/`.

## Uruchomienie aplikacji

NanoTrack używa środowiska Conda `netcat`. W terminalu z dostępną Condą:

```powershell
conda run --no-capture-output -n netcat python -m nanotrack.main
```

W terminalu z aktywnym środowiskiem wystarczy:

```powershell
conda activate netcat
python -m nanotrack.main
```

Punktem wejścia jest [nanotrack/main.py](../../nanotrack/main.py), który uruchamia
[app.py](../../nanotrack/app.py). Aplikacja tworzy okno PyQt6 i ustawia sposób
wyświetlania obrazów w pyqtgraph.

Jeżeli `conda` nie jest w `PATH`, użyj pełnej ścieżki do instalacji, np. dla
Anacondy w katalogu użytkownika:

```powershell
& "$env:USERPROFILE\anaconda3\Scripts\conda.exe" run --no-capture-output -n netcat python -m nanotrack.main
```

Do pracy z widocznym GUI używaj domyślnej platformy Qt. Jeśli w tym terminalu
ustawiono wcześniej `offscreen` do testów, przed uruchomieniem aplikacji usuń
to ustawienie z bieżącego procesu:

```powershell
Remove-Item Env:QT_QPA_PLATFORM -ErrorAction SilentlyContinue
```

Wymagane biblioteki sprawdza [kontrola jakości](QUALITY_GATES.md).
Osobne modele ML i ich środowiska zależą od wybranego backendu. Przy pracy
nad nimi sprawdź konfigurację w [mask_trackers/config.py](../../nanotrack/mask_trackers/config.py),
[sam2/backend.py](../../nanotrack/sam2/backend.py),
[trackers/backend.py](../../nanotrack/trackers/backend.py) lub
[yolo/discovery.py](../../nanotrack/yolo/discovery.py). Część domyślnych ścieżek
odnosi się do lokalnych instalacji autora, więc wymaga sprawdzenia na danej maszynie.

## Pełna kontrola zgodna z CI

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\check_nanotrack.ps1
```

Launcher sam szuka Condy i uruchamia kontrolę w `netcat`. Sprawdza zależności
oraz Qt, a następnie testy NanoTrack i viewera MolTrack. Nie wymaga aktywowania
środowiska w terminalu. `ExecutionPolicy Bypass` dotyczy tylko tego procesu.
Komunikację PowerShell–Python obsługuje wspólny [launcher UTF-8](../PYTHON_CHECKS.md).

[QUALITY_GATES.md](QUALITY_GATES.md) jest źródłem szczegółów: wymagane zależności,
dozwolone pominięcia, opcjonalne próby modeli, wybór instalacji Condy,
parametry raportów i wymagania runnera. Raport bieżącego uruchomienia trafia
do katalogu wypisanego przez skrypt w `.scratch/nanotrack-quality/`.

Konfiguracja CI: [nanotrack-quality.yml](../../.github/workflows/nanotrack-quality.yml).

## Szybkie testy podczas pracy

Wybrany plik lub test można uruchomić przez wspólny launcher w `netcat`, np.:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/run_python_utf8.ps1 -Module pytest tests/nanotrack/test_ecc_translation_backend.py -q -p no:cacheprovider
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/run_python_utf8.ps1 -Module pytest tests/nanotrack/test_session_store.py -q -p no:cacheprovider
```

Do wyboru pojedynczego testu dopisz `::NazwaKlasy::nazwa_testu` do ścieżki pliku.
`-p no:cacheprovider` pozwala pracować także przy niedostępnym lokalnym
`.pytest_cache`. Pełna kontrola przed przekazaniem zmiany pozostaje komendą
z poprzedniej sekcji: zwykły pytest może uznać pominięty test za sukces,
a wspólny skrypt sprawdza również przyczynę pominięcia.

## Zmiana wspólnego viewera

[ViewerWidget](../../napara/gui/widgets/viewer_widget.py) jest używany przez
[NanoTrack](../../nanotrack/ui/widgets/sequence_viewer_widget.py),
[podglądy par klatek](../../nanotrack/ui/widgets/frame_preview_widget.py),
[MolTrack](../../moltrack/ui/widgets/stm_series_viewer.py) oraz
[NaParA](../../napara/gui/main_window.py).

Szybka kontrola obu zestawów testów:

```powershell
$env:QT_QPA_PLATFORM = 'offscreen'
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/run_python_utf8.ps1 -Module pytest tests/nanotrack/test_viewer_widget.py tests/moltrack/test_stm_series_viewer.py -q -p no:cacheprovider
```

Następnie uruchom pełną kontrolę NanoTrack. Przy zmianie wyglądu lub interakcji
sprawdź także zmienione zachowanie w aplikacjach korzystających z viewera;
testy NanoTrack/MolTrack nie pokrywają całego interfejsu NaParA.

## Lokalna specyfikacja i kontrola planu

Przy wdrażaniu rejestracji, wyglądu, Play i eksportu punktem odniesienia jest
[zaakceptowana specyfikacja](../../.scratch/nanotrack-registration-export/spec.md).
[Mapa](../../.scratch/nanotrack-registration-export/map.md) prowadzi do decyzji,
a specyfikacja opisuje etapy i kryteria odbioru. Dostępność tych plików jest
lokalna: `.scratch` pozostaje ignorowany przez Git. Brak planu w świeżym
checkoutcie nie oznacza błędu instalacji aplikacji.

Jeśli plan jest dostępny, sprawdź jego strukturę:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/run_python_utf8.ps1 scripts/check_wayfinder_plan.py .scratch/nanotrack-registration-export
```

[Opis walidatora](../WAYFINDER_PLANS.md) wyjaśnia reguły, zakres kontroli
odnośników i kody zakończenia. Testy samego walidatora, również bez lokalnego
planu:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/run_python_utf8.ps1 -Module unittest discover -s tests/wayfinder -p "test_*.py" -v
```

Walidacja struktury planu, testy aplikacji i odbiór opisanych w specyfikacji
funkcji są osobnymi sprawdzeniami. Kryteria dotyczące rzeczywistych filmów
i programów odbierających eksport wykonuj według specyfikacji.
