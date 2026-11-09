# SD-V4-26 — wyniki ograniczonej próby

2026-11-09. [Protokół zapisany przed próbą](experiment-26.md), commit `d949bfe`.
Wykonano 152 warianty: 11 kontroli i 8 klatek TTMAPP × 8 ustawień; bez błędów wykonania.
Jedna adaptacja `gibou_fedkiw_features_v1`, te same pomiary co `geometry_tolerances_v1`.
Dane lokalne: `.scratch/stmdomains-ui-26/report.json`; pełne odmowy, hashe wejść,
konfiguracje, stan solvera i czasy są w JSON. Wyniki poniżej opisują próbę, nie accuracy.

## Wniosek

Nie wykazano przewagi detekcji domen nad Geometrią. Level set 0,25 daje na
TTMAPP te same liczby domen i przypisanych molekuł. W części kontroli różni
się wsparcie maski i liczba przyjętych centrów, ale problemy z pomiarami,
barierami oraz granicą fazową pozostają. Nie rekomendujemy zastąpienia
Geometrii ani metody bazowej tą adaptacją. Funkcja pozostaje eksperymentem
do porównywania na obrazie. Kolejny krok badawczy wymaga poprawy pomiarów
i oceny barier/cech fazowych, nie samego zwiększania siły wygładzania.

## Kontrole

Komórka: **domeny / przypisane centra**. Level set: siła 0,25, limit 120.
„Bez barier” oznacza minimum długości 100 NN; sprawdzono pustą maskę.
Wszystkie inne parametry pozostają wspólne.

| Kontrola | Referencja | G domyślne | LS domyślne | G bez barier | LS bez barier |
|---|---:|---:|---:|---:|---:|
| regular | 1 | 7 / 63 | 7 / 63 | 1 / 63 | 1 / 63 |
| two_orientations | 2 | 1 / 19 | 1 / 19 | 2 / 40 | 2 / 40 |
| gradual_turn | bez ostrej granicy | 0 / 0 | 0 / 0 | 3 / 65 | 3 / 65 |
| phase_jump | 2 | 0 / 0 | 0 / 0 | 3 / 67 | 3 / 67 |
| missing_centers | 1 | 3 / 27 | 3 / 46 | 1 / 56 | 1 / 56 |
| gap | 2 | 0 / 0 | 1 / 8 | 2 / 36 | 2 / 36 |
| noise | 0 | 0 / 0 | 0 / 0 | 0 / 0 | 0 / 0 |
| rows_1d | 0 | 0 / 0 | 0 / 0 | 0 / 0 | 0 / 0 |
| sparse | brak pomiaru | 0 / 0 | 0 / 0 | 0 / 0 | 0 / 0 |
| small_domain | 2 | 8 / 76 | 8 / 76 | 2 / 76 | 2 / 76 |
| scan_artifact | 1 | 4 / 47 | 5 / 60 | 1 / 63 | 1 / 63 |

Przy domyślnych barierach oba warianty dzielą regularną sieć na 7 obszarów,
pomijają jedną z dwóch orientacji i całkowicie pomijają obie domeny skoku fazy.
Level set na luce wykrywa tylko jeden obszar z 8 centrami; to nadal pominięcie
drugiego obszaru. Artefakt skanu daje 5 domen zamiast 1 (Geometria: 4).
Mała wyspa ma 25 centrów; obie metody zachowują 13 jej członków, ale duży
obszar jest rozdrobniony przez bariery. Same większe liczby przypisań w
brakujących centrach i artefakcie nie potwierdzają poprawnej granicy.

Bez barier obie metody odtwarzają liczbę regionów regularnej sieci, dwóch
orientacji, brakujących centrów, luki, małej wyspy i artefaktu. Skok fazy
pozostaje błędny: 3 domeny, 1 błędne scalenie, oba referencyjne regiony
rozdrobnione. Nie wolno traktować zerowego wyniku z barierami jako sukcesu.
Szum i rzędy 1D nie tworzą domen w żadnej konfiguracji. Granice nie mają
zwalidowanej referencji rastrowej, dlatego nie podajemy błędu konturu.

## TTMAPP259–266

Brak niezależnej referencji: liczby są opisem wyników, bez oceny poprawności
granic ani wniosków o innych materiałach. Jedna domena na każdej klatce.
Poniższe czasy dotyczą samej segmentacji jednego wykonania (bez pomiaru cech).

| Klatka | Aktywne centra | G przypisane | LS 0,25 przypisane | G czas [s] | LS czas [s] |
|---|---:|---:|---:|---:|---:|
| 259 | 312 | 32 | 32 | 0.033 | 0.286 |
| 260 | 301 | 38 | 38 | 0.035 | 0.189 |
| 261 | 300 | 33 | 33 | 0.033 | 0.242 |
| 262 | 300 | 40 | 40 | 0.033 | 0.361 |
| 263 | 308 | 40 | 40 | 0.033 | 0.172 |
| 264 | 298 | 35 | 35 | 0.033 | 0.395 |
| 265 | 300 | 41 | 41 | 0.033 | 0.315 |
| 266 | 309 | 35 | 35 | 0.032 | 0.335 |

Wspólny pomiar cech: 1.74–1.85 s/klatkę. Brak dowodu przyspieszenia.
Po zsumowaniu wystąpień centrów w ośmiu klatkach (nie niezależnych molekuł):
- `geometry_not_2d`: 2064.
- `levelset_no_component`: 70.

Wszystkie siły 0 / 0,25 / 1 dały te same liczniki domen i członków
na TTMAPP; maski mogły się różnić. Przy 0,25 zmieniło się względem inicjalizacji
0–4 piksele mapy regionów modelu na klatkę. To nie mierzy błędu granicy.
Stan `stable_partition` oznacza stabilny podział przez dwa bloki; nie stanowi
dowodu zbieżności PDE ani zgodności z fizycznymi domenami.

## Odtworzenie

```bash
conda activate netcat
python -m stmdomains.tools.levelset_trial .scratch/stmdomains-ui-26-repeat --source data/TTMAPP/detection_full.moltrack.json
```

Wersje środowiska: NumPy 2.2.5, SciPy 1.15.2.
Źródło TTMAPP: `/home/rlew/projekty/NEtCAT-domains/data/TTMAPP/detection_full.moltrack.json`.
SHA256 zapisu wejściowego: `d0c4cb999bede28edb5dfd18ddbe146054711382f1c78363055be2330b3cdd2e`.
Hash konkretnego obrazu i centrów znajduje się przy każdym wariancie JSON.
Gotowe dane do GUI i odbiór funkcji: [acceptance-26.md](acceptance-26.md).
