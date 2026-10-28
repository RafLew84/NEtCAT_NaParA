# Ticket 18 — raport pomiarów

Data: 2026-10-28. Kod aplikacji: `08c1f3c` (bez zmian produkcyjnych w tym etapie).
Duża seria przeszła pełny przebieg podglądu, usuwania, ponawiania oraz anulowania
importu/Phase. Nie znaleziono powodu do optymalizacji ani strojenia algorytmu.
Ręczny odbiór użytkownika pozostaje otwarty.

## Stanowisko i zakres dowodu

Ubuntu 24.04.4, kernel 7.0.0-38, x86_64, Python 3.12.12 (`netcat`).
AMD Ryzen 9 9950X3D2, 16 rdzeni / 32 wątki; 132,61 GB RAM,
125,84 GB dostępne przed dużą próbą. NVIDIA RTX 5090, 32607 MiB VRAM,
sterownik 595.91.07; Phase pracował na CPU, pomiar VRAM nie dotyczy tej próby.
NumPy 2.2.5, SciPy 1.15.2, scikit-image 0.25.2, PyQt6 6.9.1,
Qt 6.9.0 i psutil 7.1.3.

Katalog danych jest na `/dev/sda4`, dysku obrotowym ST4000VN006, nie na
obecnym w komputerze SSD Kingston SNV3S2000G. Nie czyszczono cache plików
systemu; czasy importu nie są pomiarem zimnego dysku ani stanowiska SSD.
Płynność po wczytaniu i pamięć mierzono na rzeczywistym kodzie aplikacji.
Ekran: Xvfb 1600 × 1200, Qt xcb, obszar podglądu 640 × 640; zrzuty pikseli
X11 nie potwierdzają odświeżania fizycznego monitora. To próba sterowana
skryptem z oceną zrzutów, odrębna od ręcznej akceptacji oraz odbiorów 20/21.

Metoda i polecenia: [instrukcja](large-series-manual.md).

## Dane

- Duże: `data/large-ticket18-v2/large.mpp`, **1000 × 512 × 512** float64,
  2 097 172 569 bajtów. SHA-256:
  `e8fca3386352f32e3807e3b710d2a29f3de74975615f951a071cb6059201f7eb`.
  Generator `large-series-v2`, seed 1801, manifest podaje przesunięcia XY.
  Phase wyznaczył **640 × 640**, zgodnie z geometrią wzorca.
- Typowe: `data/nanotrack_registration/dobre/MOVIE_23raw_TTMAPP_I_AU111.MPP`,
  **268 × 256 × 256**. Phase dał **313 × 656**; rozmiar faktycznie uwzględniono
  w próbie aligned. Zastępcze skale/czasy tego eksportu nie są wzorcem
  kalibracji ani czasu pomiaru. Nie oceniano tu jakości algorytmu na molekułach.

Nie wprowadzono limitu liczby klatek importu. Pozostałe pomiary lokalne
oraz końcowy odbiór systemów należą do dalszych etapów.

## Płynność i reakcje

Każdy wiersz obejmuje 30 s Play z zadanym 5 kl./s, 50 wyborów klatki i
50 prób Pause. Łącznie 400 prób reakcji. Kolejność sprawdzono względem
referencyjnych obrazów każdej klatki, nie samych numerów lub wywołań timera.

| Seria / widok | Zmierzone kl./s | Odstęp median / p95 / max [ms] | Wybór p95 [ms] | Pause p95 [ms] | Do 250 ms |
| --- | ---: | --- | ---: | ---: | --- |
| Duża original | 4,961 | 201,43 / 203,42 / 204,69 | 12,93 | 6,47 | 100% / 100% |
| Duża aligned | 4,952 | 202,05 / 203,51 / 204,31 | 13,00 | 6,49 | 100% / 100% |
| TTMAPP original | 4,960 | 201,51 / 203,30 / 204,05 | 11,96 | 6,33 | 100% / 100% |
| TTMAPP aligned | 4,951 | 202,00 / 203,67 / 204,29 | 11,35 | 6,74 | 100% / 100% |

Odstępy odpowiadają nominalnym 200 ms z narzutem GUI i pomiaru, bez długich
zatrzymań i nadrabiania. Każda próba zobaczyła 148 zmian obrazu w 30 s;
nie stwierdzono pomijania klatek. Przy zadanych 30 kl./s (dodatkowo po 3 s)
zmierzono 27,87–28,69 kl./s, nadal z kolejnymi obrazami. Kontrolowane
przeciążenie malowania pozostaje też objęte istniejącym testem `test_playback`.

## Duże operacje i RAM

Jednostki poniżej to dziesiętne GB; budżet porównania wynosi 16 GB.
RSS obejmuje proces i jego dzieci, próbkowanie co 50 ms; krótszy szczyt
może być niedoszacowany. Czasy obejmują przygotowanie widocznego wyniku.

| Operacja | Czas [s] | RSS szczyt [GB] | RSS po [GB] |
| --- | ---: | ---: | ---: |
| Pierwsze otwarcie dużego MPP | 2,263 | 2,371 | 2,371 |
| Pierwsze Phase | 21,721 | 6,073 | 6,073 |
| Phase po usunięciu 3 klatek (997) | 21,159 | 9,743 | 9,743 |
| Ponowne otwarcie | 1,664 | 9,744 | 9,678 |
| Phase po ponownym otwarciu | 21,205 | 9,686 | 9,686 |
| Kolejne otwarcie | 1,775 | 10,331 | 10,320 |
| Kolejne Phase | 20,050 | 10,327 | 10,327 |
| Zastąpienie małym MPP | 0,144 | 10,328 | 10,304 |

Szczyt całego przebiegu: **10,331 GB**, poniżej 16 GB na tym stanowisku.
TTMAPP: otwarcie 1,156 s, Phase 1,317 s, szczyt całej próby 0,907 GB.
Nie jest to obietnica tych samych czasów na innym CPU ani formalny test
systemu ograniczonego do 16 GB RAM.

Anulowanie dużego Phase przy liczeniu par i podczas materializacji przyjęto
w około 11–12 ms do zakończenia; importu podczas odczytu i miniatur — około
6 ms. Każda próba zachowała poprzednie obrazy, licznik i widok. Zmiany
postępu były obserwowane; podczas pracy działała nawigacja po starej serii.
Usuwanie środka, końca i odniesienia zachowało obrazy pozostałych klatek.

RSS po zastąpieniu dużej serii pozostaje wysoki. Osobna próba z `tracemalloc`
(bez używania jej czasów do oceny płynności) odróżniła żywe dane NumPy od
wolnych bloków pozostawionych przez alokator:

| Stan | Żywe bufory NumPy [bajty] |
| --- | ---: |
| Po otwarciu dużej serii | 2 097 152 000 |
| Po pierwszym Phase | 5 783 552 000 |
| Po ponownym Phase | 5 783 552 000 |
| Po zastąpieniu małym MPP | 288 |

Stare tablice są zwalniane; RSS nie jest tu miarą żywych stosów. Testy
szybkie obserwujące słabe referencje do wyników SciPy potwierdziły też zwolnienie
usuniętych, zastąpionych i częściowych aligned po anulowaniu/MemoryError.
Nie dodawano wymuszania GC ani platformowej funkcji oddawania pamięci.

## Walidacja i artefakty

Szybki zestaw dla generatora, zasobów, importu, Play i Phase: **46 passed**.
Po osłabieniu znacznika wzorca ponowiono jego test i 3 testy zasobów:
**4 passed**. Mypy strict: **33 pliki, bez błędów**. Pełny zestaw repo
zostanie podsumowany w [przekazaniu](handoff.md).

Pełne lokalne raporty: `/tmp/stmviewer18-large-final.json`,
`/tmp/stmviewer18-typical.json`, `/tmp/stmviewer18-live-memory.json`;
logi i zrzuty z odpowiadającymi nazwami. Pierwsza seria `data/large-ticket18/`
służyła rozpoznaniu; finalne dane i raport mają sufiks `v2` / `final`.
Wstępny mocny znacznik zakłócał szacowanie dryfu; poprawiono tylko generator,
bez zmiany ustawień Phase. Zapisane wyniki dotyczą wersji końcowej.
