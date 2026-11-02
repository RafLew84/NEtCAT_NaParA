# LightGlue + SuperPoint — kod, wagi i środowisko

Przygotowano **2026-11-02** na zlecenie użytkownika. Kod oraz oba checkpointy
są lokalne i przeszły próbę CPU/CUDA w `netcat`, bez pobierania podczas
obliczeń. [REG-13](issues/13-lightglue-superpoint.md) pozostaje
`ready-for-agent`: integracja z aplikacją i odbiór ręczny jeszcze nie nastąpiły.

## Lokalne zasoby

Katalog: `/home/rlew/.cache/stmviewer/lightglue/`.

| Element | Ścieżka względem katalogu |
| --- | --- |
| Oryginalny kod autorów, przypięty checkout Git | `source/` |
| Wagi ekstraktora SuperPoint | `weights/superpoint_v1.pth` |
| Wagi matchera LightGlue dla SuperPoint | `weights/superpoint_lightglue.pth` |
| Lista źródeł i SHA-256 plików | `source-manifest.json` |
| URL, rozmiary i SHA-256 wag | `download-manifest.json` |
| Zachowane licencje oraz ich źródła | `licenses/` |
| Skrypt przygotowania zasobów | `prepare-resources.py` |
| Odtwarzalna próba bez sieci | `verify_environment.py` |
| Wyniki CPU/CUDA i korespondencje | `verification-cpu.json/.npz`, `verification-cuda.json/.npz` |
| Porównanie pakietów przed/po | `netcat-unchanged.json` |

Źródło: [oficjalne cvg/LightGlue](https://github.com/cvg/LightGlue),
rewizja **`5a650c444718caffc2669dc0094cde908f42dd73`**.
Checkout zawiera 28 plików poza `.git`, bez modyfikacji źródeł autorów.
SHA-256 drzewa:

```text
31a9fe6f54373931339e8eb3d69931bc590768f2377ecc2e15213fec0a142d44
```

Algorytm: uporządkowane według ścieżki POSIX wiersze
`SHA256_pliku + dwie spacje + ścieżka + znak nowego wiersza`, następnie SHA-256
całego ciągu UTF-8. Manifest zachowuje wszystkie składniki.

Checkpointy z wydania autorów `v0.1_arxiv`:

| Plik i źródło | Rozmiar [bajty] | SHA-256 |
| --- | ---: | --- |
| [superpoint_v1.pth](https://github.com/cvg/LightGlue/releases/download/v0.1_arxiv/superpoint_v1.pth) | 5 206 086 | `52b6708629640ca883673b5d5c097c4ddad37d8048b33f09c8ca0d69db12c40e` |
| [superpoint_lightglue.pth](https://github.com/cvg/LightGlue/releases/download/v0.1_arxiv/superpoint_lightglue.pth) | 47 500 279 | `6ff7040d0a497fc6639337946d7538dae07428c18f77a067a0b5a960e7cc551a` |

Sumy obliczono lokalnie po pobraniu i ponownie sprawdzono po próbach.
Służą identyfikacji pobranych plików; nie opisujemy ich jako podpisu wydawcy.
Modele, kod zewnętrzny i duże wyniki pozostają poza repozytorium Viewera.

## Środowisko i lokalne ładowanie

Interpreter:

```text
/home/rlew/projekty/conda-migration-ubuntu-20261008/envs/netcat/bin/python
```

Python 3.12.12, Torch 2.9.1+cu128, torchvision 0.24.1+cu128,
Kornia 0.8.2, NumPy 2.2.5, OpenCV 4.11.0.86, Matplotlib 3.10.1.
Wymagane biblioteki były już dostępne: **nie instalowano pakietów i nie
zmieniano środowiska**. Inwentarz 213 pakietów pozostał identyczny,
`pip check`: brak uszkodzonych wymagań. Nie potrzeba osobnego `flash-attn`.

Pakiet `lightglue` nie jest globalnie zainstalowany w `netcat`: skrypt
próby dodaje lokalny `source/` do ścieżki importu w swoim procesie.
To sposób uruchomienia zasobów, a nie gotowa integracja REG-13.

Konstruktory upstream wołają Torch Hub. Próba przechwytuje wyłącznie dwa
oczekiwane URL-e i odczytuje odpowiadające im lokalne pliki przez
`torch.load(..., weights_only=True, map_location='cpu')`. Pozostałe pobieranie
i połączenia sieciowe są blokowane; raporty nie wykazały prób użycia sieci.
Nie zmieniano kodu autorów. REG-13 musi zachować ten kontrakt lokalnych zasobów
w docelowym adapterze i obsłużyć brak/uszkodzenie wag.

SuperPoint używa starszego formatu serializacji, nieobsługiwanego przez
statyczny skaner `get_unsafe_globals_in_checkpoint`; `weights_only=True`
odczytał go poprawnie. Dla obu modeli zachowano bezpieczne ładowanie bez
rozszerzania listy dozwolonych obiektów pickle.

Sprawdzono kompletność parametrów: SuperPoint `strict=True`; dla LightGlue
odtworzono zmianę nazw historycznych kluczy attention wykonywaną przez upstream.
Dokładnie dziewięć `log_assignment.0–8.r` ma wartość `[1.0]` i nie jest
używanych przez przypięty kod. Jedyny brakujący element to generowany bufor
`confidence_thresholds`. Po jawnej obsłudze tych elementów wykonano `strict=True`
i potwierdzono wartości wszystkich aktualnych parametrów uczonych.
Nie uznano samego upstreamowego `strict=False` za dowód zgodności.

## Wykonane próby

Wzorzec 256 × 256, jeden kanał float32 w zakresie 0–1, seed 20261102,
4 wątki CPU. Obraz przesunięto o (+7, −5) px; oczekiwane XY wyrównania
wynosi (−7, +5) px. Ekstrakcja `resize=None`, bez paddingu, maksymalnie
2048 punktów; pozostałe ustawienia SuperPoint domyślne i zapisane w JSON.
LightGlue: 9 warstw, `filter_threshold=0.1`, `depth_confidence=0.95`,
`width_confidence=0.99`, `flash=True`, `mp=False`, bez kompilacji.
Wagi/wejście FP32; FlashAttention może wewnętrznie używać FP16 na CUDA.

| Urządzenie | Punkty odniesienia/ruchomego | Dopasowania | Mediana XY [px] | Wczytanie [s] | Ekstrakcja obu obrazów [s] | Matcher [s] |
| --- | ---: | ---: | --- | ---: | ---: | ---: |
| CPU | 238 / 254 | 200 | −7; +5 | 0,093 | 0,075 | 0,019 |
| CUDA, RTX 5090 | 237 / 251 | 198 | −7; +5 | 0,105 | 0,208 | 0,123 |

Istniejący konsensus v2 Viewera również zwrócił **(−7, +5)** dla obu urządzeń,
ze statusem `manual_review`. To próba przygotowania zasobów, nie ocena jakości
na STM. Różna liczba punktów CPU/CUDA jest zapisana w raportach.

Szczyt RSS procesu: CPU około 1612 MiB, CUDA około 1694 MiB.
Szczyt alokacji Torch na GPU: około 115 MiB; nie jest to całe użycie VRAM.
Czasy to pojedyncze pierwsze wykonania, bez rozgrzewki; nie służą do porównania
wydajności CPU/GPU ani przewidywania czasu pełnego filmu. Nie sprawdzono karty 8 GB.

Powtórzenie próby z wynikiem poza katalogiem zasobów:

```bash
/home/rlew/projekty/conda-migration-ubuntu-20261008/envs/netcat/bin/python -I -B \
  /home/rlew/.cache/stmviewer/lightglue/verify_environment.py \
  --device cpu --output /tmp/lightglue-cpu-check.json
```

Dla GPU zmień na `--device cuda` i osobną nazwę wyniku.
Próby wymagają lokalnego checkoutu Viewera do końcowego konsensusu;
ścieżkę można zmienić przez `--viewer`. Sam model korzysta z lokalnego `source/`.

Audyt skryptu i sposobu ładowania nie wykazał blokujących uwag.
Nie wykonano pilotażu 18 par, pełnych MOVIE_4/MOVIE_8, GUI, sesji, grafu,
anulowania, eksportów ani Windows. Nie uruchamiano pełnych testów aplikacji,
ponieważ jej kod nie zmienił się. Te sprawdzenia pozostają w REG-13.

## Licencje i uwagi dla integracji

Zachowano Apache-2.0 LightGlue oraz osobną
[licencję SuperPoint](https://github.com/magicleap/SuperPointPretrainedNetwork/blob/1fda796addba9b6f8e79d586a3699700a86b1cea/LICENSE),
która określa użycie do wewnętrznych badań niekomercyjnych.
[Autorzy LightGlue](https://github.com/cvg/LightGlue/tree/5a650c444718caffc2669dc0094cde908f42dd73#license)
wskazują, że odrębne warunki dotyczą także wag i pliku inference SuperPoint.
Nie przypisujemy całemu zestawowi licencji Apache-2.0.

`extract()` domyślnie zmienia długi bok do 1024, ale zwraca punkty przeliczone
z powrotem na współrzędne wejścia. REG-13 musi zapisać przygotowanie i nie
odwracać skali ponownie. Kod LightGlue zmienia ustawienia Torch dotyczące
attention; próbę wykonano w osobnym procesie. Adapter musi określić sposób
izolacji tych ustawień i nie wpływać niejawnie na pozostałe metody.
