# Protokół treningu i porównania domen — issue 20

Wersja `stmdomains-training-plan-v1`, 2026-10-31. Realizacja przygotowania
[20](issues/20-self-supervised-training-preparation.md), wspólna dla
[21](issues/21-autoencoder-domains.md), [22](issues/22-local-self-supervised-domains.md)
i decyzji [23](issues/23-training-comparison-and-next-step.md).
Parametry są zapisane także w
[experiment-plan.json](../../stmdomains/experiments/training/experiment-plan.json).
To zamknięty zakres przyszłego porównania, nie raport treningu ani dowód
skuteczności. Implementacja AE/rVAE/SSL, relacji i solverów należy do 21/22.

## Dane i dwa oddzielne protokoły

Wejście zachowuje [kontrakt 14](experiment-input-protocol.md): raw MPP,
geometrię pomiaru i opcjonalne bieżące centra. Zakres to 24 klatki:
1, 50, 100, 150, 200 i 250–268. Ramki, prawda syntetyczna, kolory i dawne
etykiety domen nie trafiają do treningu, wyboru checkpointu ani transformacji
cech. Zmiana referencji ma pozostawić wszystkie te artefakty i predykcje
identyczne. Użycie centrów nigdy nie zmienia próbek regularnej siatki.

Podział ustala się przed generowaniem wycinków. Dla obecnego płótna
wyrównanego 480 × 408 px obowiązuje:

| Część transferu | Blok klatek | Dostępne klatki pilota | Pas X na płótnie expanded |
| --- | --- | --- | --- |
| train | 1–100 | 1, 50, 100 | [320, 480] |
| validation | 150–200 | 150, 200 | [160, 320] |
| test | 250–268 | wszystkie 19 | [0, 160] |

Klatki 101–149 i 201–249 są buforem czasowym. Przy wewnętrznych granicach
pasów 160 i 320 pozostaje po 8 px bufora po obu stronach. Każde rzeczywiste
wsparcie, obejmujące największy użyty wycinek, przesunięcie augmentacji
i interpolację, musi w całości mieścić się w swoim pasie oraz pomiarze.
Transformacja to `expanded_xy = raw_edge_xy + origin_in_expanded_xy`;
manifest zapisuje rzeczywiste granice i przyczynę niedostępności okna.
Nie dopasowywać podziału do liczby udanych okien lub wyników domen.

Normalizację `clip((image-low)/(high-low), 0, 1)` dopasowuje się raz:
low/high to kwantyle 2/98% skończonych wartości raw z dozwolonych obszarów
train, bez wielokrotnego ważenia tych samych pikseli nakładającymi się
wycinkami. Te same statystyki dotyczą
validation/test. Jeżeli cały zbiór dopasowania ma high<=low, przygotowanie
zgłasza błąd; pojedynczy stały wycinek jest poprawnym wejściem, a jego
brak porządku lub dowodu ocenia metoda. Niepełne wsparcie jest niedostępne.
PCA, skala odległości, progi relacji i ewentualny katalog też używają
wyłącznie train. Validation służy wyborowi checkpointu po stracie bez etykiet.
Test nie dopasowuje normalizacji, PCA, katalogu ani reguł podziału. Samo
zastosowanie zamrożonej reguły grafowej do nowej klatki jest inferencją;
wspólny fit z testem byłby innym, transdukcyjnym badaniem.

**Ograniczenie:** większość zapisanych rejestracji ma niską wiarygodność.
Bufor 8 px jest konwencją geometryczną, nie skalibrowanym ograniczeniem
błędu rejestracji. Rozłączne wsparcia potwierdzają brak przecięcia w zapisanym
układzie; jedna skorelowana akwizycja nie daje dowodu niezależności fizycznej
ani generalizacji na nową akwizycję. Publikować liczby dostępnych okien
w każdej części oraz ten zakres wniosku.

**Transdukcja** ma osobny run, fit normalizacji/PCA/relacji na wszystkich
24 pełnych polach i wspólny katalog tego zakresu. Jest opisem tej serii.
Nie używa rezultatów testu ani ramek do wyboru wariantu lub czasu treningu.
Wykonuje z góry ustalone refity `z32`: liczba kroków to mediana kroków
checkpointów wybranych na validation w trzech transferowych runach `z32`
danej rodziny. Jeżeli nie ma trzech poprawnych transferowych runów z32,
refit tej rodziny pomijamy z podanym powodem; bez zastępczych seedów lub
dodatkowych fitów. Zapisuje ostatni checkpoint tych kroków. Nowy fit nie zmienia
wcześniej zamrożonych predykcji i oceny transferu.

## Wycinki, augmentacje i konfiguracje treningu

Głównym samplerem jest regularna siatka o kroku 16 px; generator zapisuje
pozycję, pełne wsparcie i dostępność wszystkich miejsc. Wycinki 32, 48 i
64 px są resamplowane do tensora 64 × 64 z zachowaniem informacji o skali.
Nie dodawać gamma, paddingu, losowego skalowania ani obrotów jako par
pozytywnych. Wszystkie poprawne centra stanowią osobną diagnostykę tych
samych zamrożonych modeli, bez wybierania tylko centrów w referencjach.

Trening losuje równo skale 32/48/64 i klatki dostępne w train; wewnątrz
klatki losuje jednostajnie dostępne miejsca siatki. Skala 48 px jest
jedyną główną skalą porównania 2 × 2. Zastosowanie tych samych wag w 32/64
jest z góry ustaloną diagnostyką, bez nowych treningów lub wyboru najlepszej
skali. Miejsca bez kompletnego wsparcia pozostają w tabeli jako odmowy.

Dwa widoki SSL pochodzą z tego samego miejsca: niezależne przesunięcie
każdej osi ciągle i jednostajnie z [-2,2] px, gain jednostajnie [0.9,1.1], offset
[-0.1,0.1] i szum Gaussa z sigma losowaną z [0,0.03] po normalizacji.
Pozycje lokalnych tokenów porównuje się po odwróceniu znanego przesunięcia,
wyłącznie we wspólnym rzeczywistym wsparciu. Sąsiedni wycinek lub klatka
nie jest pozytywną parą tylko z powodu bliskości. AE/rVAE otrzymuje te same
zakłócenia fotometryczne, lecz odtwarza czysty, odpowiadający przestrzennie
wycinek; nie miesza celu z przypadkowo przesuniętym miejscem.

| Ticket | Rodzina | Konfiguracje transferu | Rola |
| --- | --- | --- | --- |
| 21 | konwolucyjny AE | z16, z32 | mały punkt odniesienia |
| 21 | ciągły rVAE | z16, z32 | główny kandydat wydzielający obrót |
| 22 | lokalne SSL | z16, z32 | główny kandydat relacji lokalnych |

Wymiary z16/z32 dotyczą ciągłych cech, nie liczby domen. W każdej rodzinie
jest jeden encoder z kanałami 16/32/64, trzema blokami konwolucyjnymi
3 × 3, krokiem 2, GELU, bez BatchNorm, oraz głową do wskazanego wymiaru.
Implementacja zapisuje dokładny model i hash kodu przed uruchomieniem;
ewentualna konieczna różnica przestrzennego dekodera rVAE musi być jawna.
rVAE dodaje ciągły kąt i translację, bez części kategorycznej lub zadanej
symetrii M6. Dekoder rVAE obraca współrzędne i podaje je wraz z latentem
do MLP odtwarzającego intensywność; nie używa niedeterministycznego CUDA
backward `grid_sample`. Kąt kodera nie jest automatycznie wiarygodnym kątem sieci.
SSL zachowuje lokalną mapę cech i dopasowuje pozycje, nie tylko globalną
średnią obrazu. Przyjęte wagi celu zgodności/wariancji/kowariancji to
25/25/1; docelowe std cechy to 1, epsilon 1e-4. AE używa MSE; rVAE
MSE z KL ważonym 1e-3, z liniowym wzrostem tej wagi w treningu przez
pierwsze 200 kroków. Walidacja rVAE od początku używa stałej wagi KL
1e-3, aby checkpointy porównywać według tego samego celu.
Wszystkie rodziny używają AdamW, lr 1e-3, weight decay 1e-4, gradient clip
norm 1, bez harmonogramu lr; wartości nie są strojone na domenach.

Trzy ziarna treningu: **20261101, 20261102, 20261103**. Transfer to
2 konfiguracje × 3 ziarna × 3 rodziny = **18 fitów**. Transdukcja to
z32 × 3 ziarna × 3 rodziny = **9 fitów**. Łącznie najwyżej **27 fitów**;
scales, solvery i stany przed/po odmowach nie mnożą treningów. `z32` jest
głównym raportowanym kandydatem, `z16` diagnostyką, bez wyboru zwycięzcy
po ocenie końcowej. W 22 zapisuje się dodatkowo cechy encodera z32 sprzed
pierwszego kroku dla tych samych trzech ziaren; to kontrola uczenia,
nie kolejne modele do strojenia. Zwykły VAE, wariant wejścia FFT i INPAINTAFF
nie należą do tego budżetu.

Limit jednego transferowego runu to **2000 kroków optymalizatora**.
Batch efektywny 64, float32, bez AMP i akumulacji; sampler ze zwracaniem
zawsze daje 64 próbki treningowe. Checkpoint co 100 kroków; wybór najmniejszej średniej straty
walidacyjnej, remis rozstrzyga wcześniejszy krok. Walidacja ma stałe,
zapisane transformacje i kolejność, bez zmiany seed przy każdym checkpointcie.
Degenerację SSL raportować także przez std i efektywny rząd cech; stały
opis lub niefinite strata kończą run jako nieudany technicznie, bez restartu
z nową konfiguracją. Koszt utraconego runu pozostaje w budżecie.

Administracyjny limit to **15 minut na fit**, najwyżej **6 h 45 min**
łącznie dla 27 fitów, **8 GiB tensorów GPU**, **12 GiB RSS**,
**10 GiB checkpointów** dla całego cyklu oraz **2 h CPU postprocessingu**.
Są to pułapy kosztu, nie prognozy czasu. Pierwsze 100 kroków docelowej
architektury mierzy się w ramach jej runu i limitu, bez osobnych treningów.
Przekroczenie kończy run z zachowaniem checkpointu i powodu, bez zwiększania
budżetu. Czas walidacji i zapisu checkpointów wlicza się do limitu fitu.

Pomiary GPU i hash raportu technicznego są wiązane z planem w
`measured_budget`. Próba techniczna na RTX 5090 dała dla batch64 medianę
3.03 ms/krok małego AE, maksimum 95 367 168 B tensorów i 100 663 296 B
zarezerwowanej pamięci alokatora. Szczyt RSS całego procesu pomiarowego
wyniósł 1 704 796 160 B. Trzy wznowienia 6 kroków wobec 3+3 były bitowo
zgodne; sprawdzono także rotację współrzędnych i MLP, reparametryzację
oraz lokalny cel SSL. To wyniki małej próby technicznej, bez jakości domen.
Nie szacować pełnego rVAE/SSL wyłącznie z tej przepustowości.
Dopuszczalny wynik całej próby jest negatywny.

## Jeden punkt odniesienia i porównanie 2 × 2

Jedyna zachowana baza historyczna to **`fft-grid--fh4`** z
[lokalnego grafu issue 19](local-feature-graph-trial.md), prototyp
`prototype/stmdomains-local-feature-graph@1ae0706`; jego baza cech ma ID
`fft-grid-r24-s0-classic-e1.5-windowed_acf`. FFT pochodzi z
[17](image-texture-domains-trial.md), `prototype/stmdomains-texture@3bb4d36`.
Historyczny manifest [19](local-feature-graph-manifest.json) i lokalne
`bases.json`/`protocol.json` określają pochodzenie. Wybór k=4 ustala jeden
udokumentowany przykład; nie oznacza, że wygrał stare porównanie.
FFT nie wymaga nowych wag i zachowuje jawne częstotliwości oraz kierunki;
FH zapewnia zachowany podział grafu do porównania z MWS.

Historyczne próbki miały 49 px, stride 12, odjęcie Gaussa sigma 3 z całej
klatki i RMS klatki. Nie wolno ukryć zmiany danych pod starym ID. Wspólna
baza nowych czterech pól to **`fft48-grid16--fh4-training20-v1`**:
pełne 48 px, stride 16, zamrożona normalizacja train, odjęcie średniej
wycinka, Hann i pierwiastek unormowanej mocy na 12 częstotliwościach
1/28–1/6 cyklu/px oraz 18 kierunkach modulo pi. Usunięcie globalnego
Gaussa/RMS zapobiega czytaniu poza własną częścią transferu i niejawnemu
poszerzeniu wsparcia. To jawna adaptacja mechanizmu FFT/FH; stare metryki
nie są metrykami tej bazy. Wynik 17 i gotowe modele 19 pozostają opisanymi
historycznymi odniesieniami, bez iloczynu ich konfiguracji.

| Cechy na tych samych miejscach 48 px | FH, k=4 | Jeden nowy podział MWS |
| --- | --- | --- |
| FFT, bez uczenia sieci | nowa wspólna baza A | wpływ zmiany relacji/podziału B |
| AE, rVAE albo SSL | wpływ uczenia C | połączenie zmian D |

Każdą rodzinę zestawia się osobno z tym samym A/B. Cechy do odległości
mają normalizację L2, PCA do min(24, liczba cech, liczba próbek train−1),
bez whitening; zerowy wektor jest niedostępny. PCA pasuje wyłącznie do
train. Nie porównujemy surowych norm wektorów różnego wymiaru: każda
reprezentacja ma własny train-fit PCA i skalę mediany krawędzi, opisane
poniżej. AE używa ciągłego kodu; SSL spłaszcza lokalną mapę w stałej
kolejności przestrzennej, aby nie usuwać korespondencji i fazy przez pooling.
Dla rVAE pełny opis podziału to konkatenacja kodu treści unormowanego L2
oraz `(cos(theta),sin(theta))`, każdy blok pomnożony przez 1/sqrt(2),
następnie wspólny adapter L2/PCA. Zero treści daje niedostępność.
To równe wagi bloków zadane przed próbą, nie kalibracja prawdopodobieństw
lub symetrii sieci. Porównanie samych cech treści jest diagnostyką typu, nie głównym
podziałem mającym zachować orientację. Nie deklarować typu strukturalnego
na podstawie klastra takiego pełnego opisu. W pierwszej próbie dopuszczalne
jest `type_id=null` dla wszystkich propozycji; walidacja katalogu nie jest
warunkiem powstania domeny bez znanego typu.

Graf ma krawędzie wyłącznie wewnątrz jednej klatki między sąsiadami siatki
o odległości <=16 sqrt(2) px. Centra w diagnostyce mają osobny graf z
promieniem min(24, 1.65 × mediana odległości najbliższych sąsiadów), bez
mieszania z siatką. Odległość d w PCA dzieli się przez medianę dodatnich
odległości krawędzi train, minimum 1e-10. Brak dodatnich odległości oznacza
degenerację cech, nie idealny obraz jednej domeny.

FH łączy krawędzie od najmniejszej d, gdy
`d <= min(Int(C1)+4/size(C1), Int(C2)+4/size(C2))`; bez dołączania małych
fragmentów do większych. MWS dostaje na **tym samym grafie** jeden znak
relacji: dla d<q25 przyciąganie o sile `(q25-d)/max(q25,1e-10)`, dla d>q75
odpychanie o sile `(d-q75)/max(q75,1e-10)`. Kwantyle liczy się raz z
nieoznaczonych krawędzi train, osobno dla reprezentacji; d w środku nie
tworzy relacji. Jeśli q25=q75, używa się tych samych ścisłych nierówności,
a identyczna odległość pozostaje bez relacji. Siły obcina się do [0,1].
Nie wybierać innych kwantyli po ocenie granic.

MWS przegląda relacje malejąco według siły, przy remisie najpierw
odpychanie, następnie kanoniczne `(min_id,max_id)`. Przyciąganie łączy
komponenty, jeśli brak między nimi zarejestrowanego konfliktu; odpychanie
rejestruje konflikt różnych komponentów. Scalanie przenosi wszystkie
konflikty. Relacja wewnątrz już scalonego komponentu nie cofa scalenia;
takie konflikty są liczone. ID komponentu to najmniejsze ID elementu.
FH remisy rozstrzyga tym samym porządkiem ID. W 21/22 trzeba sprawdzić
małe grafy, permutacje, remisy i znaną odpowiedź syntetyczną. Idealne
relacje służą wyłącznie testowi technicznemu, nigdy predykcji TTMAPP.

Nowe przyciąganie/odpychanie jest nieliniową interpretacją odległości,
nie kalibrowanym prawdopodobieństwem ani dowodem przesunięcia fazy.
W tym budżecie nie dodajemy dodatkowego wyuczonego klasyfikatora krawędzi,
prawdy syntetycznej do uczenia relacji ani dalekich krawędzi dla MWS.
FFT modułu widma może nie zachować fazy; MWS nie odtworzy brakującej
informacji. Badamy, czy reprezentacja uczona i ten zamknięty podział
pomogą na rzeczywistych sąsiadach. Nie przypisujemy poprawy B/D samemu
solverowi bez wskazania zmiany interpretacji odległości.

## Odmowy i kontrakt relacji oraz wyjść

Wszystkie pola 2 × 2 dostają tę samą ocenę porządku, niezależną od
reprezentacji. Adapter zachowuje mechanizm `windowed_acf` z 17/19:
dwa niekolinearne maksima w przesunięciach 6–24 px, sinus kąta >=0.35,
drugi kierunek widma >=25% dominującego oraz dodatnia lokalna energia.
Próg ACF to pojedynczy kwantyl 0.999 ze wszystkich dostępnych okien
znanych rozwojowych kontroli negatywnych, osobno dla skali. Nie kopiować
liczby 0.360777 z okna 49 px jako skalibrowanej dla nowego preprocessingu.
Nie zmieniać q ani mechanizmu po wynikach. Niepowodzenie ACF oznacza
`ambiguous/order_evidence_below_threshold`, nie automatyczne `disordered`.
Po odmowach ponownie policzyć spójne składowe; minimum 4 miejsca siatki
lub 8 centrów, bez wymuszonego scalenia małych składowych.

Zachowujemy [kopertę `stmdomains-result-v1`](experiment-input-protocol.md#kontrakt-wyniku-stmdomains-result-v1).
`assignments` zawiera końcowy wynik **po** odmowach, także wszystkie
nieprzypisane miejsca. W rozszerzeniu `extensions.training_v1` zapisujemy:

| Pole | Znaczenie i reguła |
| --- | --- |
| `protocol_id`, `plan_sha256`, `split_sha256` | niezmienna identyfikacja planu i rzeczywistego splitu |
| `regime`, `feature_id`, `partition_id`, `checkpoint_sha256` | transfer/transductive, cecha, reguła podziału i wagi; FFT ma checkpoint null |
| `elements` | komplet miejsc, `element_id`, `raw_edge_xy`, `support_xyxy`, `effective_support_xyxy`, `scale_px`, jednostka, sampler i dostępność |
| `proposals` | `element_id`, `component_id` przed odmowami; brak komponentu ma jawny powód |
| `evidence` | osobne dowody porządku, orientacji, wiarygodność, powody odmowy i informacja o materiale |
| `relations` lub `relations_artifact` | pełne rekordy par lub ścieżka/hash JSONL; nie odrzucać par bez danych |

Przykład rekordu pary jest ilustracją formatu, nie wynikiem pomiaru:

```json
{
  "edge_id": "g0012:g0013",
  "u": "g0012", "v": "g0013",
  "neighbor_rule": "grid8-stride16",
  "distance_px": 16.0, "support_intersection_area_px2": 2052.0,
  "support_iou": 0.5428571428571428,
  "appearance_distance": 0.7,
  "structure_spacing": {"value": null, "reason": "not_separated_from_orientation"},
  "orientation": {"value_deg": null, "reason": "no_validated_lattice_angle"},
  "translation_jump": {"value": null, "reason": "not_measured"},
  "availability": "available", "missing_reasons": [],
  "solver_relation": {"kind": "none", "strength": 0.0}
}
```

`structure_spacing`, orientację i nieciągłość/przesunięcie zachowujemy
oddzielnie; nie kopiujemy tej samej odległości do trzech rzekomo niezależnych
dowodów. Brak pomiaru pozostaje null z powodem. Prawda granicy w ocenie
ma osobny plik, nie dodatkowe pole wejściowe solvera. Dla okien różnych
skal trzeba policzyć rzeczywiste przecięcie wsparć, bez stałej z przykładu.
Przykład dotyczy maksymalnego efektywnego wsparcia 54 × 54 px wycinka
48 px: po 2 px przesunięcia i 1 px interpolacji z każdej strony.

Przykład dowodu i odmowy jednego miejsca:

```json
{
  "element_id": "g0012",
  "order": {"score": 0.31, "threshold": 0.4, "method": "windowed_acf"},
  "orientation": {"degrees": null, "equivalent_degrees": [], "reason": "unsupported"},
  "reliability": {"score": 0.31, "calibrated_probability": false},
  "material": {"state": "unknown", "score": null, "reason": "no_material_model"},
  "refusal_reasons": ["order_evidence_below_threshold"]
}
```

Propozycja komponentu pozostaje dostępna mimo tej odmowy; końcowy wiersz
ma `state=ambiguous`, `domain_id=null`, `type_id=null`. Przejście reguł
porządku i spójności bez rozpoznanego typu daje `ordered_untyped` z domeną.
ID domeny obowiązuje tylko w klatce. Typ i orientacja nie łączą odległych
obszarów w jedną domenę. Materiał pozostaje `unknown`, dopóki osobna metoda
nie uzasadni rozpoznania; nieporządek nie oznacza podłoża. Raster propozycji
z siatki jest wizualizacją, a otoczka centrów nie jest konturem/powierzchnią.

## Ocena i liczbowe warunki kontynuacji

Wszystkie wcześniej oglądane kontrole, także dawne ziarna 2701–2703,
są rozwojowe. Nowy pakiet z
[generatora kontroli](../../stmdomains/experiments/training/controls.py)
ma **27 przypadków × 3 ziarna 920001–920003 = 81 realizacji**:
22 bazowe z 14 oraz niezależne rzędy, pustą przerwę, sam brak oznaczeń
w pasie, niedostateczne pole i orientację 8°. Generator i kontrola geometrii
nie są oceną kandydata. Prawda tego pakietu pozostaje odłożona do zapisu
wszystkich predykcji i zamrożonego planu. Nie służy do treningu, walidacji
checkpointów, PCA ani kalibracji progów. Jednostki obrazu syntetycznego nie
są jednostkami raw STM: stosujemy z góry ustaloną konwencję
`synthetic_raw = low + (high-low) * (0.5 + 0.4 * renderer_image)`,
gdzie low/high to zamrożona normalizacja danego protokołu. Zwykła
normalizacja i clipping dają wejście `clip(0.5+0.4*renderer_image,0,1)`.
Nie dopasowujemy żadnej statystyki na syntetykach, starych ani odłożonych.
Nominalna amplituda +1 odpowiada 0.9, odwrócona −1 odpowiada 0.1,
a sigma szumu 0.025 odpowiada 0.01. To konwencja kontrastu modelowego,
nie fizyczna kalibracja STM. Zachowuje kontrast/odwrócenie i pary kontroli;
oryginalne tablice generatora pozostają niezmienione. Hash reguły jest
częścią planu i manifestu inferencji. `insufficient_field` nie jest
ujemnym przykładem zerowej liczby domen.

Każdą miarę podajemy osobno przed odmowami i po nich, dla każdej rodziny,
konfiguracji, ziarna i protokołu. Mianowniki: wszystkie zaplanowane miejsca,
miejsca z pełnym pomiarem, miejsca z ocenialną prawdą oraz pary z dwiema
przypisanymi końcówkami. `coverage` poniżej oznacza udział przypisanych
w **ocenialnych miejscach z pełnym wsparciem**, a dodatkowo raportujemy
udział względem całej siatki. To udział elementów, nie powierzchnia materiału.
Błędy par mają definicje `pair_scores`; brak mianownika daje null i nie
zalicza wymogu. Liczyć oddzielnie wszystkie ocenialne pary oraz rzeczywiste
lokalne krawędzie, także gdy okna przecinają granicę.

Warunki są kryteriami **kontynuacji badań**, nie progami odbioru 13:

| Kontrola | Warunek po odmowach dla każdego z 3 ziaren treningu i 3 ziaren kontroli |
| --- | --- |
| zerowe domeny: szum, pasy, losowe punkty, niezależne rzędy | 0 końcowych domen i 0 przypisanych elementów |
| jedna pełna sieć | dokładnie 1 domena, coverage >=0.90, split_rate <=0.02 |
| brak 10/30/50% centrów lub same braki w pasie, bez zmiany obrazu | wynik siatki identyczny z odpowiadającym obrazem pełnym, także przed odmowami |
| dwie orientacje/rozstawy, przesunięcie, dwa rozłączne płaty, pusta przerwa | coverage >=0.50, merge_rate <=0.02, split_rate <=0.10; obie prawdziwe części mają >=0.30 przypisań |
| niedostateczne pole | 0 rozpoznanych domen, wszystkie nieobsługiwane miejsca `insufficient_data`; brak miary błędu domen |

Dla technicznego resamplingu ×2 używa się jednostek `reference_px`.
Szczegółowe kontrole defektu, deformacji, kontrastu i ucięcia raportujemy
oddzielnie; nie znikają w średniej. Nie wymuszamy zgodności numerów etykiet.
Stabilność między trzema ziarnami: maksymalnie 10 punktów procentowych
różnicy coverage oraz <=0.10 zmienionych relacji par na wspólnie przypisanych
elementach, z jawnym udziałem tego przecięcia. Wymagania coverage wyżej
zapobiegają zaliczaniu stabilności przez wspólną pustą odpowiedź.

Syntetyczna miara granicy dotyczy wyłącznie stykających się dodatnich domen
(orientacje, różne rozstawy, faza i 8°). Używa osiowych krawędzi siatki, bez diagonali:
midpoint krawędzi przecinającej różne przypisane komponenty jest punktem
granicy propozycji. Prawdziwą granicę między dwiema dodatnimi etykietami rasteryzujemy w
jednostkach odniesienia i próbkujemy co 1 px; pomijamy brzeg pola
i przejścia do obszarów bez domeny. Precision to udział
przewidzianych midpointów <=**8 reference_px** od prawdziwej granicy,
recall to udział punktów prawdy w tej odległości od przewidzianego midpointu.
F1 jest średnią harmoniczną; gdy prawda istnieje, a predykcja jest pusta,
recall/F1=0, precision=null. Bez prawdziwej granicy podać fałszywe krawędzie,
bez wymyślonego idealnego F1. Tolerancja 8 px jest połową kroku siatki,
nie dokładnością konturu; konwencja wyłączenia pasa 3 px w etykietach
wnętrz nie zastępuje tej metryki. F1>=0.70 na tych przypadkach stykających się domen
jest dodatkowym warunkiem kontynuacji. Dla pustej przerwy i rozłącznych
płatów wymagamy osobnych domen oraz warunków coverage/scaleń z tabeli;
podajemy dodatkowo odsetek błędnych przypisań w znanym pustym pasie
(z jawną liczbą miejsc). Odmowa na przerwie jest poprawnym zachowaniem.
Nie wymagamy krawędzi między dwoma przypisanymi końcami ponad przerwą
ani konturu materiału; F1 jest tam niedostępne. Nie liczyć tej miary na przybliżonych
ramkach TTMAPP.

Na TTMAPP podajemy wszystkie pełne nakładki oraz ocenę wyłącznie w
częściowych referencjach 18 klatek. **Transfer** ocenia tylko miejsca
`transfer_split=test` z pełnym wsparciem w buforowanym lewym pasie expanded
[0,160]; validation/train i pozostałe części pełnych nakładek nie są wynikiem
heldout. **Transdukcja** ocenia całe dostępne wnętrza referencji i zachowuje
osobną tabelę oraz mianowniki. Mierzymy miejsca siatki, a pomocniczo centra odwzorowane
na najbliższą siatkę do 16 sqrt(2)/2 px. Niezmapowane centra pozostają
nieprzypisane. `BLACK/RED/YELLOW` nie określają klas typu ani kątów.
Nieoznaczone miejsca nie są błędami lub podłożem. Do ogłoszenia korzyści
na TTMAPP wymagamy coverage>=0.20 ogółem i >=0.10 w każdym z trzech
oznaczonych kolorami zbiorów, z zachowaniem osobnych regionów przestrzennych.
Gdy kolor lub rodzaj par nie ma ocenialnych miejsc w przestrzennym teście,
wynik jest niedostępny: nie wpisujemy zera ani automatycznego zaliczenia
kryterium. Wniosek transferu ograniczamy do reprezentowanych regionów;
pełnej korzyści na TTMAPP wtedy nie potwierdzamy. Wymaganie trzech kolorów dotyczy pełnej oceny transdukcyjnej; transfer
raportuje warunki na dostępnych regionach bez deklaracji generalizacji STM.
To próg użyteczności dalszego badania, nie oszacowanie globalnej trafności.

Porównanie błędów przy podobnej liczbie przypisań nie zmienia predykcji:
na stałych poziomach coverage 0.2/0.4/0.6/0.8/1.0 bierzemy najwyżej ocenione
elementy według wspólnego ACF, remisy według ID. Liczymy krzywe tylko do
coverage rzeczywiście osiąganego przez oba wyniki; nie dodajemy odrzuconych
elementów do końcowych domen. Dodatkowo oceniamy dokładnie wspólny zbiór
przypisanych ID, podając jego rozmiar. Gdy wspólna ocenialna coverage<0.20
lub brak obu rodzajów par, porównanie błędów jest niedostępne.

Po spełnieniu powyższych kontroli główny kandydat musi względem A osiągnąć
co najmniej jedną z dwóch korzyści, w medianie trzech ziaren i bez
przeciwnego znaku zmiany w pozostałych ziarnach:

1. Zmniejszenie średniej `(merge_rate+split_rate)/2` o >=0.05 przy wspólnej
   coverage>=0.20; żaden składnik nie rośnie o więcej niż 0.02.
2. Wzrost coverage o >=0.10 przy niepogorszeniu każdego z błędów o więcej
   niż 0.02 i przy spełnionych limitach scaleń/podziałów.

Przewaga musi wystąpić na odłożonych kontrolach i w ocenialnym zakresie
TTMAPP, jeżeli wniosek ma dotyczyć STM. Zysk wyłącznie syntetyczny lub
wyłącznie przed odmowami opisuje konkretny składnik i lukę; nie jest poprawą
końcowego detektora. Jeżeli bramka ACF nadal odrzuca prawie wszystko,
raport wskazuje tę przyczynę bez zamiany klastrów na domeny i bez dodawania
nowej bramki w tym budżecie. Po 21/22 decyzja 23 może zakończyć kierunek
lub wybrać jedno uzasadnione rozszerzenie. Żaden wynik nie otwiera ponownie 19.

## Artefakty i kontrola odtwarzalności

Manifest runu zawiera hashe danych/splitu/próbek, plan i hash kodu, wersje,
model i warstwy, sampler, normalizację, skale, augmentacje, ziarna, optimizer,
schedule, batch efektywny, precyzję, limit kroków/czasu oraz przyczynę stopu.
Checkpoint zachowuje wagi, optimizer, schedule, RNG Python/NumPy/Torch/CPU/GPU,
stan samplera, bieżący krok i najlepszą stratę walidacji. Wznowienie techniczne
porównuje następny batch, stratę i wagi w zapisanej tolerancji; nie jest
testem jakości domen. Wagi i tablice pozostają lokalnie poza Git.

Przed ujawnieniem końcowej prawdy zapisać hashe modelu, progów, transformacji,
kompletnych predykcji i konfiguracji. Ocena czyta te zamrożone artefakty,
nie uruchamia doboru. Raport rozróżnia kontrolę programu, pomiar GPU,
syntetyczną ocenę metody, częściową ocenę TTMAPP i odbiór GUI. Do zamknięcia
20 wystarczają działające przygotowanie oraz próba techniczna; tabela
wyników 2 × 2 i ich omówienie pozostają w 21–23.
