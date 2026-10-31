# REG-07 — przegląd i wykonane sprawdzenia

Data: 2026-11-01. Baza: `bb06220bdc8f132ebdcef0bc9ac8d045f39ef68e`.
Implementacja: `be0e253`; poprawka po przeglądzie i raport pomiarów: `11441b4`.
Dwa niezależne przeglądy dotyczyły `git diff bb06220...HEAD` po zapisie commita.

## Standards

Nie znaleziono twardych naruszeń udokumentowanych zasad. Zmieniono wyłącznie
aplikację Viewer, jej testy i dokumentację. Największy zmieniony plik kodu
ma 943 linie; wszystkie mieszczą się w celu 1000 linii. Ręczny odbiór pozostaje
jawnie niewykonany.

Jedna uwaga heurystyczna: możliwa **Primitive Obsession / Shotgun Surgery**.
`TrialDocument.payload` jest słownikiem JSON, którego pola są konstruowane
w capture, sprawdzane w walidatorze i odczytywane w GUI. Mypy nie kontroluje
wszystkich zależności między kluczami. Typowany model prób i rekordów mógłby
ułatwić dalszą rozbudowę formatu.

Decyzja wykonawcy: pozostawiono słownik na granicy wersjonowanego dokumentu,
z jawną walidacją schematu, danych liczbowych i powiązania źródeł. Uwaga jest
ograniczeniem utrzymywalności, bez potwierdzonego błędu funkcjonalnego;
rozbudowa modelu typów nie stanowi warunku odbioru REG-07. Nie deklarujemy,
że bieżąca anotacja `dict[str, Any]` zapewnia pełną statyczną kontrolę schematu.

## Spec

Wykryto jedną usterkę **P2**: anulowanie podczas natywnego obliczania pary
mogło odrzucić już zwrócone XY przed zapisaniem diagnostyki. Analogiczna luka
istniała na granicach Deep/ECC i lokalnych fragmentów. Naruszało to wymaganie
zachowania przerwanych prób „z błędem i faktycznie dostępnymi wynikami”.

Poprawiono w `11441b4`: zapis diagnostyki poprzedza obsługę anulowania po
ukończonym obliczeniu. Zachowujemy start Deep, wynik ECC i faktycznie zmierzone
fragmenty. Nieukończony konsensus nie ma końcowego XY ani zaakceptowanych inlierów.
Anulowanie nadal nie publikuje nowego aligned. Test regresji najpierw
odtworzył błąd, następnie przeszedł. Recenzent ponownie sprawdził diff i
uruchomił pięć testów tych przypadków: **5 passed**, ustalenie zamknięte.

Nie znaleziono innych potwierdzonych braków, błędnie zaimplementowanych wymagań
ani rozszerzenia zakresu. Sprawdzono źródła/kolejność, relokację, ręczne
pochodzenie i historię, oddzielenie eksportu, atomowy zapis, wspólną geometrię
oraz ograniczenie pamięci renderera. REG-06 pozostaje odłożony.

Wynik przeglądu: Standards — **0 twardych naruszeń, 1 uwaga heurystyczna**;
Spec — **1 P2 naprawione, 0 otwartych usterek**.

## Dane i odbiór

[Rzeczywiste pomiary, eksporty i ograniczenia](../full-trial-results.md)
obejmują pełne MOVIE_4/MOVIE_8, także odmowy lokalnego konsensusu. Testowano
wszystkie odtworzone klatki, źródła, pełny MPP+JSON i dekodowanie AVI FFV1,
ręczną parę oraz dwa nadpisania filmu. W osobnych procesach zablokowano
import Torch/Kornia, potwierdzając odczyt i porównanie na CPU.

[Ręczna instrukcja](../full-trial-manual.md) obejmuje GUI, porównanie struktur,
VLC i decyzję co do kolejnego etapu. Testy Qt offscreen oraz dekodowanie
OpenCV/FFmpeg są dowodami automatycznymi, nie ręcznym odbiorem. Windows,
fizyczne stanowisko 16 GB RAM / GPU 8 GB i VLC nie były tu certyfikowane.


## Testy automatyczne

- Końcowy Viewer po poprawce anulowania: **510 passed, 2 skipped**
  (`/tmp/reg07-viewer-final.log`). Pominięte testy wymagają jawnie wskazanego
  lokalnego checkpointu; osobne rzeczywiste próby z Outdoor opisuje raport.
- Pełne repo: **2296 passed, 14 failed, 16 skipped**, 274,05 s
  (`/tmp/reg07-full-suite-complete.log`). Zestaw identyfikatorów 14 błędów
  jest dokładnie równy wcześniejszemu `/tmp/reg02a-full-suite-final.log`:
  11 w MolTrack/SAM2, 3 w NanoTrack. Brak nowych błędów Viewera.
- Pierwszy pełny przebieg został zakończony SIGTERM przed podsumowaniem.
  Nie uznano go za zaliczony; ponowiono pełną komendę poza izolacją z
  diagnostycznym `faulthandler_timeout=120`. Powyższy wynik pochodzi z
  zakończonego ponowienia. Zrzut stosu wolnego testu nie jest wynikiem testu.
- Mypy: **57 modułów**, bez błędów. Ruff dla zmienionego kodu i testów: PASS.
  `git diff --check`: PASS. 24 zmienione pliki Python; maksimum **943 linie**.
- TDD obejmuje tożsamość i relokację źródeł, błędną wersję/uszkodzenie,
  anulowanie i ochronę wcześniejszego pliku, ręczne pochodzenie, oddzielne
  jakości par/skumulowane, ograniczoną pamięć i wartości interpolacji.
  Qt offscreen sprawdza zapis/odczyt, pełne A/B, zoom/gamma/Play, usuwanie,
  pary ręczne i ochronę aktywnego eksportu.

Polecenia z aktywnym `netcat`, w katalogu repozytorium:

```bash
PYTHONDONTWRITEBYTECODE=1 QT_QPA_PLATFORM=offscreen OPENBLAS_NUM_THREADS=1 PYTHONPATH=.:tests/stmviewer python -m pytest -q -p no:cacheprovider tests/stmviewer
PYTHONDONTWRITEBYTECODE=1 QT_QPA_PLATFORM=offscreen OPENBLAS_NUM_THREADS=1 PYTHONPATH=.:tests/moltrack:tests/stmviewer python -m pytest --import-mode=importlib -q -p no:cacheprovider -o faulthandler_timeout=120
python -m mypy --config-file stmviewer/mypy.ini --no-incremental --cache-dir=/tmp/stmviewer-reg07-mypy
```
