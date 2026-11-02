# REG-13: LightGlue + SuperPoint — wyniki prób

Data: 2026-11-02. Baza implementacji: `d86baba`; pomiary wykonano na roboczym
adapterze REG-13, zapisanym następnie w `243f83a`.
`final-source-manifest.json` zachowuje SHA-256 adaptera, procesu, workera,
konsensusu oraz baz Deep/RoMa z tego commita. Pierwotne raporty par pozostawiają
ówczesny HEAD i dirty state; samo `d86baba` nie odtwarza nowego adaptera.
Wersje modeli, źródła i ustawienia zachowują raporty lokalne.
**Odbiór manualny użytkownika pozostaje niewykonany.**

W sprawdzonej konfiguracji LightGlue dostarczył wynik dla **12 z 18 par STM**,
lecz nie utworzył kompletnego filmu MOVIE_4 ani MOVIE_8: odmowy rozłączyły
oba grafy. To ograniczenie użyteczności metody na tych danych, a nie zaliczenie
jakości przez sam poprawny przebieg programu. Progi pozostawiono zgodne
z konsensusem v2; brakujące pomiary nie zostały zastąpione zerami.

## Przebieg i odtwarzalność

[Harness](../../../tests/stmviewer/diagnostics/lightglue_trial.py) wykonał:

- 18 tych samych par × Deep outdoor, RoMa v2 Turbo i LightGlue/SuperPoint
  = **54 wyniki prób**, z zachowaniem wszystkich odmów;
- 9 tych samych par wzorcowych × 3 metody = 27 prób znanego ruchu i zakłóceń;
- pełne próby LightGlue w łańcuchu oraz grafie z oknem 3 dla obu filmów;
- zapis i ponowny odczyt obu niekompletnych kandydatów grafu, bez promowania
  ich do aktywnego aligned;
- sześć tablic nakładek obejmujących wszystkie 18 par i trzy metody;
- oddzielną kompletną próbę CPU na `cpu.mpp`: łańcuch, LS/Huber, zastosowanie,
  ręczna korekta, sesja, MPP oraz AVI z poprawionych sesji.

Pilotaż par, wzorce i oba pełne STM używały CUDA na RTX 5090.
Oddzielna próba kompletnego cyklu na trzyklatkowym `cpu.mpp` użyła CPU.
MOVIE_4: źródłowe 3–364, 362 klatki 256 × 256; MOVIE_8: 84 klatki 512 × 512.
Numery w tabelach są **bieżące, po usunięciu pierwszych dwóch klatek MOVIE_4**.
Hash źródła MOVIE_4:
`9d066676a3f947ed53610438051537eb3b30288aadc11d774ec52e509f31f961`;
MOVIE_8: `a06ab5d34250ca564b11eb9da4e9ea65131b80d2a2e3ceaf09f0709569cdbde7`.

[Przygotowane zasoby](lightglue-environment.md) zachowują kod i oba checkpointy.
Konfiguracja adaptera: SuperPoint maksymalnie 2048 punktów, natywny rozmiar
`resize=None`, jeden kanał, min/max float32, bez paddingu; LightGlue 9 warstw,
próg 0,1, adaptacja głębokości 0,95 i szerokości 0,99, FlashAttention,
`mp=False`. Wagi/wejście FP32, attention CUDA może wewnętrznie używać FP16.
Punkty są już w układzie original. Bez doprecyzowania ECC i bez deformacji.

RoMa: Turbo, 1000 próbek, seed 20261102, siatka 8 × 8 i konsensus v2.
Deep: dotychczasowy LoFTR outdoor i jego historyczny konsensus. Porównanie
z Deep dotyczy całego estymatora; nie izoluje samej sieci. Nie stroiliśmy
ustawień osobno dla klatek. Gamma/zoom nie były wejściem obliczeń.

Artefakty: `/home/rlew/projekty/NEtCAT-viewer/data/registration-reg13/`.
Pliki `pairs-{deep,roma,lightglue}.json` i `patterns-{deep,roma,lightglue}.json`
zawierają konfigurację, provenance, hash źródeł i par, XY, diagnostykę,
czasy i zasoby. Wzorce z manifestem są w `fixtures/`.

## Te same pary STM

| Metoda | Wynik | Odmowa | Statusy otrzymanych wyników |
| --- | ---: | ---: | --- |
| Deep outdoor | 18/18 | 0 | 2 `ok`, 16 `low_confidence` |
| RoMa Turbo | 18/18 | 0 | 12 `manual_review`, 6 `low_confidence` |
| LightGlue + SuperPoint | 12/18 | 6 | 2 `manual_review`, 10 `low_confidence` |

W sześciu odmowach LightGlue było jedynie 2–3 zgodnych wektorów przy
wymaganych 4, mimo 11–32 wstępnych korespondencji. Są to lokalne braki
poparcia, nie błąd instalacji lub wyjątek procesu.

| Film i para | Deep XY [px] | RoMa XY [px] | LightGlue XY [px] |
| --- | --- | --- | --- |
| MOVIE_4 1→2 | (22.37; 13.48) | (19.73; 11.63) | odmowa |
| MOVIE_4 31→32 | (-22.94; -31.58) | (-22.92; -32.05) | odmowa |
| MOVIE_4 118→119 | (31.43; 22.28) | (38.51; 24.67) | (32.00; 22.00) |
| MOVIE_4 29→30 | (0.68; 7.23) | (13.86; -2.93) | odmowa |
| MOVIE_4 35→36 | (0.09; -5.30) | (-12.37; -4.58) | odmowa |
| MOVIE_4 44→45 | (23.39; 8.11) | (28.50; 11.71) | (26.00; 11.50) |
| MOVIE_4 45→46 | (0.36; 17.28) | (-29.02; -10.34) | odmowa |
| MOVIE_4 61→62 | (-0.34; -0.80) | (10.27; 3.68) | (0.00; -1.00) |
| MOVIE_4 94→95 | (38.22; 9.23) | (41.81; 12.80) | odmowa |
| MOVIE_4 95→96 | (-15.46; -6.95) | (-29.29; -14.62) | (-19.00; -9.00) |
| MOVIE_4 96→97 | (-15.65; -6.58) | (-15.08; -6.38) | (-16.00; -7.00) |
| MOVIE_4 160→161 | (-1.50; 1.94) | (-3.03; 3.79) | (-2.00; 5.00) |
| MOVIE_4 250→251 | (-1.60; 4.54) | (-2.05; 3.99) | (-3.00; 3.00) |
| MOVIE_8 1→2 | (15.11; 0.43) | (16.89; 0.51) | (14.00; 1.00) |
| MOVIE_8 16→17 | (-24.51; -32.17) | (-26.34; -31.20) | (-25.00; -29.00) |
| MOVIE_8 56→57 | (-39.61; 7.04) | (-37.91; 4.06) | (-40.00; 4.00) |
| MOVIE_8 25→26 | (15.05; 0.27) | (15.06; 0.41) | (13.00; 0.00) |
| MOVIE_8 70→71 | (-7.83; -31.15) | (-7.49; -29.70) | (-10.00; -30.00) |

Zbieżność albo rozbieżność tych liczb nie ustala prawdziwego dryfu.
Na przykład 61→62 ma LightGlue (0; −1), blisko Deep, ale bardzo różni się
od RoMa. Przy odmowach 29→30 i 35→36 nowa metoda nie dostarcza poprawki,
której brak zgłaszał użytkownik. Nie wyciągamy z tego wniosku o przewadze
jednego wariantu na pozostałych fragmentach filmu.

Oglądnięto wygenerowane nakładki m.in. MOVIE_4 35–62 i 94–97 oraz MOVIE_8
1→2, 16→17, 56→57 i 25→26. Pozostają lokalne czerwone/turkusowe rozbieżności
oraz pasy. Na MOVIE_4 96→97 i wybranych parach MOVIE_8 wyniki są zbliżone,
ale te tablice nie rozstrzygają rankingu dokładności struktur.
Ocena została zapisana jako **nierozstrzygalna**, nie jako poprawa jakości.
To oględziny artefaktów przez agenta, nie manualny odbiór programu przez użytkownika.

Tablice `movie_4-pairs-1.png` do `-4.png` oraz `movie_8-pairs-1.png` i `-2.png`
mają wspólne pole klatki odniesienia i min/max obu oryginałów, gamma 1.
Czerwony oznacza odniesienie, turkusowy klatkę przesuwaną; biel to brak wspólnych
próbek po przesunięciu. Ręczna ocena powinna użyć również przełączania klatek
w programie, przy stałym zoomie, według [protokołu](manual-protocol.md).

## Znany ruch i artefakty

| Przypadek | Deep outdoor | RoMa Turbo | LightGlue + SuperPoint |
| --- | --- | --- | --- |
| `cpu.mpp`, maksymalny błąd osi z dwóch par | 0,298 px | 0,006 px | 0 px |
| Translacja subpikselowa, dwie pary | maks. 0,056 px | maks. 0,023 px | dwie odmowy: 2 i 1 korespondencja |
| Silny szum, maksymalny błąd osi | 0,350 px | 0,215 px | odmowa: 2/10 zgodnych wektorów |
| Nieruchomy pas, właściwy ruch sceny (7; −5) | około (0; 0) | około (0; −0,17) | (0; 0), `low_confidence` |
| Tylko jeden pas tekstury, właściwe XY (7; 0) | (7,02; −0,05) | (6,99; −0,01) | (7; 0), `low_confidence` |
| Różny ruch górnej/dolnej połowy | wybór górnej części | wybór górnej części, ostrzeżenie | odmowa |
| Tekstura okresowa, wiele równoważnych przesunięć | błąd braku dopasowań | inna gałąź okresowa, około (−13; −10) | odmowa |

**Żadna z trzech metod nie odzyskała ruchu sceny w obecności silnego
nieruchomego pasa.** Ostrzeżenie LightGlue pomaga rozpoznać słabe poparcie,
ale nie naprawia XY. Odmowa na obrazie okresowym nie jest pomiarem zerowego
przesunięcia; wynik RoMa nie rozstrzyga pomiędzy równoważnymi okresami.

Ten wariant SuperPoint wykrywa punkty na siatce pikselowej; mediana wektorów
może więc dawać całkowite lub połówkowe XY. Nie dodano nieuzgodnionego
etapu poprawiania dokładności subpikselowej. Dokładność łatwego `cpu.mpp`
nie dowodzi odporności na STM ani lepszej dokładności przesunięcia.

## Pełne filmy

| LightGlue, okno grafu 3 | MOVIE_4 | MOVIE_8 |
| --- | ---: | ---: |
| Łańcuch | odmowa 1→2 | odmowa 6→7 |
| Liczba badanych relacji grafu | 1080 | 246 |
| Brak pomiaru | 315 | 46 |
| `low_confidence` | 512 | 159 |
| `manual_review` | 253 | 41 |
| Składowe grafu | 41 | 3 |
| Kompletny wynik LS | nie | nie |
| Huber | `disconnected`, 0 iteracji | `disconnected`, 0 iteracji |
| Czas grafu z ładowaniem i LS | 11,09 s | 5,12 s |
| W tym RPC modelu + transport | 8,72 s | 2,98 s |
| Konsensus | 0,68 s | 0,53 s |
| LS | 0,007 s | 0,002 s |
| Próbkowany szczyt RAM drzewa procesu | 1914 MiB | 1949 MiB |
| Próbkowane użycie VRAM według sterownika | 794 MiB | 1100 MiB |

W obu przypadkach zachowano i ponownie otwarto `graph-candidate.stmsession`
w katalogach `movie-movie_4/` oraz `movie-movie_8/`. Zapis nie tworzy aktywnego
aligned. Nie można zastosować ani wyeksportować niekompletnego LS/Hubera jako
pełnego filmu. Próby eksportu na kompletnym krótkim wzorcu opisano poniżej;
nie przypisujemy ich tym dwóm odmówionym filmom.

Dla porównania wykorzystano **historyczne** pełne grafy Deep z REG-08e oraz
RoMa z REG-11, bez ich ponownego przeliczania w tym zadaniu. Manifest
`historical-baselines.json` zachowuje źródłowe raporty, ich SHA i konfigurację.
Sprawdzono zgodność wejść/usunięć, wag i parametrów z bieżącym pilotażem;
provenance RoMa jest identyczne. Identyfikatory kodu tych wcześniejszych
prób pozostają historyczne, a czasy nie są wspólnym benchmarkiem sprzętu.

| Historyczna baza | MOVIE_4 | MOVIE_8 |
| --- | --- | --- |
| Deep, okno 3 | LS kompletny; 3 braki; Huber limit iteracji | LS kompletny; 0 braków; Huber zbieżny |
| RoMa Turbo, okno 3 | LS kompletny; 0 braków; Huber limit 200 iteracji | LS kompletny; 1 brak; Huber limit 200 iteracji |

W sprawdzonej konfiguracji LightGlue ma zatem **gorszą kompletność** niż obie
bazy. Nie zastępuje ich w pracy nad tymi filmami. Nie jest to dowód gorszej
precyzji każdej pary: część par nie ma wyniku, a niezależne XY STM nie są znane.

## Kompletny krótki film: zastosowanie i eksport

Osobno wykonano pełny cykl na rzeczywistym modelu **CPU**, z trzema klatkami
80 × 80 pliku `cpu.mpp`. Łańcuch oraz LS są kompletne; Huber uzyskał
zbieżność po jednej iteracji. Gotowy łańcuch i niezastosowany graf zapisano
i odczytano, sprawdzając tożsamość pikseli, diagnostyki i aktywnego wyniku.

Dla LS i Hubera zastosowano wynik, dodano przez publiczne API ręczną korektę
+1 px Y, zapisano poprawioną sesję i MPP, sprawdzono ponowny odczyt pikseli,
XY oraz zapis korekty. Przy wariancie Hubera przywrócenie poprzednika
odtworzyło wcześniejszy wynik. Jest to automatyczna próba operacji ręcznej,
nie klikanie przez użytkownika.

Z ponownie otwartych poprawionych sesji zapisano po jednym MJPG i FFV1:
3 klatki, 5 FPS. `save_avi` dekoduje gotowy plik przed publikacją i sprawdza
geometrię/FPS/liczbę klatek; dla FFV1 weryfikuje dokładne hashe rasterów.
Wszystkie cztery zapisy przeszły te kontrole. VLC nie było używane.
Artefakty i `report.json`: `data/registration-reg13/movie-cpu/`.

## Koszt i ograniczenia pomiaru

Dla pilotażu 18 par LightGlue ładowanie trwało 1,15 s, suma wyznaczania par
0,50 s; metryki procesu dały 0,20 s ekstrakcji i 0,24 s matchera.
Pierwsza para obejmuje rozgrzewkę. Szczyt RSS pracownika około 1698 MiB,
Torch CUDA około 319 MiB. Jest to alokacja Torch, nie całkowita pamięć GPU.
Zasoby drzewa procesów i VRAM sterownika próbkowano co sekundę; zero z takiego
próbkowania na krótkiej próbie oznacza nieuchwycone użycie, nie brak użycia GPU.
Nie prowadzimy rankingu szybkości na podstawie pojedynczych pierwszych prób.

Nie wykonano próby na Windows, karcie 8 GB, niezależnym filmie walidacyjnym
ani manualnego odtwarzania AVI w VLC. Znane MOVIE_4/MOVIE_8 są zestawem
rozwojowym, a oględziny struktur wykorzystywanych przez modele nie są
niezależną walidacją. Wyników odmów nie usunięto ze zbioru.

Powtórzenie (nowy katalog wyników, ten sam lokalny kod i modele):

```bash
PYTHONPATH=.:tests/stmviewer python tests/stmviewer/diagnostics/lightglue_trial.py \
  --mode pairs --output /tmp/reg13-repeat --device cuda
PYTHONPATH=.:tests/stmviewer python tests/stmviewer/diagnostics/lightglue_trial.py \
  --mode patterns --output /tmp/reg13-repeat --device cuda
PYTHONPATH=.:tests/stmviewer python tests/stmviewer/diagnostics/lightglue_trial.py \
  --mode movie --output /tmp/reg13-repeat --source data/MOVIE_4.mpp --drop-first 2
PYTHONPATH=.:tests/stmviewer python tests/stmviewer/diagnostics/lightglue_trial.py \
  --mode movie --output /tmp/reg13-repeat --source data/MOVIE_8.mpp
PYTHONPATH=.:tests/stmviewer python tests/stmviewer/diagnostics/lightglue_trial.py \
  --mode visuals --output /tmp/reg13-repeat
```

## Zgłoszenie użytkownika: odmowa 2/32 na pierwszej parze

Na `8151970`, CUDA RTX 5090, dwukrotnie odtworzono odmowę dla źródłowych
klatek 3 i 4 MOVIE_4, czyli bieżącej pary 1→2 po usunięciu pierwszych dwóch:

```text
Za mało zgodnych wektorów przesunięcia: 2/32; wymagane co najmniej 4 zgodne.
```

32 oznacza korespondencje punktów między obrazami, nie liczbę par klatek.
Konsensus przy tolerancji 2 px zachował dwa wektory. Łańcuch potrzebuje
przesunięcia każdej sąsiedniej pary, więc kończy zadanie odmową.
To ten sam przypadek, który zapisano wcześniej w pilotażu REG-13.

Sprawdzono trzy hipotezy: rozmiar wejścia, tolerancję zgodności i skalowanie
współrzędnych. Zmieniano jeden parametr naraz, bez edycji programu:

| Długi bok wejścia | Punkty SuperPoint A/B | Korespondencje | Zgodne przy 2 px |
| --- | ---: | ---: | ---: |
| Natywne 256 px | 148 / 165 | 32 | 2 — odmowa |
| 512 px | 299 / 290 | 19 | 1 — odmowa |
| 1024 px | 2048 / 2048 | 16 | 1 — odmowa |

Powiększenie wejścia, także do domyślnego rozmiaru biblioteki 1024 px,
nie pomogło. Na tych samych 32 natywnych wektorach tolerancja 4 px dała
5 zgodnych i XY (14; 14), a 8 px — 11 zgodnych i XY (16; 13). Oba wyniki
mają ograniczone poparcie przestrzenne; 4 px także niski udział zgodnych
punktów. Nie ustalono prawdziwego dryfu ani przewagi tych oszacowań.

Kontrola na niekwadratowym wzorcu 137×219 ze znanym XY (−7; +5) dała:
natywnie (−7; +5), przy 512 px około (−6,844; +5,137), przy 1024 px
około (−7,058; +4,923). Sprawdzono też kod autorów: `extract` oddaje punkty
już przeliczone do układu wejścia. Nie stwierdzono podwójnego skalowania.

Wniosek: uzyskane korespondencje nie dają wystarczająco zgodnych wektorów
tej pary. Zmniejszenie minimum do dwóch dopuściłoby słabo poparty ruch,
bez dowodu naprawy dopasowania. **Kod i progi pozostały bez zmian;
odmowa nadal występuje.** Odbiór REG-13 pozostaje niezamknięty.

Lokalne artefakty: `data/registration-reg13/first-pair-diagnosis/`: manifest,
`summary.json`, surowe punkty `.npz` oraz dwa skrypty. W `netcat` z CUDA:

```bash
python data/registration-reg13/first-pair-diagnosis/reg13-first-pair-repro.py
```

Obecny rezultat: kod 1 i odmowa 2/32. Po poprawce algorytmu skrypt może
zwrócić przesunięcie i kod 0. Nie wykonano nowego odbioru GUI ani pełnych
testów aplikacji, ponieważ nie zmieniono jej kodu.
