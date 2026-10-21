# Przekazanie — STM Viewer

## 02: Otwarcie i przeglądanie serii STP — 2026-10-21

Gałąź: `viewer/start`. Baza implementacji i code-review:
`3f2e92b59d29dc0ecf74751807e26f530167af7d`.
Commit implementacji: `e054738`. Finalny zakres tego etapu: `3f2e92b..HEAD`;
commit raportu podany w końcowej wiadomości sesji.
Ticket: [02-stp-series](implementation/issues/02-stp-series.md),
status `ready-for-review` do ręcznego odbioru użytkownika.

### Wynik

Otwieranie jednego lub wielu STP sortuje nazwy naturalnie i wymaga jedynie
zgodnych wymiarów pikselowych. Odczyt wykorzystuje sprawdzony adapter;
każda klatka zachowuje własne wartości, orientację, skalę, kanał i pozostałe
metadane. Miniatury oryginałów są na dole, ustawienia po prawej.
Przyciski, suwak, edytowalny numer, zaznaczenie miniatury, główny obraz i panel
źródła wskazują tę samą klatkę. Pasek przewija się do wybranej miniatury.

Odczyt i przygotowanie miniatur wykonuje zadanie w tle. Postęp obejmuje obie
fazy. Błąd lub anulowanie nie zastępują poprzedniego zestawu i wyboru.
Podczas importu działają podgląd i nawigacja starej serii; nowy import jest
zablokowany. Anulowanie czeka na ukończenie bieżącego odczytu pojedynczego
pliku; okno nadal obsługuje zdarzenia. Zamknięcie podczas importu anuluje
zadanie i zamyka okno po zakończeniu wątku.

Zmiana klatki zachowuje zoom i przesunięcie. Sukces nowego importu pokazuje
pierwszą klatkę dopasowaną do okna. Pusta i pojedyncza seria mają odpowiednio
nieaktywne kontrolki. To realizuje również część przyszłego ticketu 05;
gamma i szachownica pozostają do wykonania.

### Sprawdzenia

- TDD: red → green dla naturalnego sortowania/odczytu, kontroli wymiarów,
  anulowania, nawigacji GUI oraz responsywności przy opóźnionym I/O.
  Testy korzystają z uzgodnionych publicznych granic. Zastępowane są jedynie
  dialog systemowy i czas odczytu pliku, bez atrap wewnętrznych komponentów.
- **33 testy Viewera zaliczone** w Qt offscreen. Obejmują regresje pojedynczego
  STP i gestów, dane liczbowe/metadane, odmienne znane kanały i skale,
  orientację miniatur, synchronizację, anulowanie, błędy oraz zamykanie w trakcie pracy.
- Mypy strict: **12 plików bez błędów**. Największy zmieniony plik kodu:
  `stmviewer/ui/main_window.py`, **252 linie**; wszystkie poniżej 1500.
- Pełne repo w `netcat`:
  `PYTHONPATH=.:tests/moltrack QT_QPA_PLATFORM=offscreen python -m pytest -q --import-mode=importlib --continue-on-collection-errors`:
  **1772 passed, 63 failed, 12 skipped**, 205.54 s. Zestaw 63 niepowodzeń
  jest identyczny z poprzednią próbą (`/tmp/stmviewer-navigation-full-suite.log`):
  starsze testy MolTrack/NanoTrack, m.in. brak MOVIE_3.MPP, ścieżki Windows,
  SAM2. **Brak nowych niepowodzeń i błędów zbierania**. To nie jest zielony odbiór
  całego repo. Log: `/tmp/stmviewer-series-full-suite.log`.
- Automatyczna próba rzeczywistego okna Qt xcb na Linuksie: dialog wielu STP,
  kolejność 1–2–10, przyciski i miniatury, następnie rzeczywisty pomiar 34855.STP.
  Zrzuty oceniono wizualnie: `/tmp/stmviewer-series-xcb.png`,
  `/tmp/stmviewer-series-current-xcb.png`, `/tmp/stmviewer-series-measurement-xcb.png`.
- Generator większych danych sprawdzono na trzech STP 64 × 64 z ponownym
  odczytem. Duża próba wydajności z ticketu 18 nie została tu wykonana.

- [Przegląd Standards/Spec](implementation/review-02-stp-series.md): obie
  niezależne osie bez ustaleń wymagających poprawki. Generatory odtworzyły
  wzorce bajtowo bez zmian; 38 odnośników dokumentacji było poprawnych,
  `git diff --check` bez błędów.

### Odbiór i integracja

[Instrukcja GUI i wzorce](stp-series-manual.md) obejmują ręczny scenariusz,
łącznie z generowaniem większego zestawu do anulowania. Ręczny odbiór użytkownika
oraz próba Windows są niewykonane. Wcześniejsze potwierdzenie ticketu 01
pozostaje ważne, ale nie obejmuje nowej serii.

Zmiany dotyczą wyłącznie aplikacji Viewera, jej testów i dokumentacji.
Nie zmieniono konfiguracji głównej, zależności ani współdzielonych loaderów;
nie potrzeba nowej poprawki integracyjnej. Uruchomienie pozostaje
`python -m stmviewer.main` w `netcat`. Nie publikowano ani nie scalano gałęzi.

## Uzupełnienie: zoom i przesuwanie — 2026-10-21

Baza dodatku: `7a43715`, gałąź `viewer/start`. Commit kodu: `75f419d`.
Commit raportu testów i przeglądu: `df4bbc5`.
Użytkownik potwierdził ręczną próbę otwierania STP i zlecił wcześniejsze dodanie
nawigacji obrazu. To część zakresu [05](implementation/issues/05-preview-controls.md),
bez zamykania jego przyszłych wymagań dotyczących serii i gamma.

Kółko zmienia zoom pod kursorem (czynnik 1.2 na krok, zakres 0.1–64 względem
dopasowania), lewy przycisk przesuwa obraz w obu osiach bez zmiany zoomu.
Przycisk „Dopasuj” przywraca cały obraz. Poprawny import dopasowuje nową klatkę,
anulowanie i błąd zachowują nawigację. Pusty program ma nieaktywne Dopasuj.
Zależności i wspólny kod pozostają bez zmian. Przy wprowadzaniu przeglądania
serii trzeba zachować zoom na zmianie klatki: obecne `set_frame` oznacza nowy import.

Sprawdzenia dodatku: pięć testów publicznych gestów GUI przechodzi w offscreen
(zoom pod kursorem, ruch podczas przeciągania i stała wielkość znacznika,
Dopasuj, zachowanie/reset przy imporcie, pusty program). Mypy strict: 8 plików,
bez błędów. Automatyczna próba xcb otworzyła rzeczywisty 34855.STP przez dialog,
sprawdziła kółko, przeciąganie i powrót przez Dopasuj. Użytkownik potwierdził
ręczny odbiór nawigacji 2026-10-21: „testy manualne ok”.
[Scenariusz](single-stp-manual.md#zoom-i-przesuwanie). Nie wskazał platformy;
potwierdzenie nie zamyka osobnych odbiorów Ubuntu i Windows.
[Przegląd dodatku](implementation/review-preview-navigation.md): Standards — 0 ustaleń,
Spec — 0 ustaleń. Największy zmieniony plik kodu ma 132 linie, `git diff --check`
bez błędów. Zrzut automatycznej próby: `/tmp/stmviewer-navigation-xcb.png`.
Pełny zestaw repo w `netcat`:
`PYTHONPATH=.:tests/moltrack QT_QPA_PLATFORM=offscreen python -m pytest -q --import-mode=importlib --continue-on-collection-errors`
— **1758 passed, 63 failed, 12 skipped** w 203.27 s. Wszystkie 19 testów
Viewera przeszły. Zestaw 63 niezaliczonych testów jest identyczny z wcześniejszą
bazą `ba4e0d3`; nie ma nowych błędów ani błędów zbierania testów.
Log: `/tmp/stmviewer-navigation-full-suite.log`.

## 01: Pierwszy obraz STP — poprzedni etap

Data: 2026-10-21. Gałąź: `viewer/start`. Baza zmiany i code-review: `ba4e0d3`.
Commit implementacji: `960101c`; finalny zakres `ba4e0d3..HEAD`.
Commit raportu odbioru podany w końcowej wiadomości sesji.
Ticket: [01-single-stp](implementation/issues/01-single-stp.md).

## Wynik

Działa otwieranie pojedynczego STP z przycisku, menu i Ctrl+O. Obraz jest
w całości dopasowany, z proporcjami fizycznymi przy znanej skali obu osi,
a przy braku skali — pikselowymi. Panel pokazuje źródło, rozmiar, kanał,
jednostkę sygnału, pole i offsety X/Y, napięcie, prąd oraz kąt.
Brak metadanych pozostaje brakiem, rzeczywiste zera są zachowane.
Anulowanie i błąd odczytu nie wymieniają poprzedniego obrazu.

`stmviewer.io.open_stp` wykorzystuje dekodowanie double i obrót 180°
w `napara.io.stp_reader`. Adapter zachowuje źródłowy kanał, metadane
z nagłówka i jednostkę z Z Amplitude bez skalowania próbek. Odczytuje UTF-8
oraz starsze nagłówki Latin-1 bez usuwania µ. Odrzuca jawny typ inny niż
`double`, błędne wymiary, niepełny payload i brak końca nagłówka.
Nagłówek adaptera ograniczono do 1 MiB, 64 KiB na linię i limitu liczby
linii wspólnego czytnika. Wartości pozostają float64; podgląd to osobny raster.

Nie zmieniono wspólnych aplikacji ani głównej konfiguracji. Małe wzorce,
ich generator i [ręczny scenariusz](single-stp-manual.md) są w Git.
Uruchomienie z `netcat`: `python -m stmviewer.main` z katalogu repo.
Instrukcje środowisk Ubuntu/Windows: [README](README.md#uruchomienie).

## Sprawdzenia

- TDD: zaobserwowane red → green dla dekodowania, publicznego otwarcia
  w GUI, błędów importu z nazwą źródła oraz zachowania jednostki µ w Latin-1.
- Testy Viewera: 12 testów importu i 2 testy GUI offscreen — zaliczone.
  Publiczne kontrolki sprawdzają również zastąpienie, anulowanie i błędny plik.
- `python -m mypy --config-file stmviewer/mypy.ini`: 8 plików aplikacji,
  strict, bez błędów. Stary kod `napara` nie jest objęty tym sprawdzeniem typów.
- Trzy rzeczywiste STP (34855, 17851, 17544) wczytane poprawnie: 256 × 256,
  kanał Topo, jednostka nm, zachowane zakresy wartości i skala X/Y.
- Automatyczna próba z prawdziwym oknem Qt xcb na Linuksie: wybór wzorca
  i rzeczywistego 34855.STP w dialogu, zmiana rozmiaru okna do 640 × 480.
  Zapisane obrazy ocenione wizualnie: prawidłowe L i pełne pole pomiaru.
  To próba sterowana skryptem, nie ręczny odbiór użytkownika.
- Pełny zestaw repo uruchomiony raz w `netcat` z
  `QT_QPA_PLATFORM=offscreen python -m pytest -q --import-mode=importlib --continue-on-collection-errors`:
  **1479 passed, 64 failed, 12 skipped, 36 errors**. Błędy dotyczą
  MolTrack/NanoTrack (brak `data/MOVIE_3.MPP`, ścieżki Windows, SAM2)
  oraz importów helperów testowych MolTrack przy `importlib`.
  Czyste archiwum `ba4e0d3` uruchomione tą samą komendą:
  **1466 passed, 63 failed, 12 skipped, 36 errors**. Wszystkie 99
  niepowodzeń bazy występuje też w bieżącym kodzie. Jedyna różnica to timeout
  10 s workera SAM2; powtórzony samodzielnie w bieżącym kodzie przeszedł
  w 0.70 s. Nie stwierdzono regresji Viewera; nie jest to zielony odbiór repo.
  Błędy zbierania wynikają z braku `tests/moltrack` w ścieżce importów
  pomocników testowych przy wybranym trybie `importlib`.
  Ponowiono tylko te 36 modułów z `PYTHONPATH=.:tests/moltrack`:
  **273 passed in 151.70 s**, bez błędów zbierania. Nie zmieniano ich kodu.
- Limit plików: największy nowy/zmieniony plik Python ma 109 linii.
  `git diff --check` bez błędów.
- [Przegląd Standards/Spec](implementation/review-01-single-stp.md):
  Standards — 0 ustaleń; Spec — 0 usterek kodu. W chwili przeglądu pozostały
  2 warunki odbioru; ich zamknięcie opisano poniżej.
  Obie osie wykonane przez niezależnych recenzentów od uzgodnionej bazy.

Lokalne logi: `/tmp/stmviewer-full-suite.log`, `/tmp/stmviewer-baseline-suite.log`
i `/tmp/stmviewer-collection-recheck.log`. Generator odtworzył wzorce bajtowo
bez zmiany w Git; 36 lokalnych odnośników zmienionej dokumentacji jest poprawnych.
Zrzuty próby xcb: `/tmp/stmviewer-asymmetric-xcb.png`,
`/tmp/stmviewer-measurement-xcb.png`, `/tmp/stmviewer-measurement-small-xcb.png`.
Artefakty lokalne nie są częścią repozytorium.

## Odbiór i integracja

Ticket 01 ma status `done`: funkcja działa, testy i instrukcje są dostarczone,
a użytkownik zatwierdził odbiór. Następny odblokowany etap to ticket 02.
Użytkownik potwierdził ręczny scenariusz otwierania STP 2026-10-21:
„testy manualne ok”. Nie podał systemu, więc nie oznacza to odbioru Windows.
Usunięto dodatkową blokadę osobnego potwierdzenia lokalnej konfiguracji:
nie zmieniono konfiguracji głównej ani wspólnych modułów. Doprecyzowanie
zapisano w kryterium ticketu i zasadach implementacji.

Do wykorzystania przy integracji: minimalne wymagania aplikacji
`stmviewer/requirements.txt` (wspólny PyQt6 + NumPy 2.2.5),
`stmviewer/requirements-dev.txt` oraz komenda
`python -m mypy --config-file stmviewer/mypy.ini`. Konfiguracja działa lokalnie
bez zmiany root i została przekazana w dokumentacji. Odrębnego zatwierdzenia
przez sesję integracyjną nie przeprowadzono; nie jest ono warunkiem zamknięcia
tego lokalnego etapu. Scalenie gałęzi pozostaje osobną czynnością.
Wspólny czytnik wymaga w przyszłości obsługi Acquisition channel,
X-Offset/Y-Offset, nieznanych wartości, osobnej jednostki sygnału i kodowania
nagłówka bez utraty µ. Adapter zapewnia ten kontrakt już w Viewerze.
Zmiany wspólnego czytnika powinny objąć testy jego istniejących odbiorców.

Pozostałe potrzeby integracyjne i zakres całej aplikacji zachowano
we [wcześniejszym przekazaniu planu](planning-handoff.md).
