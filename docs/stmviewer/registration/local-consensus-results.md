# REG-05 — rzeczywiste próby modelu i filmów

Data: 2026-10-31. Implementacja REG-05 po bazie `a59029d`.
Status: **gotowe do oceny wizualnej; przewaga nad samym Deep niepotwierdzona**.

Deep policzył 14/14 wskazanych par. Finalny wariant „Deep Matcher + lokalne
fragmenty (v1)” policzył 2/14, a pozostałym 12 odmówił. Próby pełnych
MOVIE_4 i MOVIE_8 zakończyły się odmową; nie powstały kompletne lokalne filmy.
Wzorce o znanej translacji i z niezależnym szumem dały poprawne wyniki
numeryczne w opisanych niżej próbach. Nie stanowią potwierdzenia jakości STM.

Są to automatyczne próby publicznych funkcji `estimate_pair` i `register_series`,
bez manualnego odbioru obrazów, Windows ani VLC. Procedura oceny w aplikacji:
[instrukcja ręczna REG-05](local-consensus-manual.md).

## Stanowisko, dane i ustawienia

- Linux, środowisko `netcat`; Python 3.12.12, Torch 2.9.1+cu128,
  Kornia 0.8.2, OpenCV 4.11.0; Torch/OMP: 4 wątki, OpenBLAS: 1.
- NVIDIA GeForce RTX 5090, około 32 GB VRAM. Deep pracował na CUDA
  w próbach pomiarów i wzorców oznaczonych CUDA; etap lokalny działa na CPU.
  W próbie `translation-cpu` oba etapy działały na CPU.
- Lokalne wagi LoFTR outdoor:
  `/home/rlew/projekty/tracker-import-20261008/trackers-windows-20261008/model_cache/torch/hub/checkpoints/loftr_outdoor.ckpt`.
  SHA-256: `21f5bec5968178e8bc8b7633441836fe5de4f47d861dd2cd7dc38e271b0479ec`.
  Narzędzie blokuje pobieranie przez Torch i `urlopen`; nie pobierano modeli.
- Parametry Deep są identyczne w bazie i metodzie lokalnej. Każda diagnostyka
  lokalna zapisuje dokładny start otrzymany z Deep w tej samej próbie.
- Pracowano na original. Nie stosowano ręcznych masek, korekt użytkownika
  ani dodatkowego wygładzania obrazów w finalnych próbach.

| Wejście | Klatki i rozmiar H × W | SHA-256 |
| --- | --- | --- |
| `data/MOVIE_4.mpp` | 364; po pominięciu pierwszych 2: 362 × 256 × 256 | `9d066676a3f947ed53610438051537eb3b30288aadc11d774ec52e509f31f961` |
| `data/MOVIE_8.mpp` | 84 × 512 × 512 | `a06ab5d34250ca564b11eb9da4e9ea65131b80d2a2e3ceaf09f0709569cdbde7` |
| REG-04 `translation.mpp` | 3 × 192 × 256 | `bd1baeecd2a6ea9c2eddbb91b79968928542202634fd2c1753fdd202ea509a95` |
| REG-04 `stationary-artifact.mpp` | 3 × 192 × 256 | `5b0923957aa657ccddcc85a5896b0e22adbd2e2b1af183bd96d3b8b1f777c1c2` |
| REG-05 `noisy.mpp` | 2 × 192 × 256 | `3255c722fb2f3d97b168deef42da51451071178505c1764e91ea4166c263f6ec` |

Finalny zestaw `LocalConsensusConfig`, jednakowy dla obu filmów i wzorców:

| Parametr | Wartość |
| --- | --- |
| Siatka / fragment | 4 × 4 / 32 px; minimalny rozmiar 16 px |
| Promień poszukiwania wokół startu Deep | 16 px |
| Minimalna tekstura w dwóch kierunkach | `1e-4` |
| Minimalne NCC | 0,1 |
| Minimalny kontrast maksimum względem tła korelacji | 3,5; mediana i `1,4826 × MAD` |
| Minimalny margines drugiego maksimum / promień wykluczenia | 0,025 / 3 px |
| Promień zgodności przesunięć | 1,5 px |
| Minimalne poparcie przestrzenne | 4 fragmenty w co najmniej 2 rzędach i 2 kolumnach |
| Próg konkurencyjnej grupy | 0,6 liczności grupy dominującej |
| Wersja ustawień | 1 |

Kontrast maksimum jest diagnostyką korelacji, a nie skalibrowanym
prawdopodobieństwem poprawności. Wynik udanej próby ma `manual_review`.
Brak poparcia kończy próbę odmową; metoda nie podstawia wtedy samego Deep.

## Wskazane pary pomiarów

XY oznacza przesunięcie klatki B do A w pikselach original. Zapis pary A→B
oznacza kolejność klatek, nie znak transformacji. MOVIE_4 pomija źródłowe 1 i 2:
źródłowe 3→4 to **bieżące 1→2**. Próby par wykonano niezależnie od pełnej serii.

| Film | Para bieżąca | Para źródłowa | Start Deep XY [px] | Lokalny XY [px] / odmowa | Poparcie |
| --- | --- | --- | --- | --- | --- |
| MOVIE_4 | 1→2 | 3→4 | (22.372, 13.478) | (19.960, 11.650) | 6/16 |
| MOVIE_4 | 31→32 | 33→34 | (-22.941, -31.578) | odmowa | 1/16 |
| MOVIE_4 | 118→119 | 120→121 | (31.435, 22.284) | odmowa | 1/16 |
| MOVIE_4 | 29→30 | 31→32 | (0.679, 7.235) | odmowa | 1/16 |
| MOVIE_4 | 35→36 | 37→38 | (0.094, -5.303) | odmowa | 2/16 |
| MOVIE_4 | 44→45 | 46→47 | (23.387, 8.111) | odmowa | 1/16 |
| MOVIE_4 | 45→46 | 47→48 | (0.364, 17.277) | odmowa | 1/16 |
| MOVIE_4 | 61→62 | 63→64 | (-0.341, -0.798) | odmowa | 1/16 |
| MOVIE_4 | 94→95 | 96→97 | (38.222, 9.234) | odmowa | 1/16 |
| MOVIE_4 | 95→96 | 97→98 | (-15.461, -6.952) | odmowa | 1/16 |
| MOVIE_4 | 96→97 | 98→99 | (-15.651, -6.577) | (-15.019, -6.226) | 4/16 |
| MOVIE_8 | 1→2 | 1→2 | (15.108, 0.428) | odmowa | 1/16 |
| MOVIE_8 | 16→17 | 16→17 | (-24.514, -32.170) | odmowa | 0/16 |
| MOVIE_8 | 56→57 | 56→57 | (-39.609, 7.039) | odmowa | 0/16 |

Na źródłowych 3→4 poprawka względem Deep wynosi (−2,411; −1,827) px;
poparcie obejmuje 6 fragmentów w 3 rzędach i 3 kolumnach. Na 98→99 poprawka
wynosi (+0,632; +0,351) px; 4 fragmenty w 3 rzędach i 3 kolumnach.
Wielkość tych zmian nie rozstrzyga, który wynik lepiej opisuje strukturę próbki.

Pozostałe pary mają niewystarczającą zgodną grupę i jej rozmieszczenie albo
brak kwalifikujących się dopasowań. Raporty JSON zachowują wszystkie fragmenty,
ich odrzucenia i wyniki korelacji także po odmowie całej pary.

## Pełne serie i zasoby

| Seria | Metoda / partia | Wynik | Czas estymacji i renderowania [s] | Eksport [s] | Peak Torch CUDA [MiB] |
| --- | --- | --- | --- | --- | --- |
| MOVIE_4, 362 klatki | Deep, pierwsza partia | kompletny, obszar 346 × 400 | 6,215 | 4,602 | 330,5 |
| MOVIE_4, 362 klatki | lokalna, finalna partia | odmowa bieżące 2→3 = źródłowe 4→5 | 0,593 | — | 330,5 |
| MOVIE_8, 84 klatki | Deep, pierwsza partia | kompletny, obszar 743 × 763 | 8,311 | 5,018 | 936,5 |
| MOVIE_8, 84 klatki | lokalna, finalna partia | odmowa bieżące/źródłowe 1→2 | 0,637 | — | 927,4 |

Pełny Deep pochodzi z wcześniejszej partii `/tmp/stmviewer-reg05-trials/`;
używa tych samych danych, wag i niezmienionego backendu Deep. Nie powtarzano
pełnego Deep w finalnej partii; powtórzono wszystkie 14 par Deep i lokalnych.
Finalny lokalny MOVIE_4 przeszedł pierwszą parę, a na następnej miał tylko
2 zgodne fragmenty w 1 rzędzie i 2 kolumnach. MOVIE_8 miał 1 zgodny fragment.
Nie zwrócono kompletnego aligned ani nie eksportowano niepełnego wyniku.

Czasy obejmują ładowanie modelu, estymację i renderowanie, z eksportem
mierzonym osobno; nie są izolowanym benchmarkiem. Czas do odmowy nie jest
czasem przetwarzania całego filmu. Peak RSS procesów finalnych pełnych prób:
1691,2 MiB dla MOVIE_4 i 1665,7 MiB dla MOVIE_8. RSS oznacza narastający
szczyt procesu, a peak Torch obejmuje tylko alokacje Torch na GPU.
Próby na 32 GB GPU nie potwierdzają pracy przy limicie 8 GB VRAM.

## Znane wzorce i ponowny odczyt MPP

| Wzorzec / urządzenie | Para | Znane XY [px] | Start Deep XY [px] | Lokalny XY [px] / odmowa |
| --- | --- | --- | --- | --- |
| REG-04 translation / CPU | 1→2 | (22.4, -13.25) | (22.285, -13.359) | (22.380, -13.229) |
| REG-04 translation / CPU | 2→3 | (-41, 24.6) | (-41.025, 24.517) | (-41.028, 24.608) |
| REG-04 stationary-artifact / CUDA | 1→2 | (22.4, -13.25) | (22.265, -13.426) | odmowa; 3 fragmenty, 2 rzędy, 3 kolumny |
| REG-04 stationary-artifact / CUDA | 2→3 | (-41, 24.6) | (-41.027, 24.506) | odmowa; 2 fragmenty, 1 rząd, 2 kolumny |
| REG-05 noisy / CUDA | 1→2 | (7, -5) | (7.138, -5.350) | (7.104, -5.026) |

CPU translation: obie metody utworzyły kompletny film 3 klatek. Metoda lokalna
miała odpowiednio 10 i 9 zgodnych fragmentów, z błędem poniżej 0,03 px na każdej
współrzędnej. Czas lokalny: 0,646 s + 0,153 s eksport; Deep: 0,659 s.
Oba eksporty MPP+JSON odczytano ponownie. Wszystkie wartości, NaN i geometria
218 × 298 są dokładnie zgodne z ponownym publicznym renderowaniem oryginałów
przy zapisanych XY. Sprawdzono również liczbę klatek i metadane metody.

Dodatkowo sprawdzono pełny `translation.mpp` z generatora REG-05 użytego w instrukcji
manualnej: na CPU z rzeczywistymi wagami lokalne XY wyniosły (13,216; −8,498)
i (−19,767; 17,771) przy znanych (13,25; −8,5) i (−19,75; 17,75), po 11 zgodnych
fragmentów dla obu par. Próba na kodzie `75eb70f` ukończyła wszystkie 3 klatki
i eksport MPP+JSON o obszarze 211 × 277 w 0,791 s + 0,113 s eksportu;
raport: `/tmp/reg05-manual-translation/report.json`.

REG-05 noisy: niezależny szum, udział sygnału w wariancji 0,3. Lokalny wynik
ma 13 fragmentów w 4 rzędach i 4 kolumnach; błąd około (+0,104; −0,026) px.
To dodatkowa próba rzeczywistych wag na znanym wzorcu. Dwa przykłady
numerycznej poprawy względem Deep nie potwierdzają przewagi na pomiarach STM.

Wzorzec nieruchomych pasów z REG-04 przy finalnych ustawieniach odmawia obu
parom. Dawny sukces pierwszej pary na starszych ustawieniach nie obowiązuje
dla finalnej metody. Nie uzyskano lokalnego filmu tego wzorca.

## Rozdzielenie etapów i ograniczenia

Pierwsza partia z surowym progiem NCC 0,45 i bez warunku kontrastu maksimum
dała **0/14** wyników lokalnych. Obniżenie samego progu oraz wygładzanie były
oddzielnymi próbami diagnostycznymi, bez zmiany aplikacji w tych próbach.
Finalna metoda używa opisanych wyżej NCC 0,1, kontrastu 3,5 i marginesu 0,025;
jej **2/14** pochodzi z nowego wykonania, a nie z mieszania najlepszych wyników
różnych ustawień. Po ustaleniu finalnego zestawu nie wykonano kolejnego
przeszukiwania parametrów ani ustawień osobnych dla MOVIE_4 i MOVIE_8.

Gotowość do ręcznej oceny oznacza możliwość obejrzenia dwóch zaakceptowanych
par, diagnostyki odmów oraz wzorców. Bieżąca metoda nie daje kompletnego
automatycznego dopasowania tych dwóch trudnych filmów. Nie stwierdzamy poprawy
fizycznego dryfu, odporności na wszystkie zakłócenia ani przewagi nad Deep.
Manualne zatwierdzenie REG-05, Windows, VLC i stanowisko 8 GB VRAM pozostają
poza zakresem tej próby. Status ticketu określa [karta odbioru](reviews/REG-05.md).

## Artefakty i odtwarzanie

Dane i duże wyniki pozostają lokalne, poza Git:

- Finalne raporty: `/tmp/stmviewer-reg05-final/summary.json`, `summary.md`,
  `movie4-pairs/report.json`, `movie8-pairs/report.json`,
  `movie4-full/report.json`, `movie8-full/report.json`.
- Wzorce: `translation-cpu/report.json`, `stationary-artifact-cuda/report.json`,
  `noisy-cuda/report.json`; kontrola eksportu: `mpp-roundtrip.json`.
- Lokalny MPP do obejrzenia:
  `/tmp/stmviewer-reg05-final/translation-cpu/deep_local_consensus-aligned.mpp`
  i towarzyszący `.stmviewer.json`.
- Pełne bazowe Deep: `/tmp/stmviewer-reg05-trials/movie4-full/`
  i `/tmp/stmviewer-reg05-trials/movie8-full/`, każdy z `report.json` i MPP+JSON.
- `code-sha256.json` zachowuje hashe czterech modułów w momencie finalnych prób;
  ich zawartość nie zmieniła się podczas tej partii.

Przykład powtórzenia 11 niezależnych par MOVIE_4, w aktywnym `netcat`,
z katalogu głównego Viewer; katalog wynikowy musi być nowy:

```bash
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=4 PYTHONPATH=. \
python tests/stmviewer/diagnostics/local_consensus_trial.py \
  data/MOVIE_4.mpp /tmp/nowa-proba-reg05-movie4 \
  --weights /sciezka/do/loftr_outdoor.ckpt --device cuda --drop-first 2 \
  --pair 2 --pair 32 --pair 119 --pair 30 --pair 36 --pair 45 \
  --pair 46 --pair 62 --pair 95 --pair 96 --pair 97
```

MOVIE_8 używa `--pair 2 --pair 17 --pair 57`, bez `--drop-first`.
Bez `--pair` narzędzie wykonuje pełną serię i zatrzymuje metodę na pierwszej
odmowie. `--export` zapisuje tylko kompletny wynik pełnej serii.
Domyślnie porównuje Deep i metodę lokalną; `--method deep_local_consensus`
ogranicza wybór do lokalnej, a `--device cpu` uruchamia Deep na CPU.
Kod zakończenia 1 przy odmowie jest spodziewanym wynikiem eksperymentu;
szczegóły pozostają w `report.json`.
