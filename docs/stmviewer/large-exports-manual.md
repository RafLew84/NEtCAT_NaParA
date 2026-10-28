# Ticket 19 — duże eksporty: próba ręczna

[Raport wykonanych pomiarów](large-exports-results.md). Ręczny odbiór użytkownika
jest jeszcze do wykonania. Do `done` potrzebny jest też odbiór poprawki wspólnego
czytnika przez integrację (opis na końcu). Automatyczne sterowanie GUI/X11 nie zastępuje tego odbioru.

## Uruchomienie i dane

W worktree Viewer, w środowisku `netcat`:

```bash
cd /home/rlew/projekty/NEtCAT-viewer
conda activate netcat
python -m stmviewer
```

Wejście: `data/large-ticket18-v2/large.mpp`, **1000 klatek 512 × 512**.
To deterministyczny wzorzec z dryfem, znaną skalą 1 nm/px i czasami co 1,5 s.
Manifest obok pliku identyfikuje dane i przesunięcia. Gotowe wyniki tej próby są
w `data/large-export-ticket19/`. Nowe próby zapisuj w osobnym katalogu,
np. `data/manual-ticket19/`, aby zachować wyniki porównawcze.

Gdy danych nie ma, przygotuj je strumieniowo:

```bash
python tests/stmviewer/make_large_series.py data/large-ticket18-v2
```

Generator nie nadpisuje istniejącego MPP. Samo wejście zajmuje około 2,1 GB;
pełen zestaw eksportów poniżej około 15 GB. Dodatkowy pomiar alokacji tworzy
około 6,8 GB. Potrzebne jest miejsce również na pliki tymczasowe podczas zapisu.

## Kroki i oczekiwane wyniki

1. Otwórz `large.mpp`; licznik ma wskazywać 1000 klatek. Wybierz Phase i
   Rejestruj. Aligned ma **640 × 640**, oryginalny obraz pozostaje 512 × 512.
   Wybór oglądanej klatki nie zmienia odniesienia: jest nim pierwsza klatka serii.
2. Zapisz całą serię przez „Zapisz MPP…”, osobno z typem **original** oraz
   **aligned**. Powstaną dwie pary `*.mpp` i `*.mpp.stmviewer.json`.
   Obserwuj postęp; podczas zapisu wybierz inną klatkę, zmień gamma, zoom i widok.
   Te zmiany podglądu nie zmieniają wartości w MPP ani ustawień rozpoczętego AVI.
3. Zapisz pełne original i aligned do AVI, każdy jako MJPG oraz FFV1, **30 kl./s**.
   Włącz podziałkę, numer klatki i czas. Dla original wybierz gamma 1 i kontrast
   osobno dla klatki; dla aligned gamma 2, wspólny kontrast i białe tło.
   W VLC powinno być 33,33 s filmu, czytelne opisy bez prostokątnych pól,
   pełny obraz oraz podziałka 100 nm. Original: 512 × 512; aligned: 640 × 640.
4. Usuń pierwszą klatkę, następnie ostatnią. Pozostaje **998 klatek**;
   pierwsza pochodzi ze źródłowej klatki 2 i ma czas 1,5 s, ostatnia z 999
   i ma czas 1497 s. Gotowe aligned zachowuje obszar i wcześniejsze położenia.
   Zapisz oba MPP oraz aligned AVI: MJPG z kontrastem osobnym/gamma 1/czarnym
   tłem i FFV1 z kontrastem wspólnym/gamma 2/szarym tłem.
5. Uruchom ponownie Phase. Odniesieniem jest teraz źródłowa klatka 2;
   w tym wzorcu obszar pozostaje 640 × 640. Zapisz aligned MPP oraz oba AVI
   z gamma 2: MJPG/kontrast osobny/tło szare i FFV1/kontrast wspólny/tło białe.
   Filmy mają 998 klatek, 33,267 s; czasy pomiaru nadal pochodzą z wejścia.
6. Rozpocznij nadpisanie gotowego MPP, potwierdź i kliknij Anuluj podczas zapisu.
   Powtórz dla AVI. Poprzednia para MPP i poprzedni AVI muszą pozostać czytelne,
   a program ma wrócić do przeglądania. Nie wywołuj ręcznie braku pamięci/dysku;
   kontrolowane awarie są częścią automatycznej próby.
7. Otwórz utworzone MPP w Viewerze. Sprawdź licznik, pierwszą/środkową/ostatnią
   klatkę, pochodzenie, czasy, rozmiar aligned i komunikat o wczytaniu dodatku.
   Aligned zawiera gotowe dopasowane piksele; do kolejnego Phase wczytaj original.
   Otwórz AVI w VLC, obejrzyj także końcówkę. Dokładne wartości MPP i rastry FFV1
   sprawdza raport automatyczny — sam podgląd nie potwierdza ich równości.

## Odtworzenie automatycznych pomiarów

Poniższe skrypty są opcjonalne i nie należą do szybkiego `pytest`.
Wymagają zależności aplikacji, OpenCV/FFmpeg oraz `psutil` (jest w `netcat`).
Uruchamiaj bez `python -O`, ponieważ warunki odbioru używają `assert`.
Skrypty GUI/VLC wymagają X11 (`QT_QPA_PLATFORM=xcb`) i niezasłoniętego okna.
Można użyć osobnego Xvfb, np. `Xvfb :98 -screen 0 1600x1200x24 -nolisten tcp`;
wybierz wolny numer ekranu i ustaw `DISPLAY=:98`. Nie zajmuj używanego ekranu.
Pomiary czasu eksportu uruchamiaj osobno od pełnych testów i tracemalloc.

```bash
export PYTHONDONTWRITEBYTECODE=1
export PYTHONPATH=.:tests/stmviewer
export QT_QPA_PLATFORM=xcb
python tests/stmviewer/measure_large_exports.py data/large-ticket18-v2/large.mpp data/large-export-repeat
python tests/stmviewer/check_large_exports.py data/large-export-repeat/report.json full
python tests/stmviewer/check_large_exports.py data/large-export-repeat/report.json deleted
python tests/stmviewer/check_large_exports.py data/large-export-repeat/report.json reregistered
python tests/stmviewer/reopen_large_exports.py data/large-export-repeat/report.json
python tests/stmviewer/play_large_exports.py data/large-export-repeat/report.json --vlc /snap/bin/vlc
python tests/stmviewer/check_export_allocations.py data/large-ticket18-v2/large.mpp data/large-export-repeat-allocations
```

Katalogi wyjściowe eksportów/alokacji/VLC muszą być nowe. Raport zapisuje SHA-256
wejścia, MPP, dodatków i AVI, indeksy źródłowe, opcje, czasy i RSS procesu wraz
z dziećmi co 50 ms. `verification-*.json` porównuje komplet próbek/metadanych
MPP i komplet klatek AVI. Próg błędu MJPG uwzględnia kompresję stratną,
FFV1 wymaga identycznego rastra. `gui-reopen.json` mierzy ponowne otwarcie,
`allocations.json` odróżnia żywe bufory od bloków zachowanych przez alokator.

VLC uruchamia się z konfiguracją `/dev/null`, bez sieciowych metadanych i bez
akceleracji sprzętowej. Skrypt czeka na koniec każdego filmu i zachowuje dwa
zrzuty do oceny. Ich czas jest liczony od startu procesu, więc przy powolnym
starcie VLC drugi zrzut może przedstawiać środek filmu. Zrzuty nie zastępują
pełnego dekodowania ani oceny odświeżania fizycznego monitora.

Wspólny czytnik NaPara/NanoTrack ma obecnie limit 1000 wierszy nagłówka;
pełny film z 1000 czasów go przekracza. To zgłoszenie dla integracji opisane
w raporcie, nie dowód uszkodzenia wyeksportowanych danych. Odbiór Windows
pozostaje oddzielnym ticketem 21.
