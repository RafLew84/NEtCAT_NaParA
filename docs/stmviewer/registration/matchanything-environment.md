# REG-12: przygotowanie MatchAnything-ELoFTR

Data: 2026-11-02. Na zlecenie „ściągnij wymagane elementy” pobrano kod
oraz checkpoint i sprawdzono uruchomienie w istniejącym `netcat`.
**Zasoby są gotowe; implementacja REG-12 pozostaje `ready-for-agent`.**
Metoda nie została jeszcze dodana do GUI. Nie instalowano bibliotek ani
nie tworzono kolejnego środowiska.

## Lokalne pliki i pochodzenie

Katalog zasobów: `/home/rlew/.cache/stmviewer/matchanything/`.

| Element | Ścieżka w katalogu zasobów |
| --- | --- |
| Kod autorów wraz z konfiguracją i licencjami | `source/` |
| Wagi ELoFTR | `weights/matchanything_eloftr.ckpt` |
| Wersja i sumy wszystkich plików źródłowych | `source-manifest.json` |
| Pochodzenie, rozmiar, CRC i SHA checkpointu | `download-weight.json` |
| Próba uruchomienia bez sieci | `verify_environment.py` |
| Raporty CPU/CUDA, logi i punkty | `verification-cpu.*`, `verification-cuda.*` |
| Punkty przeliczone konsensusem Viewera | `verification-consensus.json` |
| Porównanie pakietów przed i po przygotowaniu | `netcat-unchanged.json` |

Kod pochodzi z katalogu `imcui/third_party/MatchAnything` w
[oficjalnym demonstratorze wskazanym przez projekt](https://huggingface.co/spaces/LittleFrog/MatchAnything/tree/6a7bcb589ec8da3a9e861e799122beaa5eba2193/imcui/third_party/MatchAnything).
Przypięta rewizja: `6a7bcb589ec8da3a9e861e799122beaa5eba2193`.
Pobrano 163 pliki, łącznie 2 400 308 bajtów; każdy zweryfikowano względem
Git blob SHA z indeksu Hugging Face. SHA-256 drzewa:

```text
e7bb0235d9a7ebd38bf99fc34e9dcaaee325a0f55ecd8a2f12f1cce3671fc98f
```

Algorytm: dla plików posortowanych po względnej ścieżce POSIX łączymy
wiersze `SHA256_pliku + dwie spacje + ścieżka + znak nowego wiersza`,
a następnie liczymy SHA-256 tego ciągu UTF-8. Manifest zapisuje wszystkie
składniki. To kopia przypiętych plików źródłowych, bez katalogu `.git`.

Checkpoint pobrano z [archiwum autorów](https://drive.google.com/file/d/12L3g9-w8rR9K2L4rYaGaDJ7NqX1D713d/view),
wskazanego w README oraz
[skrypcie demonstratora](https://huggingface.co/spaces/LittleFrog/MatchAnything/blob/6a7bcb589ec8da3a9e861e799122beaa5eba2193/imcui/ui/app_class.py).
Archiwum ma 482 746 196 bajtów. Odczyt katalogu ZIP i HTTP Range pozwolił
pobrać wyłącznie `weights/matchanything_eloftr.ckpt`, bez wag MatchAnything-RoMa.
Pobrany strumień deflate: 60 766 057 bajtów, zakres 421979835–482745891.
Po rozpakowaniu:

- rozmiar **64 366 723 bajty**;
- CRC32 `fde5eff9`, zgodne z katalogiem ZIP;
- SHA-256 `b394fd368488e5e3136906daac825fadd3dd5376755dcdf5cb6ede0de20f6e7e`.

SHA jest również zgodne z metadanymi publicznej kopii
`stevenbucaille/matchanything_eloftr` w rewizji
`9572ad7aad84de82bd3cbf3d5f2ad231f0dbf6e5`; tej kopii nie pobierano.
Lokalne `download-source.py`, `source-tree.json` i `download-weights.py`
zachowują sposób pobrania. Skrypty odmawiają zastępowania istniejących zasobów.

## Biblioteki i sposób importu

Próba użyła interpretera:

```text
/home/rlew/projekty/conda-migration-ubuntu-20261008/envs/netcat/bin/python
```

Python 3.12.12; Torch 2.9.1+cu128, NumPy 2.2.5, OpenCV 4.11.0.86,
einops 0.8.2, Kornia 0.8.2, yacs 0.1.8, loguru 0.7.3,
SciPy 1.15.2 i joblib 1.4.2. Pełny inwentarz **213 pakietów pozostał
identyczny**; `pip check` zgłosił brak uszkodzonych wymagań.

Uruchomiono bezpośrednio niezmieniony `src.loftr.LoFTR` z oficjalną
konfiguracją `configs/models/eloftr_model.py`. Wrapper `PL_LoFTR`
importuje również kod treningu i nieużywane RoMa oraz stare API Lightning;
nie jest potrzebny do wykonania ELoFTR. Nie instalowano jego pełnych,
starych wymagań do `netcat`.

Próba działa jako osobny proces `netcat` z `-I -B`. Kod konfiguracyjny
używa globalnej nazwy pakietu `src`; produkcyjny adapter REG-12 musi
izolować ten import lub wykonać go w procesie. Sam udany import nie dowodzi
gotowości istniejącego adaptera EfficientLoFTR do prostej podmiany wag.
Nie modyfikowano źródeł autorów. Po próbie ponownie sprawdzono ich sumy.

## Wykonane próby

Checkpoint zawiera `state_dict`; `torch.load(weights_only=True)` nie
wymaga dodatkowych dozwolonych globals. `strict=True`: brak pominiętych
i nadmiarowych kluczy. Model ma 16 025 216 parametrów.

Wzorzec 256 × 256, jeden kanał float32 w zakresie 0–1, bez skalowania
ani paddingu; seed 20261102. Ruch obrazu (+7, −5) px, oczekiwane XY
wyrównania (−7, +5) px. Konfiguracja: FP32, próg 0,1,
NPE `[832, 832, 256, 256]`, bez reparameterization, 4 wątki CPU.
Pełna konfiguracja znajduje się w raportach JSON.

| Urządzenie | Punkty | Mediana XY [px] | Maks. błąd osi | Model i wagi | Dopasowanie |
| --- | ---: | --- | ---: | ---: | ---: |
| CPU | 731 | −7,02364; +4,96828 | 0,03172 px | 0,173 s | 0,188 s |
| CUDA, RTX 5090 | 732 | −7,02166; +4,96836 | 0,03164 px | 0,259 s | 0,191 s |

Szczyt RSS procesu: około 1115 MiB CPU / 1453 MiB CUDA. Szczyt alokacji
Torch na GPU: około 481 MiB; to nie całe użycie VRAM ani odbiór na karcie
8 GB. Czasy są pojedynczymi pomiarami tej próby, bez obietnicy wydajności filmu.

Proces miał zablokowane połączenia sieciowe i pobieranie Torch Hub.
Nie odnotowano prób użycia sieci. Zapisane korespondencje przeliczono
obecnym konsensusem v2 Viewera: CPU (−7,02560; +4,96974), CUDA
(−7,02563; +4,96957), oba ze statusem `manual_review`.

Powtórzenie lokalnej próby, z wynikiem poza katalogiem zasobów:

```bash
/home/rlew/projekty/conda-migration-ubuntu-20261008/envs/netcat/bin/python -I -B \
  /home/rlew/.cache/stmviewer/matchanything/verify_environment.py \
  --device cuda --output /tmp/matchanything-check.json
```

Dla CPU należy podać `--device cpu`. Nie wykonano próby jakości MOVIE_4/MOVIE_8,
integracji GUI, sesji, grafu, anulowania, eksportu, Windows ani sprzętu 8 GB.
Pozostają one kryteriami [REG-12](issues/12-matchanything.md).
Testów aplikacji nie powtarzano: jej kod nie zmienił się.

## Zachowane licencje

Pobrany katalog kodu HF zawiera Apache-2.0; zachowano
`licenses/HF-source-Apache-2.0.txt` oraz licencje wewnątrz `source/`.
Aktualny [GitHub LICENSE](https://github.com/zju3dv/MatchAnything/blob/8cd8c1129a6d22dabea9405a869e4fad6ff8b630/LICENSE)
ma inne brzmienie: Project Registration License v1.0. Jego kopia jest
w `licenses/GitHub-project-PRL-v1.txt`. Dokumenty pochodzą z różnych,
jawnie przypiętych źródeł; nie przypisujemy samym wagom licencji Apache
wyłącznie na podstawie licencji kodu demonstratora.
