# Audyt importu i geometrii STM Domains

Data: 2026-10-19. Kod odniesienia: `61d010e`. Środowisko: lokalna conda `netcat`.
Materiał do rozstrzygnięcia
[kontraktu importu](issues/01-import-and-geometry.md), nie implementacja importera.
Odczytywano dane i kod bez zmiany plików wejściowych.

## Wejście i rzeczywisty odczyt

Zbadano `data/TTMAPP/detection_full.moltrack.json` oraz
`data/TTMAPP/MOVIE_23raw_TTMAPP_I_AU111.MPP` w worktree Domains.
SHA-256 jest zgodne z [wcześniejszym audytem](research-molecular-orientation.md):

```text
JSON d0c4cb999bede28edb5dfd18ddbe146054711382f1c78363055be2330b3cdd2e
MPP  8fbbfa5d515a90552c13cee2dbd289ff5cc16f000315547185c2a57bfe9f7c66
```

| Sprawdzenie | Wynik |
| --- | --- |
| Schema JSON | 1; 268 klatek roboczych, źródłowe ID 0–267, reverse=false, aktywna 267 |
| Odczyt MPP istniejącym loaderem MolTrack | `(268,256,256)`, float64, wszystkie wartości skończone |
| Detekcje | 52 494: 49 226 YOLO i 3268 ręcznych; unikalne ID, wszystkie selected i expanded_aligned |
| Brak rekordów detekcji | Klatki 63–67; zapis nie rozstrzyga, czy je analizowano |
| Maski | 11 993, wyłącznie klatki 0–39; wszystkie expanded_aligned |
| Powiązania masek | Wszystkie prompt_detection_ids istnieją i wskazują tę samą klatkę |
| Rejestracja | 268 globalnych translacji; optical_flow_median, adjacent, reference 0 |
| Jakość rejestracji | Klatka 0: ok; pozostałe 267: low_confidence; minimum quality ≈0,0401264 |
| Odtworzone płótno | `(268,408,480)`; padding LTRB `(224,139,0,13)` |

Zapisana ścieżka absolutna jest windowsowa; istniejący resolver znajduje MPP
przez ścieżkę względną. Rozmiar zgadza się: **140 518 099 bajtów**. Data różni się:
JSON `mtime_ns=1327319652000000000`, lokalny MPP `1327326852000000000`, czyli
**+7200 s**. Wywołanie `load_moltrack_session` kończy się faktycznie błędem
`MolTrackSessionLoadError`, ponieważ loader wymaga zgodności obu metadanych.
Powyższe hashe obliczono w audycie; sam JSON ich nie zawiera.

## Geometria i maski

Loader MPP stosuje obrót o 180°. Odtworzenie istniejącą funkcją
`build_expanded_aligned_frames` dało początki klatek:

- 0: `(224,139)`;
- 39: `(178.2181123048067,133.27403063699603)`;
- 267: `(26.884201757609844,8.999746315181255)`.

JSON nie przechowuje globalnego paddingu. Odtworzono go z całego zestawu
przesunięć; wszystkie zapisane w metadanych segmentacji `registered_frame_origin_xy`
zgadzają się dokładnie. Obecne i historyczne bboxy detekcji oraz bboxy segmentacji
są skończone, mają dodatnie rozmiary i mieszczą się w zadeklarowanym płótnie.

282 historyczne bboxy różnią się od bieżących. Po odjęciu początków klatek
**8 bboxów częściowo wychodzi poza oryginalne pole**, żaden całkowicie.
Ich odrzucanie jako błędnego importu usunęłoby istniejące oznaczenia.
Próba wszystkich bboxów `expanded → raw → expanded` dała maksymalny błąd 0.

Wszystkie maski zdekodowano pojedynczo istniejącym dekoderem: bez błędów,
niepuste, pełny shape `(408,480)`, kodowanie `packbits-zlib-base64`.
Historyczne maski używają `same-as-mask`. Dla próbek z klatek 0, 1 i 39
przeliczenie tam i z powrotem dało 0 zmienionych pikseli; nie jest to gwarancja
odwracalności wszystkich resamplingów rastra.

Pełne zmaterializowanie bieżących i historycznych masek bool wymagałoby
`11993 × 408 × 480 × 2 = 4 697 418 240` bajtów, bez narzutu innych danych.
Istniejący dekoder kopiuje raster dla `same-as-mask`.

Obejrzano statyczne nakładki bboxów na klatkach 0, 39 i 267 w obu widokach.
Położenia odpowiadają widocznym molekułom. To ogląd poprawności importu,
nie pomiar skuteczności detekcji ani jakości rejestracji całej serii.

## Czas i jednostki

MPP zawiera kompletną tablicę **268 czasów równych 0 s**, a loader zwraca
`frame_interval_s=0.0`. To wartości zastępcze, nie użyteczny pomiar czasu.
Wcześniej użytkownik potwierdził zastępcze 1000×1000 nm, bias i current równe 0.
Brak kąta skanu otrzymuje w czytniku domyślne zero. Nie ma podstaw do uznania
tych wartości za skalibrowany pomiar; kontrakt przyjmuje px i numery klatek.

## Ustalenia z kodu

| Miejsce | Znaczenie dla importera |
| --- | --- |
| [session.py](../../moltrack/core/session.py) i [session_migration.py](../../moltrack/persistence/session_migration.py) | MolTrack obsługuje schema 1/2/3; pełny loader uruchamia także migracje analiz niepotrzebnych szkieletowi. |
| [session_store.py](../../moltrack/persistence/session_store.py) | Mapa źródłowych ID ustala kolejność. Resolver próbuje ścieżki absolutnej i względnej, ale nie przechodzi do kolejnego kandydata po wykryciu niezgodnych metadanych pierwszego. |
| [mpp_loader.py](../../nanotrack/io/mpp_loader.py) | `raw` jest już macierzą po obrocie 180°, znormalizowaną tak jak w MolTrack. |
| [aligned.py](../../nanotrack/registration/aligned.py) | Padding z ekstremów globalnych przesunięć, interpolacja liniowa, NaN poza próbkowanym obszarem. |
| [registered_coordinates.py](../../moltrack/core/registered_coordinates.py) | Oba bboxy są w tym samym układzie; zwykła translacja nie przycina ich. Metoda tworząca prompt przycina i nie jest wiernym importerem. |
| [detections.py](../../moltrack/core/detections.py) i [segmentations.py](../../moltrack/core/segmentations.py) | Rozpoznawane układy oznaczeń to `raw` i `expanded_aligned`. Pusta lista nie zapisuje historii sprawdzenia klatki. |

Krótkie próby w pamięci potwierdziły, że obecny parser cicho nadpisuje powtórzony
wynik rejestracji i przyjmuje duplikaty detection_id. Przy odtwarzaniu źródłowych
ID `(2,0)` obrazy zmieniają kolejność poprawnie, lecz `metadata.frame_times_s`
pozostaje pełnym `[10,20,30]` zamiast wybranych `[30,10]`. Dodatkowo dekoder maski
nie porównuje jej pełnego shape z geometrią widoku. Te zachowania nie mogą
zastępować walidacji kontraktu STM Domains.

Importy loadera, geometrii oraz parsera działają w netcat bez załadowania torch,
PyQt6, cv2 i ultralytics. Pełny parser wczytuje jednak moduły analizy i wszystkie
maski, więc jego interfejs nie odpowiada uzgodnionemu zakresowi lekkiego importera.
To obserwacja o ponownym użyciu, bez zmian wspólnych modułów w tej sesji.

## Wykonane sprawdzenia i granice

Uruchomiono istniejące testy w worktree Domains, z wyłączonym zapisem bytecode
i cache pytest:

```bash
PYTHONDONTWRITEBYTECODE=1 /home/rlew/projekty/conda-migration-ubuntu-20261008/envs/netcat/bin/python -m pytest -q -p no:cacheprovider tests/moltrack/test_registered_coordinates.py tests/nanotrack/test_mpp_loader.py
```

Wynik: **6 passed**. To testy istniejących komponentów, nie nowego importera.
Lokalne artefakty inspekcji są w `/tmp/stmdomains_import_geometry_audit.py`,
`/tmp/stmdomains_import_geometry_audit.txt` i `/tmp/stmdomains_import_geometry_audit.png`.
Nie należą do trwałych danych repozytorium; powyżej utrwalono wejście, procedurę
i wyniki. Kodowania masek inne niż obecne w TTMAPP oraz wersje 2/3 wymagają
fixture'ów odbioru nowego adaptera. Nie uruchamiano GUI STM Domains, nie zmieniano
jego kodu, nie wykonywano nowej rejestracji ani analizy domen.
