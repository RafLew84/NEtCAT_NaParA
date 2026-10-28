# Rejestracja MOVIE_4 i MOVIE_8 — rozpoznanie

Data: 2026-10-28. Gałąź **`viewer/registration-difficult-movies`**, utworzona
z `viewer/start` na commicie `26f5538`. Ten etap to rozpoznanie problemu
i odtwarzalne próby. Kod rejestracji aplikacji pozostaje bez zmian.

Użytkownik zgłasza silne zakłócenia i tearing oraz podejrzenie dopasowywania
zakłóceń zamiast struktur próbki. To obrazy **skaningowego mikroskopu tunelowego**.
Dryf może zmieniać kierunek. Ani zmiana znaku, ani duże przesunięcie, ani
powiększony obszar aligned nie stanowią same w sobie dowodu błędu.
Nie znamy kierunków skanowania kolejnych klatek; nie przyjmujemy trace/retrace
jako wyjaśnienia naprzemiennych estymat.

## Dane

| Plik | Klatki | Wymiary W×H | Bajty | Pole z nagłówka |
| --- | ---: | --- | ---: | --- |
| `data/MOVIE_4.mpp` | 364 | 256×256 | 190 851 832 | 62,6114×62,6114 nm |
| `data/MOVIE_8.mpp` | 84 | 512×512 | 176 165 885 | 16,1554×16,1554 nm |

W obu filmach wszystkie próbki są skończone, kanał to topo, jednostka nm.
Metadane nagłówka nie były niezależnie kalibrowane. SHA-256:

- MOVIE_4: `9d066676a3f947ed53610438051537eb3b30288aadc11d774ec52e509f31f961`.
- MOVIE_8: `a06ab5d34250ca564b11eb9da4e9ea65131b80d2a2e3ceaf09f0709569cdbde7`.

Wszystkie 363 i 83 pary sprawdzono obecnymi backendami, bez materializacji
aligned. Pętla diagnostyczna kontynuowała po błędach, aby zbadać resztę danych;
aplikacja przerwałaby próbę przy pierwszym błędzie. Dlatego dla takich metod
nie podajemy fikcyjnego kompletnego wyniku. Jednostki przesunięć: piksele;
XY określa przesunięcie **nakładane na następną klatkę**, aby dopasować ją
do poprzedniej, a nie kierunek fizycznego ruchu próbki.

## Wyniki obecnych metod

„Niepewne” oznacza status `low_confidence` backendu. „OK” nie jest niezależnym
potwierdzeniem dopasowania struktur. Wymiary poniżej to prognoza obszaru
**W×H** z sumowania estymat, nie kryterium jakości ani materializowany film.

| Film / metoda | OK | Niepewne | Błędy | Największa norma przesunięcia pary | Prognozowane W×H |
| --- | ---: | ---: | ---: | ---: | --- |
| MOVIE_4 Phase | 19 | 344 | 0 | 125,95 px | 489×1367 |
| MOVIE_4 Tile+RANSAC | 41 | 322 | 0 | 15,00 px | 260×381 |
| MOVIE_4 ECC | 275 | 88 | 0 | 129,32 px | 603×1382 |
| MOVIE_4 Optical Flow | 191 | 172 | 0 | 15,71 px | 627×352 |
| MOVIE_4 Deep Matcher | 147 | 215 | 1 | 60,49 px | brak pełnego wyniku |
| MOVIE_8 Phase | 0 | 83 | 0 | 273,83 px | 1773×1018 |
| MOVIE_8 Tile+RANSAC | 0 | 83 | 0 | 1,00 px | 512×513 |
| MOVIE_8 ECC | 43 | 35 | 5 | — | brak pełnego wyniku |
| MOVIE_8 Optical Flow | 27 | 56 | 0 | 28,74 px | 747×637 |
| MOVIE_8 Deep Matcher | 27 | 56 | 0 | 70,72 px | 763×743 |

Tile+RANSAC zwraca dokładnie (0,0) dla 81/83 par MOVIE_8. To obserwacja,
a nie argument za skutecznością: małe przesunięcie także może być błędne.

Deep Matcher MOVIE_4 zatrzymuje aplikację na **2→3**:
`Only 1 inlier feature matches; need at least 4.`. Potwierdzono dwa razy przez
publiczne `register_series` na pierwszych trzech klatkach. ECC MOVIE_8 ma
błędy na 2→3, 20→21, 24→25, 37→38 i 56→57; aplikacja zatrzyma się na 2→3.
To dodatkowe obserwacje, odrębne od zgłoszonego niedopasowania struktur.

Deep Matcher używał istniejących lokalnych wag LoFTR outdoor na CUDA:0 / RTX 5090,
bez pobierania i bez zamiany na CPU. Pełne estymaty zajęły 10,92 s / 6,96 s,
szczyt alokacji GPU 347 / 982 MB. Te czasy są pomocnicze, nie benchmark stanowiska.

## Konkretny reproduktor: MOVIE_8, klatki 1→2

Trzy przestrzennie oddzielne fragmenty 80×80, wskazane na strukturach obrazu,
porównano na surowych wartościach metodą lokalnego dopasowania wzorca NCC:

| Prostokąt referencji `(x0,y0,x1,y1)` | Przesunięcie XY | NCC przy (0,0) | NCC przy (+14,0) |
| --- | --- | ---: | ---: |
| (180,160,260,240) | (+14,0) | 0,577 | 0,833 |
| (350,320,430,400) | (+15,0) | 0,442 | 0,659 |
| (90,330,170,410) | (+14,0) | 0,264 | 0,602 |

Obecny Phase zwraca **(−0,10; +0,05)**: rozbieżność z lokalnym konsensusem
wynosi **14,10 px**. Reproduktor sprawdza najpierw zgodność fragmentów i wzrost
NCC >0,15, następnie wymaga od Phase odległości ≤3 px od tego konsensusu.
Dwa uruchomienia pierwotnego reproduktora dały identyczny RED, około 0,25 s
łącznie z odczytem danych (przed dodaniem weryfikacji SHA-256).

To lokalne odniesienie z analizy obrazów, nie niezależny fizyczny pomiar dryfu
ani prawda referencyjna całego filmu. Czwarty sprawdzony fragment wskazywał
(+19,+2), co dodatkowo ogranicza wniosek o jednym przesunięciu całej klatki.

## Eksperymenty rozdzielające hipotezy

Przed próbami rozdzielono wpływ normalizacji fazowej, cienkich poziomych
zakłóceń i zgodności przesunięć między fragmentami. Każdy wariant poniżej
zmienia jedną rzecz względem oryginalnego Phase; nie łączono filtrów.
Dotyczy wyłącznie pary 1→2 MOVIE_8. Wartości oryginalnego filmu nie były zmieniane.

| Wariant | Wynik XY | Odległość od lokalnego (+14,0) |
| --- | --- | ---: |
| Obecny Phase | (−0,10; +0,05) | 14,10 px |
| Bez normalizacji fazowej, surowe dane | (+13,55; +0,25) | **0,51 px** |
| Odjęcie mediany każdego wiersza | (−0,10; +0,05) | 14,10 px |
| Mediana pionowa 3×1 | (0; −0,15) | 14,00 px |
| Gauss pionowy σY=2, σX=0 | (−79,90; 0) | 93,90 px |
| Gauss izotropowy σ=2 | (0; +1,35) | 14,06 px |
| Ograniczenie do percentyli 1–99 | (0; −0,10) | 14,00 px |
| Okno Hanna | (−86,25; −0,05) | 100,25 px |

Gauss izotropowy otrzymał nawet status **OK**, mimo niedopasowania do wskazanych
struktur. Potwierdza to potrzebę oceny dopasowania poza samą etykietą backendu;
nie dowodzi nieskuteczności wszystkich możliwych filtrów.

Następnie wariant bez normalizacji sprawdzono na wszystkich **446 parach**:

| Film | Mediana / p95 / maks. normy przesunięcia | Prognozowane W×H | Błędy obliczeń |
| --- | --- | --- | ---: |
| MOVIE_4 | 5,20 / 42,91 / 124,65 px | 368×1213 | 0 |
| MOVIE_8 | 12,25 / 50,98 / 83,91 px | 780×754 | 0 |

Mniejszy obszar lub mniejsze skoki nie dowodzą poprawności. Pozostałe pary nie
mają jeszcze niezależnie ocenionych struktur odniesienia, a MOVIE_4 nadal daje
bardzo odmienne estymaty. To nie uzasadnia domyślnej zmiany dla obu filmów.
Dodatkowo obecny backend liczy quality/status z normalizowanego widma nawet przy
`normalization=None`; nie uznajemy tych etykiet za zweryfikowaną ocenę nowego wariantu.

## Wniosek i granica etapu

Potwierdzono rozbieżność istniejącego dopasowania z wybranymi strukturami,
nie mechanizm „dopasowywania zakłóceń” we wszystkich metodach i klatkach.
Zmiana normalizacji pomaga w jednym odtwarzalnym przypadku, lecz nie jest
potwierdzoną naprawą obu filmów. Domyślne algorytmy pozostały bez zmian.

Dalsza walidacja powinna objąć kilka oddzielnych struktur w kilku parach obu
filmów. Należy oceniać zgodność dopasowania w części wspólnej, dopuszczając
dryf w dowolnym kierunku i nie odrzucając wyniku tylko z powodu dużego kroku.
Warto następnie badać zgodność lokalnych estymat i rozpoznawanie wyniku
niejednoznacznego. To kierunek dalszych prób, nie już sprawdzony nowy algorytm.
Tearing wymagający różnych przesunięć różnych części jednej klatki trzeba
odróżnić od jej globalnego XY; pojedyncza translacja nie opisuje takiej deformacji.

Kierunki dalszej pracy i ich podstawy opisano w
[przeglądzie metod poprawy rejestracji](registration-improvement-options.md).

## Odtworzenie

Środowisko `netcat`, katalog repo Viewera. Wejścia muszą pozostać lokalne.
Nowe skrypty nie są testami zbieranymi przez zwykły pytest. Nie używaj `python -O`.

```bash
export PYTHONDONTWRITEBYTECODE=1
export PYTHONPATH=.
export OPENBLAS_NUM_THREADS=1
python tests/stmviewer/diagnostics/registration_baseline.py data/MOVIE_4.mpp data/registration-repeat-4
python tests/stmviewer/diagnostics/registration_baseline.py data/MOVIE_8.mpp data/registration-repeat-8
python tests/stmviewer/diagnostics/registration_baseline.py data/MOVIE_8.mpp data/registration-repeat-none --method phase_no_normalization
python tests/stmviewer/diagnostics/repro_movie8_phase.py data/MOVIE_8.mpp
python tests/stmviewer/diagnostics/repro_movie8_phase.py data/MOVIE_8.mpp --normalization none
```

Przedostatnie polecenie **celowo kończy się AssertionError** na obecnej produkcji;
ostatnie przechodzi dla tej pary. Reproduktor sprawdza SHA-256 wejścia.
Baseline wymaga nowego katalogu wyjściowego. Opcja `--max-pairs 2` służy wyłącznie
krótkiemu smoke; raport oznacza niepełny przebieg i nie podaje całego aligned.

Deep Matcher uruchamia się jawnie: `--method deep_matcher_translation --weights
/ścieżka/do/loftr_outdoor.ckpt --device cuda`. Pełna lokalna ścieżka wag jest
w [instrukcji modelu](deep-matcher-manual.md). Narzędzie nie pobiera modelu.

Artefakty rozpoznania zachowano lokalnie w **`data/registration-difficult-movies/`**:
manifest wejść, `movie4/`, `movie8/`, `deep/`, `normalization/` z pełnymi wynikami,
reproduktorami, logami oraz figurami oryginalnych klatek i estymat.
Wykresy obrazów używają niezależnego zakresu percentyli 1–99 dla czytelności;
zmienia to wyłącznie prezentację. Figury nie stanowią wyniku rejestracji.

Wykonano smoke zapisanych CLI: cztery CPU i rzeczywisty Deep Matcher/CUDA na
pierwszych dwóch parach MOVIE_4, Phase/bez normalizacji na dwóch parach MOVIE_8;
sprawdzono celowy RED i porównawczy GREEN reproduktora. Pełne wyniki powyżej
pochodzą z wcześniejszych skryptów diagnostycznych zachowanych z artefaktami.
Sprawdzono Ruff, odnośniki, limit plików i `git diff --check`. Nie powtarzano
pełnego pytest ani ręcznych testów GUI: kod aplikacji nie został zmieniony.
To nie zamyka zależności integracyjnej ticketu 19 ani odbiorów platform 20/21.
