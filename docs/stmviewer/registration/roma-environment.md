# REG-11: osobne środowisko RoMa v2

Data: 2026-11-02. **Przygotowanie środowiska zakończone.**
Pierwotnie użytkownik wybrał „Przygotuj środowisko i zaktualizuj REG-11”.
Poniższe pomiary opisują tamten etap przygotowania. Na późniejsze zlecenie
wdrożono [REG-11](issues/11-roma-v2.md); status `ready-for-review`.
Aktualne próby integracji i produkcyjnego procesu: [wyniki](roma-results.md),
[obsługa w GUI](roma-manual.md).

## Podział wykonania

- **`netcat`**: STM Viewer, Qt, odczyt pomiarów, sesje, konsensus korespondencji
  do XY, graf LS/Hubera, renderowanie oraz MPP/AVI.
- **`netcat-romav2`**: osobny proces wykonujący model RoMa v2 i próbkowanie
  gęstych dopasowań. Jego biblioteki nie są importowane do procesu GUI.

Proces jest uruchamiany bezpośrednio interpreterem nowego środowiska,
bez `conda activate` wewnątrz programu. Jeden model obsłuży całe zadanie
pary, serii albo grafu. Wymiana JSON/NumPy, anulowanie, sprzątanie i zapis
konfiguracji są opisane jako wymagania w tickecie REG-11.
Otwarcie zapisanej sesji nie uruchomi zapisanego w niej interpretera.

## Przygotowane środowisko

Nazwa conda: **`netcat-romav2`**.

```text
/home/rlew/miniconda3/envs/netcat-romav2/bin/python
```

Python 3.12.16. Zestaw głównych bibliotek:

| Biblioteka | Wersja |
| --- | --- |
| romav2 | 2.0.1 |
| torch / torchvision | 2.11.0 / 0.26.0 |
| CUDA runtime Torch | 13.0 |
| fused-local-corr | 0.3.211 |
| numpy / einops | 2.2.5 / 0.8.2 |
| Pillow / rich / tqdm | 12.3.0 / 14.3.4 / 4.67.3 |

[Wymagania procesu](../../../stmviewer/requirements-roma-worker.txt) są
oddzielne od wymagań głównej aplikacji. Na Linuksie zawierają zgodne wersje
Torch i `fused-local-corr`; bibliotek przyspieszenia nie pominięto.
Zestaw sprawdzono na Ubuntu z RTX 5090 i sterownikiem 595.91.07.
Nie instalowano ani nie zmieniano sterownika NVIDIA.

Odtworzenie środowiska z katalogu repozytorium:

```bash
conda create --name netcat-romav2 --override-channels -c conda-forge python=3.12.16 pip -y
conda run -n netcat-romav2 python -m pip install -r stmviewer/requirements-roma-worker.txt
conda run -n netcat-romav2 python -m pip check
```

Pełna lista zainstalowanych wersji, eksport conda i manifest pozostają lokalne:

```text
/home/rlew/.cache/stmviewer/romav2/requirements-frozen.txt
/home/rlew/.cache/stmviewer/romav2/environment.yml
/home/rlew/.cache/stmviewer/romav2/environment.json
```

To zapis sprawdzonego zestawu na tym stanowisku. Windows i inne sterowniki
nie zostały sprawdzone. `netcat` zachował wszystkie **213 pakietów** z tymi
samymi wersjami; nadal ma Torch 2.9.1+cu128. Dowód porównania inwentarzy:
`/home/rlew/.cache/stmviewer/romav2/netcat-unchanged.json`.

## Lokalne zasoby

Katalog: `/home/rlew/.cache/stmviewer/romav2/`.

- `weights/romav2.0.1.pt` — 1 095 883 548 bajtów; SHA-256
  `1557dec0d21b62366465f7ff4d5fdf228cc695d0582e196ad2b80e05230828b7`.
  Pobrano z [oficjalnego wydania](https://github.com/Parskatt/RoMaV2/releases/tag/v2.0.1)
  i sprawdzono sumę opublikowaną przy zasobie.
- `dinov3/` — kod [DINOv3](https://github.com/facebookresearch/dinov3),
  czysty checkout `adc254450203739c8149213a7a69d8d905b4fcfa`, wymagany przez
  zainstalowane RoMa v2. DINOv3 nie jest instalowane do `netcat`.
- Kod RoMa jest zainstalowany w nowym środowisku jako `romav2==2.0.1`.
  Hash 29 plików Python pakietu:
  `198779ceb8d2a02e112c2f346456c37477f7bc3ac61dff3d19aec58038d2ab21`.
  Algorytm sumy i pełne wersje zapisano w `environment.json`.
- `download.json` — pochodzenie, sumy, wersje i ścieżki licencji.
  Kod RoMa ma MIT z wyjątkiem DINOv3, które ma własną licencję.
  Zachowano pliki `licenses/RoMaV2-MIT-LICENSE.txt` i `dinov3/LICENSE.md`.

Domyślny pełny checkpoint zawiera również parametry DINOv3 oraz VGG.
Nie pobierano osobnych wag tych składników. Kod konstruktorów inicjalizuje
je bez wag wstępnych, a następnie ładuje cały stan RoMa:
[konstruktor](https://github.com/Parskatt/RoMaV2/blob/main/src/romav2/romav2.py),
[składniki](https://github.com/Parskatt/RoMaV2/blob/main/src/romav2/features.py).
Ścisłe ładowanie rzeczywistego checkpointu potwierdzono lokalnie.

## Wykonane sprawdzenia

Rodzic używał interpretera `netcat`, a proces potomny pełnej ścieżki
`netcat-romav2/bin/python`, z izolowanym `sys.path`. Potomek nie korzystał
z pakietów `netcat`. `pip check` zgłosił brak konfliktów.

Lokalny skrypt `verify_environment.py` przekierowuje tylko dwa znane wywołania
Torch Hub do zweryfikowanego checkpointu i lokalnego kodu DINOv3. Blokuje
pobieranie oraz połączenia sieciowe. To skrypt przygotowania środowiska,
nie produkcyjny backend aplikacji; nie modyfikuje zainstalowanego RoMa.

Znany wzorzec 256 × 256, szarość powielona do RGB, ruch obrazu (+7, −5) px.
Preset **turbo**, wejście modelu 320 × 320, 1000 próbkowanych dopasowań,
seed 20261102. Oczekiwane XY do wyrównania: (−7, +5) px.

| Proces | Mediana XY [px] | Maks. błąd osi | Ładowanie modelu | Dopasowanie i próbkowanie |
| --- | --- | --- | --- | --- |
| CPU, 4 wątki | (−7,0061; +5,0299) | 0,030 px | 2,15 s | 0,84 s |
| CUDA, RTX 5090 | (−7,0097; +5,0352) | 0,035 px | 2,14 s | 0,36 s |

Przyspieszenie `fused-local-corr` załadowało się w obu procesach.
Szczyt pamięci przy dopasowaniu CUDA wyniósł około 1173 MiB alokacji Torch;
to nie całkowite użycie GPU ani odbiór innych presetów na karcie 8 GB.
Żaden proces nie podjął próby połączenia z siecią. Po zakończeniu model
zniknął wraz z procesem. Proces nadrzędny w `netcat` wczytał punkty NumPy
i przeliczył je obecnym konsensusem v2: 1000 zgodnych punktów, te same XY, `manual_review`.

Raporty w katalogu zasobów: `verification-cpu.json`, `verification-cuda.json`,
`verification-parent-consensus.json`, odpowiadające logi i tablice `.npz`.
Przykład powtórzenia lokalnej próby (z podmienioną nazwą pliku wyniku):

```bash
/home/rlew/miniconda3/envs/netcat-romav2/bin/python -I -B \
  /home/rlew/.cache/stmviewer/romav2/verify_environment.py \
  --device cuda --output /tmp/romav2-environment-check.json
```

Te sprawdzenia potwierdzają gotowość środowiska i możliwość uruchomienia
modelu w osobnym procesie. Nie stanowią wdrożenia GUI, testu anulowania
produkcyjnego zadania ani oceny jakości RoMa na rzeczywistych filmach STM.
Ich późniejsze wykonanie opisuje raport wyników REG-11 podlinkowany powyżej.
