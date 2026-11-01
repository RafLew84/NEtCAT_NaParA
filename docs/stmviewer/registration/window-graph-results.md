# REG-08a — wyniki prób automatycznych i rzeczywistego modelu

Data: 2026-11-01. Status: próby obliczeniowe ukończone; ręczna ocena jakości niewykonana.
Baza zmiany: `e12a79440b806a9f44c3fe5b112212052ae6ce29`.

## Metoda i odtwarzalność

Obecny Deep Matcher / lokalny LoFTR **Outdoor**, bez ECC i bez wariantu REG-05.
Równe wagi LS; pierwsza klatka zakotwiczona w `(0,0)`; okna do trzech i pięciu
poprzednich klatek. W obu oknach są identyczne pomiary wspólnych par; drugie
obliczenie wykorzystuje cache i mierzy wyłącznie dodatkowe relacje.
Braki modelu pozostają w grafie z przyczyną; nie są zamieniane na zerowe XY.

Sprzęt próby: NVIDIA GeForce RTX 5090, 32 GB VRAM, Linux. Nie jest to odbiór
stanowiska z 8 GB VRAM ani Windows 11. NumPy 2.2.5, SciPy 1.15.2,
Torch 2.9.1+cu128, Kornia 0.8.2, 4 wątki Torch. Brak pobierania przez sieć.

Checkpoint: `loftr_outdoor.ckpt`, SHA-256
`21f5bec5968178e8bc8b7633441836fe5de4f47d861dd2cd7dc38e271b0479ec`.
Odcisk kodu estymatora, przygotowania danych i grafu zapisany w każdej próbie:
`sha256:e0e3ee3f5f891a25f8731c46d1eb31ef8a25625de75dca79d909fa75a3bff621`.
Pełna konfiguracja, wersje bibliotek, SHA źródeł i pikseli są w sesjach i raportach.

| Dane | Okno | Pary / braki | Ponownie użyte | Pomiary i przygotowanie | Solver | Render p95 | RAM peak procesu | VRAM allocated / reserved peak |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Wzorzec 7 × 256² | 3 | 15 / 0 | 0 | 0.78 s | 0.60 ms | 2.27 ms | 1504 MiB | 331 / 418 MiB |
| Wzorzec 7 × 256² | 5 | 20 / 0 | 15 | 0.23 s | 0.45 ms | 1.98 ms | 1657 MiB | 331 / 418 MiB |
| MOVIE_4, 362 × 256² | 3 | 1080 / 3 | 0 | 13.36 s | 5.11 ms | 3.30 ms | 2757 MiB | 331 / 418 MiB |
| MOVIE_4, 362 × 256² | 5 | 1795 / 5 | 1080 | 8.14 s | 7.67 ms | 3.06 ms | 2760 MiB | 331 / 418 MiB |
| MOVIE_8, 84 × 512² | 3 | 246 / 0 | 0 | 13.25 s | 1.56 ms | 11.79 ms | 2620 MiB | 937 / 1636 MiB |
| MOVIE_8, 84 × 512² | 5 | 405 / 0 | 246 | 5.03 s | 2.07 ms | 11.69 ms | 2656 MiB | 936 / 1636 MiB |

Czasy są pomiarami tego stanowiska, nie limitami ani gwarancją wydajności.
„Render” obejmuje pojedynczy raster każdego wariantu i każdej klatki, nie
transfer QImage/Qt ani odświeżanie monitora. RAM to maksimum całego procesu,
włącznie z odczytem sesji i aktywną bazą; nie sam narzut grafu. Podgląd nie
zachowuje stosów obrazów wariantów. VRAM obejmuje tylko alokator Torch.

Wszystkie sześć obliczeń zakończyło się pełnym, spójnym grafem bez mostów.
Sesje zapisano i ponownie odczytano; porównano wszystkie zapisane dane grafu.
Bazą w tych sesjach jest łańcuch tych samych sąsiednich pomiarów — bez drugiego
uruchomienia modelu. Kandydat pozostaje osobny, nie jest eksportowany.

## Wzorzec ze znanym ruchem

Siedem nieokresowych wycinków większej sceny z nawrotami XY, bez zawijania
brzegów. Oczekiwane położenia i generator: [instrukcja](window-graph-manual.md).
Maksymalny błąd współrzędnej kandydata: **0,054 px** (okno 3), **0,065 px**
(okno 5). Łańcuch: **0,197 px** w obu przypadkach. Wynik potwierdza znaki,
kotwicę, przeliczenie na piksele i współpracę z rzeczywistym modelem na tym
wzorcu. Nie jest dowodem poprawy na trudnym pomiarze STM.

## MOVIE_4

Użyto źródłowych klatek 3–364; źródłowy plik pozostaje bez zmian.
SHA-256: `9d066676a3f947ed53610438051537eb3b30288aadc11d774ec52e509f31f961`.

W numeracji po usunięciu dwóch klatek brak dopasowań:

- Okno 3: 37–40, 46–49, 86–89.
- Okno 5: te same trzy oraz 71–76, 72–76.

Każda odmowa oznacza 2 lub 3 punkty zgodne przy wymaganym minimum 4.
Inne relacje zapewniają obejście. Wszystkie pomiary sąsiednie są dostępne,
więc istnieje też pełna baza łańcuchowa. Rozmiary wspólnego kadru:
400 × 424 px (Y×X, okno 3), 368 × 409 px (okno 5). Mniejszy kadr nie jest
oceną poprawności. Problemowe przejścia wskazane przez użytkownika, pierwsze
150 klatek i cały film nadal wymagają ręcznej oceny.

## MOVIE_8

Pełne 84 klatki; SHA-256:
`a06ab5d34250ca564b11eb9da4e9ea65131b80d2a2e3ceaf09f0709569cdbde7`.
Brak odmów par dla obu okien. Wspólny kadr 759 × 763 px i 743 × 763 px (Y×X).
To wynik kompletności obliczeń; jakość struktur i tearing wymagają oględzin.

## Dostępne wyniki lokalne

- `/tmp/stmviewer-reg08a-fixtures/`: MPP ze znanymi XY, manifest oraz pięć
  sesji solvera: pełna, obejście braku, most, rozłączenie i spójny błędny alias.
  Te sesje mają **zadane pomiary**, nie wynik Deep.
- `/tmp/reg08a-known-results/`, `/tmp/reg08a-movie4-results/`,
  `/tmp/reg08a-movie8-results/`: w każdym katalogu `window-3.stmsession`,
  `window-5.stmsession`, `report.json`.
- Sesje MOVIE_4 i MOVIE_8 zajmują odpowiednio około 192 MB i 199 MB każda.
  Zawierają obrazy, bazę aligned i metadane grafu. Nie trzeba przenosić źródeł.
- Pliki w `/tmp` są tymczasowe; do trwałego zachowania należy zapisać sesję
  z aplikacji w wybranym katalogu. Duże pliki nie są wersjonowane w Git.

Odtworzenie (z katalogu repozytorium, `netcat`; katalog wyniku musi być nowy):

```bash
PYTHONPATH=.:tests/stmviewer python tests/stmviewer/diagnostics/graph_fixtures.py /tmp/stmviewer-reg08a-fixtures
PYTHONPATH=.:tests/stmviewer python tests/stmviewer/diagnostics/graph_trial.py data/MOVIE_4.mpp /tmp/reg08a-movie4-new --weights /ścieżka/loftr_outdoor.ckpt --drop-first 2
PYTHONPATH=.:tests/stmviewer python tests/stmviewer/diagnostics/graph_trial.py data/MOVIE_8.mpp /tmp/reg08a-movie8-new --weights /ścieżka/loftr_outdoor.ckpt
```

## Automatyka i odbiór

Testy pokrywają uzgodnione granice: obrazy/pomiary → graf, braki → jawne
komponenty i mosty, sesja/GUI → podgląd oraz zachowanie aktywnego filmu.
Są testy natywnej granicy LoFTR z kontrolowanym modelem; powyższe próby GPU
są odrębnym dowodem pracy rzeczywistych wag. Typechecking: 66 modułów.
Pełny zestaw repozytorium i dwa przeglądy są odnotowane w
[karcie odbioru](reviews/REG-08a.md).

Ręczne GUI, ocena dopasowania struktur obu filmów, Windows 11 i docelowe GPU
8 GB pozostają niewykonane. Zrzuty Qt offscreen służyły tylko kontroli układu.
