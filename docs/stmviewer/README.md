# STM Viewer

Program do przeglądania obrazów i sekwencji STP/S94/MPP, rejestracji
oraz eksportu MPP/AVI. Katalog aplikacji: `stmviewer/`.

## Stan aplikacji

Działa otwieranie jednego lub wielu STP/S94, także mieszanych, oraz jednego filmu MPP.
STP/S94 sortujemy naturalnie, MPP zachowuje kolejność źródłową. Dostępny jest podgląd
z dolnym paskiem miniatur, suwakiem, numerem i przyciskami klatek.
Panel pokazuje pochodzenie i metadane aktualnej klatki. Import działa w tle,
ma postęp i anulowanie; błąd lub anulowanie zachowują wcześniejszą serię.
Wymagane są wspólne wymiary pikselowe, skale i kanały mogą się różnić.
Kółko myszy zmienia zoom pod kursorem; przeciąganie lewym przyciskiem przesuwa
obraz z zachowaniem powiększenia. Przyciski +/− zmieniają zoom wokół środka.
Gamma 0,1–4 dotyczy głównego obrazu; miniatury pozostają przy gamma 1.
Brakujące próbki pokazuje białe tło. Opcja Proporcje pikselowe pozwala
pominąć niewiarygodną skalę źródłową: [próba podglądu](preview-controls-manual.md). Zmiana klatki zachowuje widok, a „Dopasuj”
i nowy poprawny import przywracają całą klatkę. Próba ręczna:
[instrukcja serii STP](stp-series-manual.md) oraz
[S94 i mieszane serie](s94-series-manual.md). S94 rozróżnia dane skalibrowane
w nm/nA od surowych wartości przy nieznanym trybie lub wzmocnieniu.
MPP pokazuje numer źródłowej klatki oraz dostępny czas pomiaru, także przy
częściowych brakach: [instrukcja próby MPP](mpp-series-manual.md).
Play/Pause, tempo 1/2/5/10/20/30 kl./s i pętla działają; ręczny wybór
zatrzymuje film. [Instrukcja odtwarzania](playback-manual.md).
Rejestracja Phase, Tile+RANSAC, ECC i Optical Flow działa w tle z postępem i anulowaniem. Wynik aligned ma
pełny obszar, obrys źródła i oznaczenia niepewności; przełącznik original/aligned
zachowuje osobne kadry. [Instrukcja rejestracji](phase-registration-manual.md).
[Próba metod CPU](cpu-registration-manual.md) opisuje wybór metody,
stan dostępności i zachowanie wcześniejszego wyniku. Deep Matcher używa lokalnych
wag LoFTR i pozwala wybrać Auto/CPU/CUDA; Sprawdź model działa w tle.
[Instrukcja modelu i wag](deep-matcher-manual.md). Działa zapis całej serii original lub aligned do MPP z towarzyszącymi metadanymi,
postępem i anulowaniem: [zapis original](original-mpp-manual.md) oraz
[zapis aligned](aligned-mpp-manual.md). Wersję wybiera się w polu Typ pliku
okna zapisu; domyślnie jest to aktualny widok. Dostępne są tylko **original**
i **aligned**. Zapis używa jasnego tła w MPP i dokładnego opisu braków w JSON.
Do odtworzenia braków w STM Viewerze przenoś oba pliki razem.
[Próba zapisu i białego tła](wsxm-export-manual.md). Odczyt aligned zachowuje pełny
obszar, NaN, obrys źródłowej klatki i historię. Dostępny jest również eksport
original do AVI: cała seria lub zakres, FPS 1–30, MJPG/FFV1, gamma podglądu,
pełne obrazy oraz postęp i anulowanie. [Próba AVI](original-avi-manual.md).
Ticket 14 oczekuje na ręczny odbiór; opcje prezentacji, aligned i opisy
należą do kolejnych etapów.
Przycisk Usuń klatkę usuwa bieżący obraz z serii, zatrzymuje Play i zachowuje
pochodzenie oraz czasy pozostałych klatek. Źródła na dysku pozostają bez zmian:
[instrukcja usuwania](frame-deletion-manual.md).
Mapa decyzji jest zamknięta: specyfikacja pierwszej wersji jest gotowa do
implementacji. Nie oznacza to wdrożenia funkcji ani zaliczenia odbioru.

[Kryteria odbioru](issues/06-acceptance.md#answer) obejmują Ubuntu 24.04 i
Windows 11, uruchomienie z repozytorium, 16 GB wolnego RAM, SSD i NVIDIA/CUDA
z minimum 8 GB VRAM. Dane typowe uzupełnia test 1000 klatek 512 × 512;
filmy AVI sprawdzamy w VLC na obu systemach. [Inwentarz lokalny](acceptance-reconnaissance.md)
opisuje dostępne pomiary, sprzęt i granice wykonanych sprawdzeń.
Od 2026-10-21 lokalne pomiary do kolejnych testów znajdują się w
`/home/rlew/projekty/NEtCAT-viewer/data/` (czyli `data/` z katalogu repo).
Katalog pozostaje poza Git; małe wzorce testowe są w `tests/stmviewer/fixtures/`.

## Mapa

- [STM Viewer — mapa pierwszej wersji](map.md) — cel, zakres i indeks zamkniętych decyzji.
- [Tickety](issues/) — pytania do rozstrzygnięcia, po jednym w pliku.
- [Słownik STM Viewer](GLOSSARY.md) — pojęcia serii i rejestracji.
- [Rozpoznanie istniejącego kodu](reconnaissance.md) — fakty, zależności i ograniczenia.
- [Przekazanie](handoff.md) — wynik sesji i potrzebne wspólne zmiany.

Lokalny tracker adaptuje konwencję `wayfinder` do wymaganych przez repo ścieżek
`docs/stmviewer/`, zamiast `.scratch/`. Pliki wersjonujemy na gałęzi `viewer/*`.
Mapa i jej tickety decyzyjne mają wyłącznie etykiety `wayfinder:*`.

Ticket ma `Type`, `Status` (`open`, `claimed`, `resolved`), `Assignee`, `Parent`
i `Blocked by`. Brak zależności oznaczamy `none`; pozostałe wskazują numery
plików. Dostępny ticket jest otwarty, nieprzejęty i ma wszystkie blokujące
tickety rozwiązane. Wybieramy pierwszy według numeru.

Przed pracą ustaw `Status: claimed` i `Assignee: rlew` (osoba prowadząca mapę).
Komentarze dopisuj pod `Comments`. Rozstrzygnięcie zapisz jako `Answer`, ustaw
`Status: resolved` i dopisz nazwany link z krótkim wynikiem do mapy. Nie zmieniaj
samego pytania w magazyn decyzji. W sesji rozstrzygamy najwyżej jeden ticket
(wyjątek skillu: research); tworzenie mapy nie zamyka ticketów.

## Implementacja

[Lista 21 ticketów implementacyjnych](implementation/README.md) została
zatwierdzona 2026-10-19 wraz z zależnościami i publicznymi granicami testowania
TDD. Każdy etap kończy się funkcją możliwą do sprawdzenia w działającym GUI
oraz zawiera konkretne kroki próby i oczekiwane wyniki.

[Pierwszy obraz STP w działającym oknie](implementation/issues/01-single-stp.md)
ma status `done`.
[Otwarcie i przeglądanie serii STP](implementation/issues/02-stp-series.md)
ma status `done`: użytkownik potwierdził testy manualne, w tym poprawkę
podświetlenia miniatur, 2026-10-21.
[S94 i mieszane serie STP/S94](implementation/issues/03-s94-series.md) mają
status `done`: użytkownik potwierdził testy manualne 2026-10-21.
[Otwarcie filmu MPP z czasami i pochodzeniem](implementation/issues/04-mpp-series.md)
ma status `done`: użytkownik potwierdził testy manualne 2026-10-21.
[Zoom, gamma i brakujące próbki](implementation/issues/05-preview-controls.md)
mają status `done`: użytkownik potwierdził [testy manualne](preview-controls-manual.md)
2026-10-21.
[Play, Pause i tempo odtwarzania](implementation/issues/06-playback.md)
mają status `done`: użytkownik potwierdził [testy manualne](playback-manual.md)
2026-10-21.
[Usuwanie klatek z zachowaniem czasu i pochodzenia](implementation/issues/07-frame-deletion.md)
ma status `done`: użytkownik potwierdził [testy manualne](frame-deletion-manual.md)
2026-10-23.
[Rejestracja Phase i pełny widok aligned](implementation/issues/08-phase-registration.md)
ma status `done`: użytkownik potwierdził [testy manualne](phase-registration-manual.md)
2026-10-23.
[Pozostałe metody rejestracji CPU](implementation/issues/09-cpu-registration-methods.md)
mają status `done`: użytkownik potwierdził [testy manualne](cpu-registration-manual.md)
2026-10-23.
[Deep Matcher z lokalnymi wagami](implementation/issues/10-deep-matcher.md)
ma status `done`: użytkownik potwierdził [testy manualne](deep-matcher-manual.md)
2026-10-23 po wyjaśnieniu obwódki interpolacyjnej na wzorcu cpu.mpp.
[Otwarcie MPP z metadanymi towarzyszącymi](implementation/issues/11-mpp-metadata-import.md)
ma status `done`: użytkownik potwierdził testy manualne 2026-10-23.
[Próba ręczna](mpp-metadata-manual.md), [format dodatku V1](mpp-metadata-format.md).
[Zapis original do MPP i ponowne otwarcie](implementation/issues/12-original-mpp.md)
ma status `done`: użytkownik potwierdził [testy manualne](original-mpp-manual.md)
2026-10-26.
[Zapis aligned do MPP](implementation/issues/13-aligned-mpp.md) ma status
`done`: użytkownik potwierdził testy manualne 2026-10-26, wraz z poprawkami
zgodności MPP, białego tła i uproszczeniem zapisu do original/aligned;
[scenariusz próby ręcznej](aligned-mpp-manual.md) obejmuje zapis po usunięciu
odniesienia, historię geometrii i dokładne porównanie próbek.
Statusy i przebieg pracy skillem `implement` opisuje indeks implementacji.
Są odrębne od zamkniętego trackera decyzji powyżej; tych decyzji nie otwieramy
ponownie przy rozpoczynaniu kodowania. W instrukcji aplikacji obowiązuje
cel do 1000 linii i bezwzględny limit 1500 fizycznych linii pliku kodu.

## Uruchomienie

Z katalogu głównego worktree, z Pythonem 3.12. Dla tej funkcji potrzebne
są NumPy, PyQt6 oraz SciPy/scikit-image dla Phase, Tile+RANSAC i Optical Flow; wersje zapisano w `stmviewer/requirements.txt`,
który korzysta ze wspólnego zestawu PyQt6 z `requirements/stm-apps.txt`.

Ubuntu 24.04:

```bash
python3.12 -m venv .venv
.venv/bin/python -m pip install -r stmviewer/requirements.txt
.venv/bin/python -m stmviewer.main
```

Windows 11, PowerShell (instrukcja przygotowana, próba na Windows jeszcze niewykonana):

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r stmviewer/requirements.txt
.\.venv\Scripts\python.exe -m stmviewer.main
```

ECC dodatkowo wymaga OpenCV. Opcjonalny zestaw `stmviewer/requirements-ecc.txt`
zawiera podstawowe zależności oraz `opencv-python==4.11.0.86` (wersja użyta w próbie
lokalnej). Instalacja w wybranym środowisku:

```bash
# Ubuntu
.venv/bin/python -m pip install -r stmviewer/requirements-ecc.txt
```

```powershell
# Windows
.\.venv\Scripts\python.exe -m pip install -r stmviewer/requirements-ecc.txt
```

Bez OpenCV ECC pozostaje na liście z powodem niedostępności; pozostałe metody
są dostępne. Brak SciPy/scikit-image wyłącza rejestrację, zachowując przeglądanie.
Program niczego nie pobiera i nie zastępuje wybranej metody. Zmiana zainstalowanych
zależności wymaga ponownego uruchomienia programu.

Deep Matcher ma osobny, opcjonalny zestaw `stmviewer/requirements-deep.txt`.
[Instrukcja](deep-matcher-manual.md#przygotowanie-zależności-poza-aplikacją) podaje
wybór wariantu Torch dla CPU/CUDA, lokalne wagi i rzeczywistą kontrolę urządzenia.
Aplikacja nie instaluje bibliotek ani nie pobiera wag.

W już przygotowanej conda `netcat`:

```bash
conda activate netcat
python -m stmviewer.main
```

Na tym stanowisku można również użyć bezpośrednio
`/home/rlew/projekty/conda-migration-ubuntu-20261008/envs/netcat/bin/python`.
Przycisk „Otwórz STP/S94/MPP…”, menu Plik lub Ctrl+O otwierają wybór jednego lub wielu STP/S94 albo jednego MPP.
Małe dane i oczekiwany wygląd: [próba ręczna STP/S94](s94-series-manual.md).

Kontrole dla dewelopera (po aktywowaniu środowiska):

```bash
python -m pip install -r stmviewer/requirements-dev.txt
python -m mypy --config-file stmviewer/mypy.ini
python -m pytest -q tests/stmviewer
```

Testy Qt wymagają ekranu lub ustawienia `QT_QPA_PLATFORM=offscreen` przed
uruchomieniem pytest (Linux: prefiks komendy; PowerShell:
`$env:QT_QPA_PLATFORM = "offscreen"`). Tryb offscreen dotyczy testów,
nie interaktywnego uruchomienia aplikacji.
Mypy sprawdza cały kod `stmviewer` w trybie strict, pomija śledzenie starego
kodu `napara`. Komenda i zależności są sprawdzone po stronie aplikacji
oraz opisane dla integracji w [handoff](handoff.md).
Nie zmieniono głównej konfiguracji ani wspólnych czytników.

[Przygotowanie środowiska repo](../../README.md) i
[praca równoległa](../PARALLEL_DEVELOPMENT.md).

## Kod do wykorzystania i testy

- Czytniki: `napara/io/`; dane obrazu: `napara/core/data_models.py`.
- Viewer: `napara/gui/widgets/viewer_widget.py`.
- Rejestracja: `nanotrack/registration/`.
- Testy nowych funkcji i małe wzorce: `tests/stmviewer/`.

Współdzielony kod wymaga dodatkowych zależności poza minimalnym PyQt6 szkieletu.
Ich dobór oraz zmiany wspólnych modułów koordynuje sesja integracyjna.
