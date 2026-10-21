# Przekazanie — 01: Pierwszy obraz STP w działającym oknie

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
  Standards — 0 ustaleń; Spec — 0 usterek kodu, 2 jawnie otwarte warunki odbioru.
  Obie osie wykonane przez niezależnych recenzentów od uzgodnionej bazy.

Lokalne logi: `/tmp/stmviewer-full-suite.log`, `/tmp/stmviewer-baseline-suite.log`
i `/tmp/stmviewer-collection-recheck.log`. Generator odtworzył wzorce bajtowo
bez zmiany w Git; 36 lokalnych odnośników zmienionej dokumentacji jest poprawnych.
Zrzuty próby xcb: `/tmp/stmviewer-asymmetric-xcb.png`,
`/tmp/stmviewer-measurement-xcb.png`, `/tmp/stmviewer-measurement-small-xcb.png`.
Artefakty lokalne nie są częścią repozytorium.

## Odbiór i integracja

Status `ready-for-review`: funkcja działa, testy i instrukcje są dostarczone.
Ręczny scenariusz użytkownika nie został wykonany; automatyczne sterowanie
xcb nie zastępuje tego dowodu. Windows nie był dostępny do próby.

Do potwierdzenia w sesji integracyjnej: minimalne wymagania aplikacji
`stmviewer/requirements.txt` (wspólny PyQt6 + NumPy 2.2.5),
`stmviewer/requirements-dev.txt` oraz komenda
`python -m mypy --config-file stmviewer/mypy.ini`. Konfiguracja działa lokalnie
bez zmiany root; nie deklarujemy uzgodnienia, którego jeszcze nie było.
Wspólny czytnik wymaga w przyszłości obsługi Acquisition channel,
X-Offset/Y-Offset, nieznanych wartości, osobnej jednostki sygnału i kodowania
nagłówka bez utraty µ. Adapter zapewnia ten kontrakt już w Viewerze.
Zmiany wspólnego czytnika powinny objąć testy jego istniejących odbiorców.

Pozostałe potrzeby integracyjne i zakres całej aplikacji zachowano
we [wcześniejszym przekazaniu planu](planning-handoff.md).
