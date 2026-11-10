# Maskowane odtwarzanie obrazu — prototyp 25

Mały konwolucyjny AE32 z próby 21 uczy się odtwarzać zakryte bloki 16×16
wejścia 64×64. Mask25/50 ukrywają dokładnie 4/8 z 16 bloków. Strata obejmuje
wyłącznie zakryte, rzeczywiście zmierzone piksele. To inspiracja zadaniem MAE,
a nie odtworzenie architektury ViT-MAE. Pytanie dotyczy użyteczności cech dla
podziału domen, nie samej jakości rekonstrukcji.

Parametry, kryteria, zakres wniosków i limity:
[protokół25](../../../../docs/stmdomains/masked-autoencoder-protocol.md).
Kod jest prototypem badawczym; nie jest wdrożony do aplikacji.

Wykonana próba: [raport 25](../../../../docs/stmdomains/masked-autoencoder-trial.md).
12 fitów zakończono; rekonstrukcja poprawiła się, końcowe domeny TTMAPP nie.
Galeria tej realizacji: `.scratch/masked-ae-25/index.html`.

## Wejście i środowisko

Potrzebne są niezmienione lokalne artefakty 20, 21 i 22 oraz istniejące
środowisko `netcat` z Torch/CUDA, NumPy, SciPy, scikit-learn, Pillow,
Matplotlib i PyQt6/QtWebEngine. Niczego nie pobieramy ani nie instalujemy.
W tej konfiguracji interpreter znajduje się pod poniższą ścieżką.

```bash
masked25_python=${NETCAT_PYTHON:-/home/rlew/projekty/conda-migration-ubuntu-20261008/envs/netcat/bin/python}
masked25_output=.scratch/masked-ae-25-repeat
export OMP_NUM_THREADS=1
export MKL_NUM_THREADS=1
export OPENBLAS_NUM_THREADS=1
export NUMEXPR_NUM_THREADS=1
```

Uruchamiaj z katalogu głównego repozytorium. Wybierz nowy katalog wynikowy;
etapy odmawiają zastąpienia poprzednich wyników. Zachowuj także nieudane
próby i ich koszt. Powtórzenie całego eksperymentu jest odtworzeniem,
a nie dodatkowym wariantem pierwotnej próby.

## Przygotowanie i zamrożenie

```bash
"$masked25_python" -m stmdomains.experiments.training.masked_ae.prepare controls \
  --output "$masked25_output"
"$masked25_python" -m stmdomains.experiments.training.masked_ae.audit_predictions technical \
  --output "$masked25_output"
"$masked25_python" -m stmdomains.experiments.training.masked_ae.fit preflight \
  --data .scratch/training-20 --output "$masked25_output/preflight-cuda.json" \
  --device cuda --resume-check
"$masked25_python" -m stmdomains.experiments.training.masked_ae.prepare plan \
  --prepared .scratch/training-20 --baseline-ae .scratch/autoencoder-21 \
  --baseline-ssl .scratch/local-ssl-22 --output "$masked25_output"
```

Preflight sprawdza maskowanie, gradienty, zmierzone wsparcie, zgodność
inicjalizacji i danych z AE21 oraz krótkie techniczne wznowienia. Wagi
techniczne są odrzucane. Docelowa macierz obejmuje 12 fitów: 2 maski × 3 ziarna
×transfer/transdukcja. Zapisane AE21 i SSL22 oraz FFT nie są ponownie uczone.
`plan.json` przypina wszystkie numeryczne źródła, protokół, wejścia i użyte
artefakty baz. Po tym kroku nie zmieniaj kodu interpretującego próbę.

## Trening i zapisane predykcje

```bash
"$masked25_python" -m stmdomains.experiments.training.masked_ae.run_fits \
  --output "$masked25_output" --device cuda
"$masked25_python" -m stmdomains.experiments.training.masked_ae.audit_training \
  --output "$masked25_output"
"$masked25_python" -m stmdomains.experiments.training.masked_ae.prepare cache \
  --output "$masked25_output"
"$masked25_python" -m stmdomains.experiments.training.masked_ae.predict encode \
  --output "$masked25_output" --device cuda
"$masked25_python" -m stmdomains.experiments.training.masked_ae.predict partition \
  --output "$masked25_output"
"$masked25_python" -m stmdomains.experiments.training.masked_ae.audit_predictions exports \
  --output "$masked25_output"
"$masked25_python" -m stmdomains.experiments.training.masked_ae.predict freeze \
  --output "$masked25_output"
```

Transfer kończy 2000 kroków i wybiera checkpoint ze stałej nieetykietowanej
walidacji. Transdukcja trwa medianę wybranych kroków własnej maski; brak
trzech poprawnych transferów pomija tę rodzinę. Nie ma automatycznych
restartów lub zastępczych ziaren. Pełny stan obejmuje osobne RNG maskowania
i augmentacji. Budżet: 900 s/fit, 10 800 s fitów łącznie, 7200 s CPU pozostałych
etapów, 8 GiB tensorów GPU, 12 GiB RSS i 10 GiB checkpointów.

32 reprezentacje × 117 obrazów × 3 skale × 2 samplery × 2 solvery = 44 928 wyników.
Transfer zachowuje osobny graf testowy: 4608 archiwów, z czego 960 pustych
w pięciu klatkach spoza testu. Wagi wnioskowania otrzymują **oryginalny
niezakryty pomiar**. Rekonstrukcja nie służy jako obraz do znajdowania domen.
Bazy na TTMAPP są kopiowane bitowo; nowe 93 kontrole otrzymują nowe inferencje
starymi modelami i adapterami. Referencje nie są wejściem tych etapów.

## Ocena i galeria

Po zamrożeniu predykcji można otworzyć referencje do oceny:

```bash
"$masked25_python" -m stmdomains.experiments.training.masked_ae.evaluate \
  --output "$masked25_output"
"$masked25_python" -m stmdomains.experiments.training.masked_ae.diagnostics \
  --output "$masked25_output" --prepared .scratch/training-20 --device cuda
"$masked25_python" -m stmdomains.experiments.training.masked_ae.gallery \
  --output "$masked25_output"
"$masked25_python" -m stmdomains.experiments.training.masked_ae.check_browser \
  "$masked25_output/index.html" --out "$masked25_output/gallery/browser"
"$masked25_python" -m stmdomains.experiments.training.masked_ae.summarize \
  --output "$masked25_output" --manifest "$masked25_output/result-manifest.json"
```

Główny wynik to **mask50, siatka 48 px**. Mniejsze maskowanie, pozostałe skale
i centra są diagnostyką. Porównania wspólnych ID/pokrycia i stabilności
odnoszą się do głównej siatki; pełne metryki zachowują pozostałe konfiguracje.
Ocena przekazuje również nieocenialne wartości, wszystkie ziarna i oba
etapy przed/po odmowach. Treningi nie wybierają progów na podstawie domen.

`index.html` otwiera się bez serwera i zawiera zapisane nakładki oraz figury
rekonstrukcji/treningu. Punkty są **środkami okien siatki**, nie wykrytymi
molekułami. Przełącznik osobnego grafu testowego oddziela ocenę transferu
od pełnej nakładki. Kolor nie oznacza automatycznie typu struktury.
Audyt przeglądarki zapisuje interakcje i zrzuty; obejrzyj zrzuty wizualnie.

Nowe ziarna kontroli są realizacjami znanych rodzin. TTMAPP jest wielokrotnie
oglądaną jedną akwizycją z częściowymi referencjami. Przypisanie centrów nie
jest wykrywalnością molekuł ani powierzchnią materiału. Niższy błąd
rekonstrukcji nie zastępuje jakości granic domen. Duże wyniki pozostają lokalne.
