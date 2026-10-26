# Issue 19 — lokalny graf cech i położenie siatki

Data: 2026-10-26. Kontynuacja [diagnozy PCA i epsilon](feature-separation-trial.md)
na polecenie „wykonaj kolejne badanie”. **Badanie wykonane; issue 19
pozostaje `claimed`, do omówienia. Nie przyjęto metody do aplikacji.**

**Wniosek:** lokalny graf potrafi ograniczyć scalenia różnych orientacji,
ale nadmiernie dzieli pojedynczą sieć i jest wrażliwy na początek siatki.
Nie rozwiązuje też ograniczenia narzuconego przez obecną ocenę porządku.
Żadna z 32 konfiguracji nie spełnia wszystkich warunków rozwojowych.

Prototyp: **`prototype/stmdomains-local-feature-graph`, `1ae0706`**, baza
`cf88e8a`. Nie scalać prototypu do aplikacji. Dokumentacja:
`domains/local-feature-graph-trial`, baza `e7b6ae0`.
[Manifest badania](local-feature-graph-manifest.json).

Samowystarczalny podgląd do otwarcia dwuklikiem:
`/home/rlew/projekty/NEtCAT-domains/.scratch/local-feature-graph/index.html`.
Zakładki „Obrót i jedna sieć”, „Granica i brak porządku”, „Przesunięcie
siatki”, „Pełne TTMAPP”. Porównanie przesunięcia pokazuje ten sam graf
na obu siatkach, a nie jednoczesną zmianę grupowania i próbkowania.
Można oglądać surowe obszary wyglądu, połączone fragmenty, dowód porządku
i końcowych kandydatów. Krzyżyki są próbkami siatki, okręgi centrami molekuł.

## Zakres i zamrożony protokół

Protokół zapisano przed obliczeniami: `local_feature_graph_design.json`,
SHA-256 `8ec1a45a9f5fc1084a1e7bd5e9a45c931bbf95979c28460d3fb936fc0ff854be`.
Nie dostrajano parametrów po obejrzeniu wyników.

- Te same **24 całe klatki TTMAPP** (1, 50, 100, 150, 200, 250–268)
  oraz **204 kontrole**, 34 przypadki × sześć ziaren.
- Osiem dotychczasowych baz: FFT/EWT/FCN/DINO × siatka/centra.
  Promień 24 px, sieci 112 × 112 i kontrast percentylowy. Cechy L2,
  zaokrąglenie do ośmiu miejsc i PCA24 zachowane z poprzedniej próby.
- **32 nowe konfiguracje grafu**: cztery skale 1/4/16/64 na każdą bazę.
  Osiem zapisanych wyników HDBSCAN to punkt odniesienia; osiem dodatkowych
  kontroli pokazuje maksymalny zakres przypisań przy obecnej bramce.
- Bez K oznaczającego liczbę domen, bez wzorców domen i bez treningu.
  PCA i skala odległości krawędzi są wspólne dla 24 klatek. Grafy nie
  mają połączeń między klatkami. Identyfikatory obszarów są lokalne
  dla klatki; **nie zbudowano wspólnego katalogu typów strukturalnych**.
- Użyto pełnych obrazów. Predykcje oraz parametry zapisano i zahashowano
  przed odczytem masek oceny, również dla próby przesuniętej siatki.

Wszystkie ziarna 1701–1703 i 2701–2703 oraz częściowe ramki były już
oglądane. To diagnoza rozwojowa, bez nowej niezależnej walidacji.
Tabele kontroli poniżej używają 2701–2703 dla porównania z poprzednimi
raportami; nie nazywamy ich już nieznanym zestawem testowym.

## Co zmieniono w grupowaniu

Zastosowano algorytm 1 [Felzenszwalba i Huttenlochera](https://cs.brown.edu/people/pfelzens/papers/seg-ijcv.pdf):
krawędzie rozpatrywane od najmniejszej różnicy łączą dwa obszary, gdy
różnica nie przekracza obu progów `Int(C) + k / |C|`. `Int(C)` opisuje
największą przyjętą krawędź drzewa obszaru, a `k` skalę tolerancji.
To metoda segmentacji grafu, bez wymaganej liczby segmentów.

Nasza adaptacja używa miejsc pobrania cech zamiast pikseli. Odległość
euklidesową w PCA dzielimy przez medianę dodatnich wag krawędzi całego
zakresu. Każda kontrola ma własną medianę. Siatka ma sąsiedztwo do
`12√2` px, centra do `min(24, 1.65 × mediana najbliższego sąsiada)`.
Wagi i sąsiedztwo nie korzystają z referencji. Brak wymuszonego
dołączania małych segmentów do większych.

Podział odbywa się na wszystkich miejscach z podparciem pomiaru ≥50%,
przed oceną porządku. Następnie stosujemy dokładnie poprzednią bramkę
ACF i reguły spójności: minimum cztery miejsca siatki albo osiem centrów.
Małe fragmenty pozostają odmową. Surowy segment wyglądu nie jest domeną.

Kontrola maksymalnego zakresu przypisuje wszystkim wspartym miejscom
jedną etykietę i wykonuje tylko niezmienioną bramkę oraz filtr spójności.
To **górne ograniczenie przypisań**, nie górne ograniczenie jakości
podziału i nie kolejny detektor. Każdy wynik grafu mieści się w tym zakresie.

## Kontrole: mniej scaleń, więcej fragmentów

Skala 4 jest przykładem z wcześniej ustalonego budżetu, nie wybranym
ustawieniem. Wszystkie skale są w HTML oraz `controls.csv`.

| Cecha / miejsca | Jedna sieć: HDBSCAN → graf 4, trzy ziarna | Obrót 8°: przypisanie HDBSCAN → graf 4 | Obrót 8°: błędne scalenia par HDBSCAN → graf 4 |
| --- | --- | ---: | ---: |
| FCN / siatka | 2/2/2 → 7/5/5 | 87.5% → 87.3% | 100% → 1.9% |
| FCN / centra | 4/4/4 → 5/5/5 | 68.8% → 74.9% | 100% → 0.9% |
| DINO / siatka | 2/3/3 → 4/7/7 | 86.6% → 87.3% | 20.9% → 8.5% |
| DINO / centra | 5/2/2 → 4/4/4 | 75.7% → 81.3% | 3.8% → 25.2% |

Niskie scalenia nie wystarczają: przy obrocie 8° graf 4 daje zarazem
39.9% błędów podziału par dla FCN/siatka i 42.6% dla FCN/centra.
Podziały i scalenia liczymy tylko wśród przypisanych par; obok podajemy
przypisanie, żeby odmowy nie udawały dobrej detekcji.

Mała skala często rozcina jedną sieć na liczne części. Przy skali 64
cztery neuronowe bazy nadal dają po dwie domeny na pojedynczej sieci,
a FCN/siatka ponownie całkowicie scala obrót 8°. Większa skala nie
naprawia obu błędów jednocześnie. FFT i EWT także nie spełniają kompletu
warunków. Żadnej konfiguracji nie zakwalifikowano do odbioru.

Na sześciu rodzajach negatywnych kontroli wszystkie nowe konfiguracje
mają zero końcowych fałszywych przypisań. Ochrona pochodzi z zachowanej
bramki porządku: surowy graf tworzy segmenty wyglądu także na szumie.
Wariant centrowy nie ma punktów na części kontroli szumu/pasów, więc
brak jego wyniku nie zastępuje oceny obrazowej siatki.

## Dlaczego dobre AUC wnętrz nie wystarczyło

Poprzednia próba porównywała całe, czyste wnętrza, z niepokrywającymi się
oknami. Teraz dodatkowo oceniono **rzeczywiste krawędzie grafu**:
odległości cech sąsiadów tej samej i różnych znanych domen. Okna mogą
przecinać granicę — to celowo inne pytanie, nie pogorszenie tej samej metryki.
Etykiety służą wyłącznie ocenie, bez dobierania progu krawędzi.

Średnie AUC z sześciu ziaren, dla obrotu 8°:

| Cecha / miejsca | Czyste wnętrza, poprzednia próba | Lokalne krawędzie, obecna próba | Oceniane krawędzie między domenami, razem |
| --- | ---: | ---: | ---: |
| FCN / siatka | 0.994 | 0.543 | 276 |
| FCN / centra | 1.000 | 0.947 | 54 |
| DINO / siatka | 1.000 | 0.760 | 276 |
| DINO / centra | 1.000 | 0.948 | 54 |

Wspiera to hipotezę, że informacja rozróżniająca odległe wnętrza nie
daje automatycznie wyraźnej lokalnej granicy. Zachowanie zależy też od
położenia i nakładania się okien. Nie wyznaczamy dokładnych konturów ani
statystycznej istotności z zależnych krawędzi. Dla centrów w kontrolach
rozstawu i granicy przesunięcia brak krawędzi z oboma końcami w pewnych
wnętrzach; wynik AUC jest null. Nie jest to dowód poprawności lub porażki
detekcji tych granic.

## TTMAPP: podział wyglądu i ograniczenie ACF

Końcowe molekuły w częściowych referencjach, mianownik **1678**:

| Cecha / miejsca | HDBSCAN | Graf 1 | Graf 4 | Graf 16 | Graf 64 | Limit obecnej bramki |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| FFT / siatka | 98 | 81 | 98 | 98 | 98 | 98 |
| FFT / centra | 34 | 30 | 34 | 34 | 34 | 34 |
| EWT / siatka | 86 | 60 | 76 | 82 | 86 | 86 |
| EWT / centra | 34 | 24 | 34 | 34 | 34 | 34 |
| FCN / siatka | 86 | 77 | 86 | 86 | 86 | 86 |
| FCN / centra | 34 | 23 | 34 | 34 | 34 | 34 |
| DINO / siatka | 86 | 67 | 86 | 86 | 86 | 86 |
| DINO / centra | 0 | 27 | 46 | 46 | 46 | 46 |

Limity odpowiadają około **2.0–5.8%** znanych oznaczeń. Wszystkie końcowe
przypisania nadal dotyczą BLACK; RED 0/101, YELLOW 0/274. DINO/centra
odzyskuje fragmenty przez zmianę grupowania, lecz nie rozwiązuje orientacji.
Nieznane obszary poza referencjami nie są traktowane jako podłoże.

Również podział **przed oceną porządku** jest niewystarczający. Przy skali 4
FCN/siatka i DINO/siatka zachowują odpowiednio 99.6% i 99.2% ocenianych
miejsc siatki, ale błędnie scalają 82.9% i 71.7% przypisanych par różnych
regionów. Dla centrów scalenia wynoszą 94.5% (FCN) i 79.7% (DINO).
Duże przypisanie obszarów wyglądu nie oznacza więc odkrycia domen.
Mianownik tej oceny to 1916 miejsc siatki lub 1678 centrów, zależnie od
trybu; nie mieszamy tych liczb z końcową oceną molekuł.

## Przesunięcie początku siatki

Osiem przypadków × sześć ziaren oraz klatki TTMAPP 1, 50, 250, 255, 268:
**53 całe obrazy**. Dwa modele, cztery początki siatki (przesunięcia
0/0, 6/0, 0/6, 6/6 px), cztery skale grafu. Razem **424 zestawy cech
i 1696 wyników grafu**. Cechy pobrano z rzeczywistych przesuniętych okien,
bez interpolacji starych wektorów. Utrzymano PCA całych 24 klatek,
skalę grafu oraz progi bramki; nie dopasowano katalogu do pięciu klatek.

Oceniono przypisania tych samych molekuł dostępnych w obu geometriach,
osobno zmianę odmów i relacji między parami. Dla jednej sieci końcowy
podział zmienia się w **144/144** porównań (6 ziaren × 2 modele × 4 skale
× 3 przesunięcia). To liczba powiązanych porównań, nie niezależnych obrazów.

Po zamrożeniu wyników wykonano dodatkowy, jawnie pomocniczy audyt:
wykluczono pas 30.5 px przy brzegu (24.5 px promienia + 6 px przesunięcia).
Nie zmieniano predykcji ani parametrów. Także we wnętrzu zmieniają się:

- jedna sieć: **69/144** podziałów;
- granica przesunięcia: **108/144**;
- obrót 8°: **144/144**;
- TTMAPP: **24/120** końcowych podziałów; przed bramką **85/120**.

Pozostałe zgodne wyniki mogą być puste. Zgodność odmowy nie jest dowodem
stabilnego wykrywania. Przesunięcie zmienia też liczebność próbek przy
brzegu, dlatego porównanie używa wspólnych dostępnych centrów, a audyt
wnętrza osobno ogranicza wpływ brzegu. Nie usunięto całkowicie wpływu
próbkowania — właśnie jego wrażliwość badamy.

## Weryfikacja i koszt

- **7296/7296** podziałów grafu zachowuje tę samą relację przypisań po
  permutacji punktów i krawędzi. **128** małych grafów zgodnych z osobną,
  wolną implementacją opartą na zbiorach; uwzględniono remisy i zera.
- **7296/7296** wyników mieści się w limicie niezmienionej bramki.
  Osiem starych konfiguracji daje 1824 zachowane wyniki przez odczyt;
  **nie przeliczano ponownie HDBSCAN** w tej próbie.
- **384/384** par kontroli braków 10/30/50% i lokalnej luki oznaczeń
  pozostawia niezmieniony wynik siatki.
- **106/106** świeżych zestawów cech przy przesunięciu zero jest bitowo
  identycznych z cache. Podparcie zgodne; projekcja PCA sprawdzona
  numerycznie. **424/424** wyników grafu przy przesunięciu zero jest
  identycznych z podstawowym przebiegiem. Wagi i bufory obu sieci bez zmian.
- Hashe wszystkich podstawowych i przesuniętych predykcji pozostają
  zgodne po ocenie. Metadane kontroli wybierają wyłącznie zadeklarowane
  przypadki; maski nie uczestniczą w ekstrakcji, transformacji ani grafie.
- **107 kontroli QtWebEngine**, bez błędów JS i poziomego przepełnienia;
  obejrzano podgląd i wykres. Składnia Python/Bash, lokalne linki i diff.
  To kontrola eksperymentu HTML, nie odbiór natywnego GUI aplikacji.

Lokalne netcat: Python 3.12.12, NumPy 2.2.5, SciPy 1.15.2, sklearn 1.6.1,
torch 2.9.1+cu128. Bez nowych instalacji lub pobierania wag. CPU:
jeden wątek BLAS/OpenMP; ekstrakcja cztery wątki Torch i RTX 5090.

| Etap | Czas | Szczyt pamięci procesu |
| --- | ---: | ---: |
| Krawędzie i skale z istniejącego PCA | 3.91 s | 186816 KiB RSS |
| Grafy podstawowe wraz ze sprawdzeniem permutacji | 26.95 s | 164668 KiB RSS |
| Przesunięta siatka: cechy i ponowna ACF | 55.02 s, w tym ACF 33.33 s | 1478120 KiB RSS |
| Grafy przesuniętych siatek i kontrola zera | 4.17 s | Nie mierzono osobno |

Maksymalnie alokowane tensory CUDA: 163117568 B (155.6 MiB), bez pełnej
pamięci procesu GPU i sterownika. To koszt tej próby, nie benchmark
268 klatek. Brak zakwalifikowanego kandydata do rozszerzenia pomiaru.

Wyniki: `controls.csv`, `edge-discrimination.csv`, `grid-origin-changes.csv`,
pełne JSON/NPZ, manifesty, protokół, HTML, wykres `graph-comparison.png`
i PDF. Kopia lokalna: **1555 plików / 367553595 B**, wszystkie SHA-256
zgodne. Względne symlinki prowadzą do zachowanych wcześniejszych cech
i PCA; sam HTML jest samowystarczalny. Duże dane i wagi pozostają poza Git.

Odtworzenie: `run_local_feature_graph.sh` i `README-local-feature-graph.md`
na gałęzi prototypu. Etapy uruchomiono osobno, wrapper sprawdzono składniowo.
Nie testowano produkcyjnej aplikacji, zapisu projektu ani eksportu programu.

## Następny krok

Nie ma podstaw do dalszego strojenia samej skali grafu jako rozwiązania
całego problemu. Badanie ujawnia dwa niezależne ograniczenia:
niestabilny podział lokalnego wyglądu oraz zbyt mały zakres przypisań
dopuszczany przez obecną ocenę porządku.

Najbliższa osobna próba może sprawdzić **skalę i podparcie kryterium
porządku ACF**, z zamrożonymi cechami/podziałami oraz kontrolami szumu
i pasów. Nie należy po prostu obniżać progu po obejrzeniu TTMAPP.
Nawet poprawa tej bramki nie rozstrzygnie scaleń i zależności od siatki;
dalszy kandydat opisu/granic musi przejść te kontrole. Wynik pozostaje
też punktem odniesienia dla planowanego treningu bez etykiet 20–23.
Nie uruchomiono go automatycznie ani nie wybrano metody do programu.
