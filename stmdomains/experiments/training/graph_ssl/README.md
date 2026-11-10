# Próba grafowa 24 — odtworzenie obliczeń

Pakiet wykonuje zamknięte porównanie geometrii otoczeń, własnego encodera
przed i po uczeniu oraz zachowanej procedury geometrycznej 15. Zakres,
hipotezę, budżet i kryteria określa
[protokół 24](../../../../docs/stmdomains/graph-self-supervised-protocol.md).
Poniższe polecenia opisują procedurę; nie są raportem skuteczności.

Uruchamiaj je z katalogu głównego repozytorium w istniejącym środowisku
`netcat`, z Pythonem, Torch/CUDA, NumPy, SciPy, scikit-learn i Pillow.
Implementacja nie potrzebuje DGL, PyG ani pobierania wag. Środowisko `.venv`
repozytorium nie zastępuje środowiska `netcat`. GPU musi być dostępne dla
procesu; bieżący audyt CUDA wymagał uruchomienia poza ograniczeniem urządzeń
sandboxa. Do obejrzenia HTML wystarczy przeglądarka; lokalny audyt GUI używa
także PyQt6/QtWebEngine.

Przykład wskazuje **nowy** katalog odtworzenia. Bieżące artefakty próby leżą
w `.scratch/graph-ssl-24/`. Poszczególne etapy odmawiają nadpisania istniejących
fitów i wyników. Nie usuwaj nieudanego runu w celu ponowienia tego samego fitu.

```bash
export OPENBLAS_NUM_THREADS=1
export OMP_NUM_THREADS=1
export CUBLAS_WORKSPACE_CONFIG=:4096:8
graph24_root=.scratch/graph-ssl-24-repeat
graph24_data=.scratch/training-20/data
```

## Wejście i przygotowanie grafów

Wejście pochodzi z zakończonego przygotowania 20:
`data/analysis/manifest.json`, 24 zapisane klatki i oznaczenia,
`data/split.json` oraz `data/manifest.json`. Sposób odtworzenia tego wejścia
z MPP i sesji oznaczeń opisuje [README przygotowania 20](../README.md).
Próba 24 nie importuje nowych pomiarów i nie zmienia podziału 20.

```bash
python -m stmdomains.experiments.training.graph_ssl.data \
  --data-root "$graph24_data" --output "$graph24_root"
```

`data` automatycznie wywołuje `controls.prepare`, jeżeli nie ma jeszcze
`controls/`. Sam `graph_ssl.controls` **nie ma osobnego CLI**. Powstają
93 kontrole: 31 rodzin × ziarna 920021–920023. Obrazy i geometria są w
`controls/analysis/`, a prawda, nazwy rodzin i ziarna w osobnym
`controls/evaluation/`. Generowanie kontrolowanej prawdy nie jest oceną
predykcji; przygotowanie grafów czyta następnie tylko `analysis/`.

W `prepared/` znajdują się manifest, tablice grafów i wiersze mapujące
korzenie na oryginalne ID, współrzędne oraz wsparcie. Każdy korzeń ma
otoczenie 72 × 72 jednostki odniesienia, najwyżej 128 węzłów i 57 cech
na węzeł. Model dostaje tylko `x`, binarną `adj` i maskę rzeczywistych
węzłów `valid`; surowe xy i indeksy geometrii służą przygotowaniu i eksportowi.
W TTMAPP jednostką pozostaje px, bez deklarowania kalibracji nm.

Przed fitami trzeba sprawdzić tożsamość wejścia, pełne wsparcie i liczebności.
Dla wejścia bieżącej próby oczekiwane liczby są następujące:

| Zakres | Liczba korzeni | Klatki |
| --- | ---: | --- |
| Transfer train | 76 | 1: 66, 50: 10; klatka 100 nie ma pełnego wsparcia |
| Transfer validation | 27 | 150: 19, 200: 8 |
| Transfer test | 831 | 250–268 |
| Transdukcja train | 3795 | Wszystkie 24 klatki |

Łącznie zapisano 6730 korzeni pomiarowych, w tym 3795 z pełnym wsparciem,
oraz 19629 korzeni syntetycznych, w tym 8350 z pełnym wsparciem.
Niedostępne korzenie pozostają w eksporcie z przyczyną odmowy. Nie są
zastępowane paddingiem udającym pomiar. Żaden dopuszczony korzeń treningowy
lub walidacyjny nie ma mniej niż dwóch węzłów. Te liczby opisują zależne
otoczenia jednej akwizycji, nie liczbę niezależnych przykładów materiału.

Poniższy odczyt ponownie sprawdza hashe cache i wejścia, odmawia dostępu
do referencji i zapisuje liczebności bez wykonywania treningu:

```bash
python - "$graph24_root" <<'PY'
from collections import Counter
import json
from pathlib import Path
import sys
import numpy as np
from stmdomains.experiments.training.graph_ssl.data import load_training_graphs
from stmdomains.experiments.training.graph_ssl.fit import deny_evaluation_paths

deny_evaluation_paths()
root = Path(sys.argv[1])
manifest = json.loads((root / "prepared/manifest.json").read_text())
assert manifest["total_samples"] == 117
expected = {("transfer", "train"): 76, ("transfer", "validation"): 27,
            ("transfer", "test"): 831, ("transductive", "train"): 3795}
audit = {}
for (regime, split), count in expected.items():
    graphs = load_training_graphs(root, regime, split)
    assert len(graphs) == count
    assert all(np.count_nonzero(g["valid"]) >= 2 for g in graphs)
    audit[f"{regime}/{split}"] = {
        "roots": len(graphs),
        "frames": dict(sorted(Counter(g["frame_id"] for g in graphs).items())),
    }
(root / "input-counts-audit.json").write_text(json.dumps(audit, indent=2))
print(json.dumps(audit, indent=2))
PY
```

W bieżącym przygotowaniu zachowano również `data-technical-audit.json`
(skończone cechy, translacja, permutacja, resampling, duplikaty i izolacja
otoczenia), `data-cache-replay-audit.json` (dokładna zgodność ponownie
obliczonych tablic i wierszy wszystkich 117 próbek), `data-split-audit.json`
oraz `data-preparation-resources.json`. To artefakty osobnych audytów sesji,
bez dodatkowego publicznego CLI. CPU/RSS pierwotnego przygotowania nie były
mierzone; zapisano osobno zmierzony, identyczny replay. Nie przedstawiaj jego
kosztu jako bezpośredniego pomiaru pierwszego wykonania.

## Audyt techniczny i zamrożenie planu

CPU sprawdza powtarzalny forward/backward bez aktualizacji wag. CUDA dodaje
audyt wznowienia: sześć kroków ciągłych kontra trzy, zapis i kolejne trzy.
Porównywane są wagi, optimizer, scheduler, RNG, sampler i losowane batche.
Łączny budżet technicznej optymalizacji to 12 kroków; dlatego CPU nie dostaje
`--resume-check`. Wagi tego audytu nie trafiają do fitów naukowych.

```bash
python -m stmdomains.experiments.training.graph_ssl.fit preflight \
  --data "$graph24_root" --output "$graph24_root/preflight-model-cpu.json" \
  --device cpu
python -m stmdomains.experiments.training.graph_ssl.fit preflight \
  --data "$graph24_root" --output "$graph24_root/preflight-model-cuda.json" \
  --device cuda --resume-check
python -m stmdomains.experiments.training.graph_ssl.prepare plan \
  --output "$graph24_root"
```

Audyt obejmuje też zgodność po permutacji węzłów oraz przypadek podwojenia
amplitudy celu: SCE pozostaje niewrażliwe na normę, a MSE odległości rośnie.
`plan` wymaga dodatniego audytu CUDA, najwyżej 12 kroków technicznych,
zgodnych hashy źródeł modelu i gotowego manifestu grafów. Zapisuje kod
numeryczny, protokół, konfigurację, liczniki danych i dokładną macierz
dziewięciu fitów. Po zamrożeniu nie zmieniaj przypiętych źródeł ani parametrów.
Galeria i dokumentacja nie dobierają modelu ani progów.

## Sześć fitów transferowych i trzy transdukcyjne

Wykonuj sekwencyjnie. Każdy transfer ma dokładnie 2000 prób kroku; checkpoint
powstaje co 100. Wyboru checkpointu dokonuje najmniejsza strata rekonstrukcji
na stałych maskach walidacyjnych, bez etykiet domen. Dla tego samego ziarna
oba cele mają tę samą inicjalizację, losowanie korzeni i maski.

```bash
for graph24_loss in sce_scale sce; do
  for graph24_seed in 20261101 20261102 20261103; do
    python -m stmdomains.experiments.training.graph_ssl.fit run \
      --data "$graph24_root" --output "$graph24_root" \
      --regime transfer --loss "$graph24_loss" --seed "$graph24_seed" \
      --steps 2000 --device cuda || exit 1
  done
done
```

`sce_scale` jest głównym celem: SCE + MSE dostępnych odległości. `sce` jest
wyłącznie diagnostyką. Transdukcja używa głównego celu i mediany wybranych
kroków jego trzech zakończonych transferów. Nie wybieraj liczby kroków
na podstawie kontroli, referencji ani wyglądu domen.

```bash
graph24_steps=$(python - "$graph24_root" <<'PY'
import json
from pathlib import Path
import statistics
import sys
root = Path(sys.argv[1])
runs = [json.loads((root / f"training/transfer/sce_scale/seed-{seed}/run.json").read_text())
        for seed in (20261101, 20261102, 20261103)]
assert all(run["status"] == "completed" for run in runs)
print(int(statistics.median(run["selected_step"] for run in runs)))
PY
)
for graph24_seed in 20261101 20261102 20261103; do
  python -m stmdomains.experiments.training.graph_ssl.fit run \
    --data "$graph24_root" --output "$graph24_root" \
    --regime transductive --loss sce_scale --seed "$graph24_seed" \
    --steps "$graph24_steps" --device cuda || exit 1
done
python -m stmdomains.experiments.training.graph_ssl.prepare audit-training \
  --output "$graph24_root"
```

Audyt sprawdza wybór kroków, parowanie inicjalizacji i batchy, zapisane
checkpointy, medianę transdukcji oraz łączny koszt. Limity wynoszą 900 s/fit,
8100 s wszystkich fitów, 8 GiB tensorów GPU, 12 GiB RSS i 10 GiB checkpointów.
Batch bez informacyjnego celu zużywa próbę kroku, ale pomija aktualizację;
run zapisuje oba liczniki. Nie ma zastępczych ziaren ani automatycznych prób
po niepowodzeniu. Checkpointy są zaufanymi lokalnymi archiwami Torch,
a nie formatem do otwierania nieznanych pobrań.

## Predykcje i ich zamrożenie

```bash
python -m stmdomains.experiments.training.graph_ssl.predict geometry \
  --output "$graph24_root"
python -m stmdomains.experiments.training.graph_ssl.predict encode \
  --output "$graph24_root" --device cuda
python -m stmdomains.experiments.training.graph_ssl.predict partition \
  --output "$graph24_root"
python -m stmdomains.experiments.training.graph_ssl.audit_predictions \
  --output "$graph24_root"
python -m stmdomains.experiments.training.graph_ssl.predict freeze \
  --output "$graph24_root"
```

Kolejność jest zależna: geometria zasila wspólną bramkę porządku i kontrolę
15, encoding zapisuje reprezentacje wyuczonych i własnych początkowych wag,
a partition dopasowuje transformacje i katalog wyłącznie na dozwolonym train.
Każda reprezentacja dostaje FH k=4 oraz MWS. Pełna procedura 15 pozostaje
osobnym porównaniem. Transfer pomiarowy ma dodatkowy plik z grafem wyłącznie
części testowej; pełna klatka jest tylko kontekstem podglądu.

`audit_predictions` sprawdza ukończone 4212 eksportów i 504 osobne grafy
testowe, zgodność ID/stanów, brak przypisań bez wsparcia, train adapterów,
przypisania katalogu oraz odtwarzalność procedury 15. Nie ocenia jakości
i odmawia odczytu referencji. W oryginalnym wykonaniu był dodatkowym
niezależnym audytem po zamrożeniu, bez zmiany wyników.

`frozen-predictions.json` przypina komplet zapisanych wyników, wejście
analityczne i kod. Trening oraz etapy `predict` mają blokadę odczytu ścieżek
referencji. Do tego miejsca nie otwieraj `controls/evaluation/` ani referencji
pomiarowych w celu wyboru parametrów. Kontrole nie są danymi treningowymi,
walidacyjnymi ani źródłem progów. Łączny budżet pozostałych etapów wynosi
7200 s CPU i 12 GiB RSS; pliki zasobów zachowuj także przy niepowodzeniu.

## Ocena, raport i galeria

Dopiero po `freeze` wolno otworzyć prawdę do oceny. Ewaluator najpierw
weryfikuje zamrożenie, potem wczytuje referencje. Używa osobnego grafu
testowego dla transferu, wszystkich zapisanych kontroli i uprzednio
określonych kryteriów. Nie dopasowuje predykcji ponownie.

```bash
python -m stmdomains.experiments.training.graph_ssl.evaluation \
  --output "$graph24_root" \
  --controls-evaluation "$graph24_root/controls/evaluation" \
  --measurement-evaluation .scratch/unsupervised-input/evaluation
python -m stmdomains.experiments.training.graph_ssl.summary \
  --output "$graph24_root"
python -m stmdomains.experiments.training.graph_ssl.gallery \
  --output "$graph24_root"
```

Domyślne wyjścia to `evaluation/`, `report/` i `index.html`.
`evaluation` dopuszcza `--evaluation-output`; `summary` dopuszcza
`--report-output`, ale czyta ocenę z `OUTPUT/evaluation`.
Galeria może dostać `--evaluation DIR` i `--controls-evaluation DIR`.
Czyta tylko zapisane wyniki, obrazy i metadane nazw kontroli po zakończonej
ocenie; nie wykonuje inferencji w przeglądarce.

W galerii kółka są rzeczywistymi centrami wejściowych oznaczeń, a żółta ramka
pokazuje otoczenie grafu. Przypisany udział centrów nie oznacza wykrywalności
molekuł ani powierzchni materiału. Puste wejście szumu/pasów nie potwierdza
umiejętności odrzucania takich obrazów. Dla procedury 15 oba panele pokazują
ten sam wynik końcowy, ponieważ nie zapisano oddzielnego etapu przed odmowami.

Wersjonowany harness QtWebEngine wykonuje przejścia przez selektory,
scenariusze, zakres testowy, widoczność oraz kliknięcie
rzeczywistego centrum i zapisuje pięć zrzutów:

```bash
python -m stmdomains.experiments.training.graph_ssl.check_browser \
  "$graph24_root/index.html" \
  --out "$graph24_root/gallery/browser"
```

Harness jest narzędziem QA, nie częścią danych wejściowych ani
kryteriów naukowych. Wynik GUI trzeba uzupełnić oględzinami zrzutów;
poprawne działanie przełączników nie potwierdza poprawności domen.
Duże dane, checkpointy, raporty szczegółowe i HTML pozostają poza Git.
