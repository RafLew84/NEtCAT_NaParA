# RoMa i LightGlue: odczyt pamięci na Windows 64-bit — 2026-11-03

## Objaw i przyczyna

Po rozpoczęciu dopasowania RoMa v2 zwracała:
`ctypes.ArgumentError: argument 1: OverflowError: int too long to convert`.
Traceback wskazywał `_peak_rss_mib` w `stmviewer/roma_worker.py`,
wywołanie `GetProcessMemoryInfo`. LightGlue używa tej samej funkcji.

`GetCurrentProcess` zwraca uchwyt wielkości wskaźnika, w tym przypadku
pseudouchwyt `(HANDLE)-1`. Funkcja odczytu pamięci nie miała określonych
typów argumentów dla ctypes. Próba przekazania 64-bitowej wartości jako
domyślnego C int powodowała przepełnienie. W RoMa odczyt wykonywany jest
po dopasowaniu i próbkowaniu, przed przekazaniem wyniku do aplikacji.

Poprawka deklaruje sygnatury obu funkcji Windows: HANDLE, wskaźnik do
struktury liczników, DWORD oraz wynik BOOL. Zachowuje liczniki SIZE_T
i dotychczasowy wynik 0 MiB, jeśli API zgłosi niepowodzenie.
Nie zmienia obliczania przesunięć, modeli, wag ani konfiguracji CUDA.

## Aktualizacja istniejącej instalacji

Mała paczka: `data/distribution/STMViewer-2026-11-03-windows-memory-fix.zip`.

1. Zamknij STM Viewer.
2. Rozpakuj ZIP. Z jego folderu `stmviewer` skopiuj `roma_worker.py`
   do folderu `stmviewer` swojej instalacji, zastępując dotychczasowy plik.
   Jest to folder z kodem programu, a nie folder środowiska conda lub modeli.
3. Uruchom program ponownie i wykonaj dopasowanie RoMa na używanym filmie.

Dotyczy także wcześniejszych pełnych paczek `STMViewer-2026-11-03.zip`
i `STMViewer-2026-11-03-auto-models.zip`; nie przebudowano ich w miejscu.
Wagi i zainstalowane biblioteki pozostają te same.

Opcjonalna szybka kontrola z katalogu programu, w aktywnym środowisku Python:

~~~text
python -c "from stmviewer.roma_worker import _peak_rss_mib; print(_peak_rss_mib())"
~~~

Oczekiwany wynik to liczba MiB bez tracebacku. Dodatkowo można sprawdzić
LightGlue; odczyt pamięci jest współdzielony przez obie metody.

## Weryfikacja

Przed zmianą przygotowano `tests/stmviewer/test_worker_memory.py`.
Windows CPython 3.12.10 amd64 uruchomiony przez odizolowane Wine:
test rzeczywistego wywołania systemowego odtworzył dokładnie zgłoszony błąd
(3 testy, 1 błąd). Po zmianie te same 3 testy przeszły. Pierwotna próba
samej funkcji również przeszła, zwracając 42,390625 MiB.

Test sprawdza rzeczywiste API na platformie, na której jest uruchamiany.
Dwa dodatkowe przypadki z atrapą granicy API sprawdzają niepowodzenie
odczytu oraz licznik 6 GiB bez obcięcia do 32 bitów.
Ścisłe odtworzenie i traceback wystarczyły do wskazania przyczyny;
pominięto szersze poszukiwanie alternatywnych hipotez.

Na Linux, w środowisku netcat:

- 38 testów pamięci, procesu RoMa/LightGlue, backendów i GUI RoMa: OK
  (GUI automatycznie w trybie Qt offscreen).
- 2 rzeczywiste próby modeli na CPU: RoMa i LightGlue odtworzyły znane
  przesunięcie pary zgodnie z istniejącymi tolerancjami testów.
- Mypy: 106 modułów bez błędów; Ruff F i `git diff --check`: OK.
- Zmieniony moduł aplikacji: 222 linie; nowy test: 37 linii.

Test na Windows bez dodatkowych bibliotek, z katalogu programu:

~~~text
python -m unittest discover -s tests/stmviewer -p test_worker_memory.py -v
~~~

Logi lokalne: `/tmp/stmviewer-win-memory/tests-red.log`, `tests-green.log`,
`red-probe.log`, `green-probe.log` oraz `/tmp/stmviewer-memory-tests.log`
i `/tmp/stmviewer-memory-real-models.log`.

Nie wykonano pełnej rejestracji w GUI na fizycznym Windows 11 z NVIDIA.
To pozostaje próbą użytkownika po podmianie pliku; Wine potwierdza poprawkę
interfejsu Windows API, nie działanie całego zestawu CUDA na jego komputerze.

## Źródła kontraktu API

- [Microsoft: GetProcessMemoryInfo — HANDLE, wskaźnik, DWORD, wynik BOOL](https://learn.microsoft.com/en-us/windows/win32/api/psapi/nf-psapi-getprocessmemoryinfo).
- [Microsoft: GetCurrentProcess — pseudouchwyt procesu](https://learn.microsoft.com/en-us/windows/win32/api/processthreadsapi/nf-processthreadsapi-getcurrentprocess).
- [Python: deklaracje typów argumentów ctypes](https://docs.python.org/3/library/ctypes.html#specifying-the-required-argument-types-function-prototypes).
