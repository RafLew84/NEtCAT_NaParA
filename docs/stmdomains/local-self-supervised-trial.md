# Lokalny SSL i relacje domen — próba 22

Data: 2026-10-31. Realizacja [ticketu 22](issues/22-local-self-supervised-domains.md)
według [zamrożonego protokołu 20](self-supervised-training-protocol.md).
Źródło prototypu: `stmdomains/experiments/training/local_ssl/`;
[odtworzenie](../../stmdomains/experiments/training/local_ssl/README.md).
Artefakty lokalne: `.scratch/local-ssl-22/`; galeria `index.html`.
[Manifest dowodów](local-self-supervised-manifest.json) wiąże konfiguracje,
wagi, wyniki, diagnostykę i odbiór galerii. Źródło zachowuje gałąź
`prototype/stmdomains-local-self-supervised`.

## Wynik

**Lokalny SSL nie poprawił końcowego wykrywania domen w tym protokole.**
Model poprawnie się trenuje i nie zwraca stałych cech, lecz główny z32
w transferze daje **0/174** przypisań po odmowach dla obu podziałów
i wszystkich trzech ziaren. W transdukcji FH daje **4/782 (0,51%)**,
tyle samo co FFT, a MWS 0/782. Żadna z sześciu konfiguracji uczonych
(z16/z32 i oba reżimy z FH/MWS) nie spełnia kryteriów kontynuacji.
Próbę 22 zamykamy jako wykonany eksperyment, bez przyjęcia detektora.

Są dwa odrębne problemy. Zachowana bramka wraz ze spójnością nie pozwala
przekroczyć 0/174 w transferze niezależnie od cech. Jednocześnie SSL
nie rozdziela badanych granic również **przed** bramką: główny z32
scala częściowe referencje transferu, a F1 czterech kontroli granic
wynosi 0. Zerowego wyniku końcowego nie można przypisać wyłącznie
sieci, ale analiza przed odmowami także nie uzasadnia jej wdrożenia.

### Cztery pola porównania i encoder bez treningu

Tabela dotyczy głównej siatki 48 px. „Scalenia/podziały” to procent
błędnych par w obrębie klatek **przed** odmowami, przy 100% przypisań
ocenianych miejsc; dla sieci pokazano mediany trzech ziaren. Z32 ma
pierwszeństwo ustalone przed próbą, a z16 pozostaje diagnostyką.

| Cechy | Podział | Transfer: scalenia / podziały | Transdukcja: scalenia / podziały | Końcowe przypisania: transfer; transdukcja |
| --- | --- | --- | --- | --- |
| FFT | FH | 100,0% / 3,8% | 88,0% / 5,8% | 0/174; 4/782 |
| FFT | MWS | 0,0% / 77,5% | 1,1% / 52,1% | 0/174; 4/782 |
| Encoder z32 bez treningu | FH | 100,0% / 0,0% | 96,2% / 5,7% | 0/174; 4/782 |
| Encoder z32 bez treningu | MWS | 85,7% / 8,5% | 38,4% / 59,6% | 0/174; 0/782 |
| SSL z32 | FH | 100,0% / 0,0% | 95,4% / 7,2% | 0/174; 4/782 |
| SSL z32 | MWS | 100,0% / 0,0% | 16,5% / 80,0% | 0/174; 0/782 |

MWS otrzymuje także inną interpretację odległości jako przyciągania
i odpychania. Różnica względem FH nie izoluje samego solvera.
W transferze jest tylko 28 par różnych referencji i jedna taka krawędź
sąsiedztwa; to mały zakres oceny, nie globalna trafność TTMAPP.
SSL z32 scala tę krawędź we wszystkich ziarnach. W transdukcji SSL+MWS
scala 29,4% z 17 krawędzi między referencjami i dzieli medianowo 64,5%
z 2136 krawędzi wewnętrznych; FH scala wszystkie 17 krawędzi granicznych.

Porównanie uczenia z własną inicjalizacją na tych samych miejscach
przed bramką nie daje użytecznej przewagi. Dla transferu FH średnia
błędu scaleń i podziałów nie zmienia się; MWS pogarsza ją we wszystkich
ziarnach. W transdukcji FH poprawia ją w 1/3 ziaren, MWS w 2/3,
lecz mediana poprawy MWS to zaledwie 0,15 punktu procentowego i wynik
pozostaje słabszy od FFT. Po bramce wspólne pokrycie wynosi najwyżej
0,51%, poniżej wymaganego 20%; porównanie błędów przy użytecznym pokryciu
jest niedostępne, nie zaliczone.

### Granice i pozostałe kontrole

F1 poniżej łączy trzy realizacje syntetyczne dla każdego ziarna modelu,
następnie pokazuje medianę ziaren. Tolerancja granicy wynosi 8 reference px.
Tabela pokazuje **transfer przed odmowami**; w SSL wszystkie te F1 są także
zerowe po odmowach, dla obu reżimów i podziałów.

| Kontrola | FFT + FH | FFT + MWS | SSL z32 + FH | SSL z32 + MWS |
| --- | --- | --- | --- | --- |
| Dwie orientacje | 0,444 | 0,571 | 0 | 0 |
| Różnica orientacji 8° | 0,467 | 0 | 0 | 0 |
| Różny rozstaw | 0,571 | 0,706 | 0 | 0 |
| Granica przesunięcia wzoru | 0,571 | 0,571 | 0 | 0 |

Każda z tych czterech kontroli ma **0/9 zaliczonych ocen SSL z32**
osobno dla reżimu i podziału: trzy ziarna modelu × trzy realizacje,
nie dziewięć niezależnych realizacji danych. Encoder bez treningu
również ma F1=0 na tych granicach. Dodatnia wartość F1 FFT nie oznacza
zaliczenia wszystkich warunków detektora.

Pełna pojedyncza sieć, rozłączne płaty/pusta przerwa, pięć kontroli
brakujących centrów oraz niewystarczające pole uzyskują po 9/9 zaliczeń
SSL z32 w każdym reżimie/podziale. Pięć negatywnych kontroli (`noise`,
`random`, `random_gradient`, `random_minsep`, `stripes`) także uzyskuje
po 9/9. Natomiast **niezależne rzędy mają 0/9** i 75% błędnych przypisań.
Pozostałe przypadki diagnostyczne zachowują `null` kryterium, gdy nie
ustalono warunku zaliczenia; nie są automatycznym sukcesem.
Wszystkie **1530 sprawdzeń** niezmienności siatki po usunięciu centrów
przeszło, w tym 810 dla wyuczonych SSL.

### Co ogranicza zachowana bramka

Po zamrożeniu policzono dodatkową diagnozę geometryczną, bez nowych
predykcji, fitów lub zmian progów: spójne składowe miejsc przechodzących
już zapisaną bramkę, z minimum czterech miejsc, po pominięciu wszystkich
granic narzuconych przez cechy. Jest to górne ograniczenie przypisań
dowolnej reprezentacji przy tym samym grafie i filtrze.

| Reżim, siatka 48 px | Dostępne miejsca zakresu | Przechodzą samą bramkę | Maksimum po spójności, wszystkie miejsca | Maksimum w częściowych referencjach |
| --- | --- | --- | --- | --- |
| Transfer, osobny graf testowy | 912 | 6 | 0 | **0/174** |
| Transdukcja | 3456 | 50 | 18 | **4/782** |

W transferze cztery z sześciu miejsc przechodzących samą bramkę leżą
w referencjach, lecz nie tworzą wymaganej składowej. W transdukcji
takich miejsc w referencjach jest 26, a po spójności pozostają najwyżej
cztery. Wszystkie 816 rzeczywistych wyników głównego porównania mieszczą
się w tym ograniczeniu. Diagnozę zapisano jako `gate-upper-bound.json`;
nie jest nową metodą ani powrotem do strojenia bramki z 19.

### Ustalone diagnostyki skali i centrów

Transfer SSL z32 nadal ma 0 przypisań we wszystkich skalach: na siatce
mianowniki wynoszą 260/174/128 dla 32/48/64 px, na centrach 382/302/213.
Transdukcja na siatce 32 px ma 0/1002; przy 64 px FH osiąga 8/782
(1,02%) w każdym ziarnie, a MWS 0/782. To wcześniej ustalona diagnostyka,
bez wyboru nowej skali głównej. Osobny graf centrów daje 0 przypisań
we wszystkich skalach. Mapowanie siatki 48 px na centra daje dla FH
7/1354 (0,52%), dla MWS 0. Z16 nie zmienia końcowego transferu 0/174,
choć jego MWS przed bramką ma inny kompromis scaleń/podziałów.

### Cechy po uczeniu

Efektywny rząd deskryptorów transferowego SSL z32 na dostępnych oknach
TTMAPP wynosi 113,72–120,27, wobec 25,82–61,92 dla własnych inicjalizacji.
Maksymalna bezwzględna korelacja wymiaru z jasnością maleje z 0,734–0,751
do 0,364–0,404. Strata stałej walidacji maleje z 24,71–24,74 do
9,45–10,44. To mierzalna zmiana i brak degeneracji, lecz wzrost
zróżnicowania opisu nie zastępuje rozdzielenia rzeczywistych sąsiadów.
Diagnostyka obejmuje 17 reprezentacji i 204 oceny czystych wnętrz kontroli.
Nie wyprowadzamy z niej fizycznego kąta lub typu struktury.

## Zakres i zamrożenie

Sześć fitów transferowych: z16/z32 × ziarna 20261101/2/3; trzy refity
transdukcyjne z32. Przed pierwszym krokiem zapisano konfigurację,
architekturę i hashe źródeł. Plan 22 ma SHA-256
`c13408085dbb93471e49d605beb647da525ffb71eb73c8a236c7595d640c02ac`.
Próg ACF, parametry FH/MWS, normalizację i podział z 20 zachowano.
81 realizacji kontroli przygotowanych w 20 było już oglądanych w 21;
obecna ocena jest rozwojowa, bez strojenia pod te wyniki.

W transferze uczymy na 362 oknach, wybór checkpointu korzysta z 270
okien bez etykiet. Transdukcja używa 11 616 okien obecnej serii;
liczba kroków wynika wyłącznie z mediany trzech wybranych checkpointów
transferu z32. Ręczne referencje domen ani prawda syntetyczna nie trafiają
do treningu, normalizacji, PCA, relacji lub wyboru checkpointu.

Główne porównanie: siatka co 16 px i wycinek 48 px. Te same wagi
stosujemy także dla 32/64 px i centrów jako diagnostyki, bez wyboru
najlepszej skali. Każdy wycinek wymaga pełnego wsparcia pomiarowego.
Graf ocenianego transferu zawiera wyłącznie dozwolone węzły i krawędzie
testu; pełne nakładki klatek są oddzielnym podglądem.

Zachowane FFT × FH/MWS są dwoma polami macierzy 2 × 2, a SSL × FH/MWS
dwoma kolejnymi. Początkowe wagi z32 dla tych samych trzech ziaren
w obu reżimach sprawdzają wpływ uczenia bez dodatkowych fitów.
Każde porównanie korzysta z tych samych miejsc, wsparć i bramki.

## Model i zadanie lokalne

Trzy konwolucje 3×3, krok 2, kanały 16/32/64 i GELU, bez paddingu
i BatchNorm, dają mapę 7×7. Głowa 1×1 daje 16 lub 32 kanały.
Opis do grafu to cała mapa spłaszczona w kolejności kanał–Y–X,
odpowiednio 784 lub 1568 wymiarów. L2/PCA i normalizacja odległości
są dopasowane osobno do train danej reprezentacji.

Dwa widoki tego samego wycinka mają niezależne przesunięcia ±2 raw px,
gain 0,9–1,1, offset ±0,1 i szum Gaussa sigma 0–0,03. Nie dodajemy
pozytywnych par z sąsiedztwa ani losowych obrotów lub skalowania.
Znane przesunięcie odwracamy w mapie cech; 25 centralnych pozycji
ma komplet sąsiadów do interpolacji we wszystkich skalach. Gęsta
macierz wag liniowych umożliwia deterministyczny backward CUDA.
Interpolacja cech jest przybliżeniem ich zgodności po przesunięciu,
nie dokładną niezmienniczością konwolucji z krokiem 2.

Cel to 25 × MSE zgodności + 25 × kara niedostatecznej wariancji
+ kara kowariancji. Wariancję i kowariancję liczymy po batchu × 25
lokalnych pozycjach, oddzielnie dla kanałów; std docelowe 1,
epsilon 1e-4. Kowariancja ma mianownik N−1. Monitorujemy także std
całego opisu między wycinkami, aby stały wzór przestrzenny nie pozorował
braku degeneracji. Stały opis (próg 1e-6), niefinite, przekroczenie
czasu lub pamięci kończą próbę bez zastępowania ziaren.

SSL nie ma dekodera obrazu ani osobnej głowy kąta. Rozstaw, orientacja
i faza mogą wpływać na pełny opis, lecz odległość w nim nie staje się
skalibrowanym kątem, rozstawem ani pomiarem skoku translacji.
Osobna geometria ACF pochodzi z zachowanego mechanizmu oceny porządku.
`type_id=null` i materiał `unknown` pozostają dopuszczalne.

## Wykonanie treningu

Ukończono **9/9 fitów, 18 000 kroków** bez restartów, dodatkowych
konfiguracji lub instalacji. Sam trening wraz z walidacją i zapisem
checkpointów trwał **452,04 s**; najdłuższy fit 55,38 s przy limicie 900 s.
Szczyt pamięci tensorów GPU wyniósł 99 495 936 B, RSS 1 795 444 736 B.
189 checkpointów, w tym dziewięć początkowych, zajmuje 167 606 618 B.
Łącznie 21 i 22 wykorzystały 27/27 fitów, 921,13 s treningu
i 1 058 561 615 B checkpointów. Osobny dodatek 21a nie jest wliczony.

| Konfiguracja transferu | Wybrane kroki, trzy ziarna | Strata walidacyjna, trzy ziarna |
| --- | --- | --- |
| z16 — diagnostyka | 600 / 1000 / 1900 | 9,119 / 8,339 / 9,050 |
| z32 — główny model | 2000 / 2000 / 1900 | 10,064 / 10,441 / 9,448 |

Transdukcja z32 wykonała ustalone 2000 kroków dla każdego ziarna.
Średnie std lokalnych kanałów wybranych modeli transferowych z32
wynoszą 1,018 / 0,999 / 1,013; opisy nie są stałe. Różne wymiary
zmieniają także składnik kowariancji celu: tabela nie wybiera z16
na podstawie niższej wartości funkcji treningowej.

Audyt sprawdził wszystkie 189 checkpointów, zgodność początkowych wag
między reżimami, wspólny encoder między szerokościami oraz **6000 par
batchy** z16/z32: identyczne indeksy i wejścia dla tego samego ziarna.
Wszystkie 270 okien walidacji i ich transformacje są wspólne.
Wstępne sprawdzenie GPU potwierdziło bitową zgodność powtórzonego
forward/backward przy zerowej liczbie kroków optymalizatora.

## Sprawdzenia techniczne i artefakty

**181 testów przeszło** (`tests/stmdomains`, 11,58 s), w tym 20 nowych
sprawdzeń SSL: geometria korespondencji, statystyki celu, gradienty,
checkpoint, brak dostępu do referencji, train-only PCA, inicjalizacje,
kontrakt cech, budżet i diagnostyka. Sprawdzono składnię wrappera;
jego etapy wykonano osobno, bez powtarzania treningów.

Audyt przed rozpoczęciem potwierdził wszystkie **100 299 hashy**
zamrożonej próby 21. Nowa ekstrakcja obejmuje 68 540 dostępnych okien:
25 530 rzeczywistych i 43 010 syntetycznych. Powstało 21 420 predykcji
dla 17 przebiegów (9 SSL, 6 inicjalizacji, 2 FFT), dwóch podziałów,
trzech skal, siatki i centrów. Osobne wyniki grafu testowego transferu
są dodatkowymi artefaktami tych samych predykcji.

**2808 archiwów FFT** zachowuje liczbowo identyczne tablice z 21:
oba reżimy, wszystkie obrazy, skale i samplery, także grafy testowe.
Cache i adaptery FFT skopiowano po sprawdzeniu hashy; nie dopasowywano
ponownie bramki ani progów relacji. Nowe deskryptory mają jeden zapis
tablicy `features`, bez dublowania jej jako `content`; sprawdzenie
bitowej zgodności potwierdza niezmienność wartości.

Przed oceną zamrożono **84 595 lokalnych i 115 zewnętrznych artefaktów**,
w tym modele, wejścia, adaptery, predykcje i źródła. Manifest zamrożenia:
`b4c60fb8334328226fd725242edab422c696d58735108e97f68f28984e1c63a9`.
Finalizacja kontraktu sprawdziła 24 300 kopert, 4 895 892 rekordy miejsc
i 48 600 plików chronionych. Hash przypisań/relacji przed i po tej
operacji jest identyczny; zmiany dotyczą tylko jawnego opisu wsparcia,
jednostek i dostępności.

Galeria zawiera **105 obrazów, 17 wariantów i 3570 wyników** głównej
siatki, z przełączaniem reżimu, ziaren, FH/MWS, pełnego i osobnego grafu
testowego. Sześć scenariuszy pokazuje pojedynczą sieć, orientację, granicę
przesunięcia, braki centrów, paski i TTMAPP. Osadzone trzy ilustracje
pokazują korespondencję pozycji, przebieg celu i statystyki cech.
HTML ma 16 902 529 B; SHA-256:
`31fb78006bb5561856383a2daef761a310339b9f1f3eb8bea359eb5ae19edda7`.

QtWebEngine sprawdził **89 interakcji, zero błędów JS**. Obejrzano pięć
zrzutów i trzy ilustracje; brak problemów układu. Nie wykonywano odbioru
natywnego GUI aplikacji. Galeria jest prototypem badawczym.
Pomierzone etapy 22 zużyły **1031,08 s CPU**; razem z wcześniejszymi
etapami 21 **2088,67 / 7200 s CPU**. Dane, modele i wyniki zajmują
około 7,19 GiB, poza Git. Nie zmieniono wspólnych modułów ani artefaktów
21/21a; nie są potrzebne nowe instalacje.

## Ograniczenia wniosku

TTMAPP to jedna skorelowana akwizycja. Podział pasów i czasu ogranicza
przeciek geometryczny, lecz słaba wiarygodność rejestracji nie pozwala
utożsamiać go z testem na nowej akwizycji. Wyniki dotyczą oznaczonych
wnętrz, nie globalnej trafności obrazu lub dokładnych konturów domen.
Transfer zawiera 174 oceniane miejsca: BLACK 172, RED 2, YELLOW 0;
brakująca grupa ma wynik niedostępny. Transdukcję raportujemy osobno.

Niski cel SSL, wysoka wariancja lub rząd cech nie są samodzielnym
powodem przyjęcia detektora. Dalsze porównanie z 19/21/21a należy
do 23; jakość 04 i odbiór 13 pozostają osobnymi etapami.

Materiał dla 23 wskazuje dwie konkretne luki: brak użytecznych lokalnych
granic po stronie SSL/relacji oraz bardzo niski geometryczny limit
przypisań zachowanej bramki. Dalszy eksperyment wymaga własnej hipotezy
i budżetu; wykonanie 22 nie uruchamia strojenia 19, nowych fitów ani
warunkowych 24–26. Przygotowanie dodatkowych MPP/STP pozostaje odłożone
do decyzji na podstawie całego porównania.
