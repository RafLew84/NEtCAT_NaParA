# Prototyp 24a — diagnoza kontekstu zamrożonego grafu

Pakiet porównuje trzy sposoby podania otoczenia do istniejących encoderów
z próby 24. Nie wykonuje nowych treningów, kroków optymalizacji ani ponownego
dopasowania adapterów, PCA, progów lub katalogów. Zakres i kryteria ustalono
w [protokole 24a](../../../../docs/stmdomains/graph-context-boundary-protocol.md).
Poniższa instrukcja opisuje odtworzenie procedury, bez oceny jej wyników.

Wejściem jest **kompletna, zamrożona próba 24** z
`frozen-predictions.json`, cache, wagami, adapterami i predykcjami.
Polecenie `trial plan` sprawdza przypięte pliki źródłowe i zapisuje ich hashe.
Źródłowy katalog 24 pozostaje wejściem tylko do odczytu. Nie wolno użyć go
jako katalogu wynikowego 24a.

## Środowisko i nowy katalog wynikowy

Uruchamiaj z katalogu głównego repozytorium, w istniejącym środowisku `netcat`.
W tej konfiguracji interpreter znajduje się pod poniższą ścieżką. Można
wskazać równoważny interpreter przez `NETCAT_PYTHON`; wymagane są istniejące
Torch, NumPy, SciPy, scikit-learn i Pillow. Audyt przeglądarki korzysta także
z PyQt6/QtWebEngine. Nie instalujemy bibliotek ani nie pobieramy wag.

```bash
graph24a_python=${NETCAT_PYTHON:-/home/rlew/projekty/conda-migration-ubuntu-20261008/envs/netcat/bin/python}
graph24a_source=.scratch/graph-ssl-24
graph24a_root=.scratch/graph-context-24a-repeat
export OMP_NUM_THREADS=1
export MKL_NUM_THREADS=1
export OPENBLAS_NUM_THREADS=1
export NUMEXPR_NUM_THREADS=1
```

Wszystkie obliczenia numeryczne są wykonywane **na CPU, z jednym wątkiem**.
Nie uruchamiaj preflightów GPU ani poleceń treningowych z 24 w ramach tej
próby. Budżet 24a wynosi 1800 s CPU łącznie i 4 GiB RSS na proces.

Przykład celowo używa nowego katalogu `graph-context-24a-repeat`.
Katalog nie powinien zawierać wcześniejszego planu, predykcji, audytu lub
raportu. Poszczególne etapy odmawiają nadpisania wcześniejszej próby.
Zachowuj również ewidencję nieudanego etapu; nie usuwaj jej w celu
automatycznego ponowienia lub powiększenia budżetu.

## Stała macierz i zakres danych

Próba obejmuje wyłącznie 93 **znane kontrole 24**, z istniejącymi ziarnami
920021–920023. Nie jest nową oceną held-out, nie tworzy nowych kontroli
i nie obejmuje ponownej oceny TTMAPP, transdukcji ani modelu SCE-only.

| Tryb | Wejście |
| --- | --- |
| `closed72` | Dokładne cache i predykcje 24; zamknięte otoczenie 72 |
| `halfopen72` | Otoczenie `[-36,36)` w obu osiach, z promieniem krawędzi przypiętym z `closed72` |
| `root_only` | Oryginalne 57 cech centrum, jeden węzeł z pętlą własną, te same dwie warstwy encodera |

`root_only` jest ablacją agregacji, a nie naprawionym lub ponownie
wytrenowanym GNN. Dolna granica `halfopen72` to `delta >= -36 - 1e-10`,
górna to `delta < 36 - 1e-10`. Opis samego centrum musi pozostać identyczny.

Macierz ma **19 reprezentacji × 2 solvery × 93 kontrole = 3534 wyniki**:
jedna klasyczna `root57` oraz trzy tryby × wagi początkowe/wyuczone × trzy
ziarna głównego encodera transferowego 24, 20261101–20261103. Solvery to
FH k=4 i MWS. Wagi, adaptery, graf podziału oraz bramka geometryczna z 24
pozostają przypięte.

Każdy wariant zachowuje te same 8350 dostępnych centrów **S24**, ich ID,
wsparcie 72, jednostki i mianownik. Brak przypisania nie usuwa centrum
z mianownika. Audyt dwóch kroków agregacji i obwiedni opisów R24 jest
diagnostyką wymaganego kontekstu; nie filtruje S24 i nie dodaje halo.
Nie ma paddingu udającego pomiar, odbicia punktów ani poszerzania pola.

## Plan, predykcje i audyt techniczny

Wykonuj etapy kolejno. Do następnego przechodź dopiero po pomyślnym
zakończeniu poprzedniego.

```bash
"$graph24a_python" -m stmdomains.experiments.training.graph_context.trial plan \
  --source "$graph24a_source" --output "$graph24a_root"
"$graph24a_python" -m stmdomains.experiments.training.graph_context.trial predict \
  --output "$graph24a_root"
"$graph24a_python" -m stmdomains.experiments.training.graph_context.audit \
  --output "$graph24a_root"
```

Plan zapisuje bezwzględną ścieżkę wejścia, macierz, limity, protokół oraz
hashe pięciu źródeł numerycznych: `__init__.py`, `representation.py`,
`trial.py`, `evaluation.py` i `audit.py`. **Po zamrożeniu nie zmieniaj tych
źródeł ani protokołu.** `predict` i kolejne sprawdzenia korzystają z wejścia
zapisanego w planie; `--source` wybiera je na etapie `plan`.

Predykcja kopiuje oryginalne cechy i etykiety `closed72`/`root57`. Pozostałe
wejścia przechodzą przez zamrożone encodery na CPU i oryginalne adaptery 24.
Kroki optymalizatorów są zablokowane, wagi mają wyłączone gradienty,
a wykonanie zapisuje dowód zerowej liczby kroków i refitów w `execution.json`.
Wejścia, cechy, certyfikaty zależności i wyniki pozostają osobnymi artefaktami.

Audyt zapisuje `audits/technical.json`. Sprawdza pełną macierz, tożsamość
ID, wsparcia i grafu, przypisania/odmowy, zgodność NPZ z eksportem JSON,
niezmienione adaptery i pliki 24 oraz mechanikę brzegów, permutacji,
translacji i paddingu. Replay CPU starego encodera jest wyłącznie kontrolą
numeryczną z `atol=rtol=1e-5`; nie zastępuje oryginalnych etykiet bazowych.
Poprawny audyt techniczny nie potwierdza poprawności domen.

Referencje domen nie są argumentem tych poleceń. `trial` oraz `audit`
blokują odczyt ścieżek oceny; nazwy kontroli, prawda i jakość kandydatów
nie służą do dopasowania nowych parametrów.

## Zamrożenie i dopiero potem ocena

Po dodatnim audycie przypnij wszystkie predykcje, a następnie uruchom ocenę:

```bash
"$graph24a_python" -m stmdomains.experiments.training.graph_context.trial freeze \
  --output "$graph24a_root"
"$graph24a_python" -m stmdomains.experiments.training.graph_context.evaluation \
  --output "$graph24a_root"
```

`freeze` zapisuje `frozen-predictions.json`. Ewaluator weryfikuje całe
zamrożenie przed odczytem referencji. Domyślnie bierze znane kontrole
z `plan.source_root/controls/evaluation`; opcja `--controls-evaluation`
pozwala jawnie wskazać ten katalog. `--evaluation-output` zmienia katalog
oceny, ale domyślna galeria oczekuje `OUTPUT/evaluation`.

Nie ma osobnego CLI `summary` w tym pakiecie. Polecenie `evaluation` samo
zapisuje `evaluation/report.md`, `summary.json`, pliki JSON/CSV porównań
i kryteriów oraz `evaluation/evidence.json`. Kryteria obejmują artefakt
pojedynczej sieci, rzeczywiste granice i brak regresji; zapis obejmuje
każde ziarno oraz etapy przed i po odmowach.

## Galeria i sprawdzenie przeglądarki

Galeria wymaga zakończonej oceny wskazującej ten sam freeze:

```bash
"$graph24a_python" -m stmdomains.experiments.training.graph_context.gallery \
  --output "$graph24a_root"
"$graph24a_python" -m stmdomains.experiments.training.graph_context.check_browser \
  "$graph24a_root/index.html" --out "$graph24a_root/gallery/browser"
```

Samowystarczalny `index.html` pokazuje bazę `closed72` po lewej i wybrany
`halfopen72`/`root_only` po prawej, z tymi samymi wagami, ziarnem i solverem.
Klasyczna geometria pokazuje identyczny wynik po obu stronach. Przełącznik
zmienia etap przed/po odmowach; kółka odpowiadają rzeczywistym centrom,
a żółty obrys oznacza niezmienione wsparcie S24, także w ablacji.
Przeglądarka nie wykonuje inferencji.

Harness używa QtWebEngine offscreen z renderowaniem programowym, przechodzi
przez 26 par konfiguracji, pięć scenariuszy i przełączniki oraz zapisuje
`gallery/browser/browser-check.json` i trzy zrzuty. Sprawdzenie automatyczne
uzupełnij oględzinami zrzutów. Weryfikacja galerii nie jest oceną skuteczności.

Etapy zachowują osobne `*.resources.json`, w tym `gallery.resources.json`
i `browser.resources.json`; raportują także niepowodzenie. Liczba
przypisanych centrów nie jest wykrywalnością molekuł ani powierzchnią
materiału. Puste grafy szumu i pasków nie dowodzą rozpoznawania negatywnych
obrazów. Duże artefakty, wejście 24 i HTML pozostają lokalne, poza Git.
