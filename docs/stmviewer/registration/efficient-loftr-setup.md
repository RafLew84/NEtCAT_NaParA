# EfficientLoFTR: lokalny kod i wagi

Przygotowano 2026-11-02 na prośbę użytkownika. Biblioteki zainstalował użytkownik;
kod i checkpoint pobrano oraz sprawdzono w `netcat`. Następnie wdrożono
REG-10: [obsługa w aplikacji](efficient-loftr-manual.md),
[rzeczywiste próby](efficient-loftr-results.md). Poniższa pierwsza próba
ładowania dokumentuje przygotowanie poprzedzające implementację.

## Pliki i pochodzenie

Katalog lokalny: `/home/rlew/.cache/stmviewer/efficientloftr/`.

- `source/`: czysty checkout [repozytorium autorów](https://github.com/zju3dv/EfficientLoFTR),
  detached HEAD `07e9c1401e71e9c556b1fda9d86d060af36ba176`.
- `weights/eloftr_outdoor.ckpt`: oryginalny format checkpointu, **192797577 bajtów**;
  pobrano z [Google Drive](https://drive.google.com/file/d/1jFy2JbMKlIp82541TakhQPaoyB5qDeic/view).
  Identyfikator pliku potwierdza [instrukcja vismatch](https://vismatch.readthedocs.io/en/stable/contributing.html).
  README autorów wskazuje folder Drive; jego przynależności do folderu nie
  udało się niezależnie potwierdzić.
- `download.json`: faktyczny URL pobrania, czas, rozmiar i suma pliku.
- `verify.py`, `verification.json`: powtarzalna próba ładowania i obliczenia
  pary, wersje bibliotek, konfiguracja, sprzęt i wyniki.

SHA-256 wag:

```text
0af6291141c736e75e94b7f8aae4399b77c7731b3f08758212b2cfe370188878
```

Suma została obliczona po pobraniu i sprawdzona z kopiami, m.in.
[historycznym oryginalnym checkpointem Stevena Bucaille](https://huggingface.co/stevenbucaille/efficient_loftr_pth/commit/7181929f57628733cce513d0080c7ee763a4023f).
Nie jest podpisaną sumą opublikowaną przez autorów. Plik pochodzi z Drive,
nie z tego mirrora. Jest to `eloftr_outdoor.ckpt`, odrębny od wag dotychczasowego
Deep Matchera `loftr_outdoor.ckpt`.

Kod w przypiętej wersji ma [licencję PRL v1.0](https://github.com/zju3dv/EfficientLoFTR/blob/07e9c1401e71e9c556b1fda9d86d060af36ba176/LICENSE).
Zachowano lokalny `source/LICENSE` i jego SHA-256 w raporcie. Osobnej deklaracji
licencji oryginalnych wag nie znaleziono; nie przypisujemy im automatycznie
licencji podanej przez mirrory. Kod zewnętrzny, wagi i wyniki pozostają lokalne.

## Środowisko i ładowanie

Sprawdzone wersje: Python środowiska `netcat`, torch 2.9.1+cu128,
torchvision 0.24.1+cu128, NumPy 2.2.5, einops 0.8.2, Kornia 0.8.2,
yacs 0.1.8, loguru 0.7.3, pytorch-lightning 2.6.6, torchmetrics 1.9.0,
joblib 1.4.2 i opencv-python 4.11.0.86. Pobranie nie instalowało dodatkowych
pakietów ani nie zmieniało torch/CUDA.

Pierwsze ładowanie `weights_only=True` wykazało metadane klasy Lightning
`pytorch_lightning.callbacks.model_checkpoint.ModelCheckpoint`.
To jedyny global wskazany przez `get_unsafe_globals_in_checkpoint`.
Próba zachowuje `weights_only=True` i dopuszcza wyłącznie tę klasę z już
zainstalowanej biblioteki przez kontekst `torch.serialization.safe_globals`.
Następnie ładuje `state_dict` z `strict=True`, wywołuje `reparameter()` i `eval()`.
Nie użyto nieograniczonego ładowania pickle ani nie modyfikowano checkpointu.
Adapter REG-10 uwzględnia ten format. Dodatkowo przed wykonaniem sprawdza
35 plików `src/**/*.py`: posortowana ścieżka POSIX względem repo + NUL +
zawartość + NUL, SHA-256
`4007cea8f5fdcaeb46cfab76fe72c94666c49181a077e66eb1deff0268ef78ec`.
Wykonuje zweryfikowane źródła w odrębnej przestrzeni nazw, pomijając pliki
`.pyc`; nie wymaga Git podczas pracy programu.

Na Windows zachowaj oryginalne zakończenia linii przy klonowaniu, np.
`git -c core.autocrlf=false clone https://github.com/zju3dv/EfficientLoFTR.git`,
a następnie wybierz powyższy commit. Automatyczna zamiana LF na CRLF zmienia
sumę źródeł. Aplikacja odrzuci taki zmieniony kod z komunikatem o wersji.

Powtórzenie lokalnej próby (wymaga CPU i dostępnego CUDA):

```bash
conda activate netcat
PYTHONDONTWRITEBYTECODE=1 MPLCONFIGDIR=/tmp/efficientloftr-matplotlib \
  OPENBLAS_NUM_THREADS=1 python /home/rlew/.cache/stmviewer/efficientloftr/verify.py
```

## Wynik sprawdzenia

Automatyczna próba: syntetyczna para 256 × 256, FP32, `full_default_cfg`,
znane przesunięcie drugiego obrazu X=+7, Y=−5 px, seed 20261102.

| Urządzenie | Dopasowania | Mediana X/Y [px] |
| --- | ---: | --- |
| CPU | 729 | +6,9977 / −4,9894 |
| CUDA, NVIDIA GeForce RTX 5090 | 729 | +6,9989 / −4,9911 |

Załadowano wszystkie parametry bez brakujących lub dodatkowych kluczy;
punkty i wyniki były skończone, błąd mediany w każdej osi poniżej 0,02 px.
Repozytorium modelu pozostało czyste. To weryfikacja pobrania, zgodności
bibliotek i wykonania modelu, bez oceny jakości na STM i bez odbioru GPU 8 GB.
Na etapie samego pobrania nie zmieniano kodu aplikacji i nie uruchamiano
pełnego zestawu jej testów. Późniejszą implementację i sprawdzenia opisuje
[karta REG-10](reviews/REG-10.md).
