# Gotowe cechy sieci — próba issue 19

Data: 2026-10-26. [Issue 19](issues/19-frozen-feature-domains.md).
**Obliczenia i podgląd wykonane; zadanie pozostaje `claimed` do dalszego
omówienia/rozwinięcia.** Użytkownik wybrał: „Najpierw omówmy lub rozwińmy
tę próbę”. Nie przyjęto metody do programu i nie rozpoczęto treningu.

Zamrożone FCN–ResNet101 i DINOv2 w badanym przetwarzaniu nie poprawiły
wykrywania domen względem cech klasycznych. Wybrane na kontrolach warianty
przypisują 0–5.1% molekuł we wnętrzach TTMAPP i pomijają RED/YELLOW.
Nie jest to dowód, że reprezentacje tych modeli nie mogą zawierać potrzebnej
informacji. Wynik dotyczy **uśredniania lokalnych map, normalizacji, PCA,
HDBSCAN i dwóch konkretnych kryteriów porządku** opisanych poniżej.

Dwa problemy występują równocześnie: większość miejsc odpada przy ocenie
porządku, a wybrane grupowanie przed tą oceną zazwyczaj łączy TTMAPP w jedną
grupę wyglądu. Samo złagodzenie progu porządku nie odtworzy orientacyjnych
domen, jeśli ich różnicy nie zachowało wcześniejsze grupowanie.

Podgląd całych klatek i pięciu scenariuszy:
`/home/rlew/projekty/NEtCAT-domains/.scratch/frozen-feature-domains/index.html`.
Tam również `comparison.png`, PDF, CSV, cechy, katalogi i komplet przypisań.
Krzyżyki oznaczają siatkę próbkowania; okręgi rzeczywiste centra molekuł.
Osobne widoki pokazują podobieństwo, dowód porządku i fragmenty po połączeniu.
Referencje są domyślnie ukryte i nie były wejściem algorytmów.

Źródło prototypu: **`prototype/stmdomains-frozen-domains`, `652ab96`**,
baza `ad584eb`. Nie scalać prototypu do aplikacji. Dokumentacja:
`domains/frozen-domain-trial`, docelowo `domains/start`.
[Manifest przebiegu](frozen-feature-domains-manifest.json) i
[audyt grupowania](research-frozen-domain-clustering-audit.md).

## Zakres i rozdzielenie analizy od oceny

Wejście to ten sam zestaw co w 15–17: **24 pełne klatki TTMAPP, 6730
oznaczeń oraz 204 kontrole — 34 przypadki × 6 ziaren**. Klatki: 1, 50,
100, 150, 200 oraz 250–268. Obrazy raw z MPP, bez gamma i bez dopełnienia
rejestracji. Kalibracja fizyczna pozostaje niewiarygodna; używamy px.

Algorytmy otrzymują pełne obrazy i opcjonalnie centra. Nie otrzymują ramek,
liczby domen, kolorów, masek SAM ani historycznych domen MolTrack.
Klasyczne cechy FFT/EWT wykorzystano z audytowanego zapisu issue 17,
sprawdzając hashe. Nowe cechy sieci obliczono dla wszystkich 228 obrazów.

Do doboru służyło **102 syntetyczne kontrole rozwojowe**, ziarna 1701–1703.
Przed odczytem pozostałych etykiet zapisano wszystkie predykcje, konfigurację
oraz `selection-lock.json` z hashami kodu i ustawień. Wtedy w nowym katalogu
wejścia nie było drzewa referencji. Dopiero później odczytano 102 kontrole
z ziarnami 2701–2703 oraz 18 częściowych referencji TTMAPP.
Sprawdzenie końcowe potwierdziło niezmienność tej konfiguracji i źródeł.

Referencje TTMAPP były używane wcześniej. Obecny podział nie czyni ich
niezależnym testem. Ocena obejmuje wyłącznie wnętrza: **1678 centrów**,
BLACK 1303, RED 101, YELLOW 274. Nieoznaczone części nie są tłem ani błędem.

## Wspólny, z góry zapisany budżet

Protokół: `stmdomains/prototypes/frozen_domain_design.json` na gałęzi
prototypu; lokalna kopia to `protocol.json`.

**64 podstawowe konfiguracje:** cztery rodziny cech × dwa sposoby
próbkowania × dwa promienie × dwa epsilon × dwa kryteria porządku.
Każda rodzina/tryb ma dokładnie osiem prób do wyboru. Dla sieci podstawą
jest wejście 112×112 i normalizacja percentylami klatki.

Dodatkowe wejście 224×224 i normalizacja min–max dają **96 konfiguracji
wrażliwości**, łącznie 160. Nie zastępują podstawowego wyboru po obejrzeniu
referencji. Żaden ze wszystkich 160 wariantów nie spełnił kompletu
zapisanych warunków rozwojowych.

Kryteria doboru: minimum 90% przypisań jednej sieci, dokładnie jeden jej
obszar dla każdego ziarna, maksymalnie 2% podziałów par; zero fałszywych
próbek w sześciu rodzinach negatywnych; w sześciu przypadkach rozdzielenia
minimum 50% przypisań i maksimum 2% scaleń. Brak mianownika scaleń nie
zalicza rozdzielenia. Ranking: najmniej niespełnionych warunków, następnie
średnie `przypisanie × (1−podziały) × (1−scalenia)` na 24 dodatnich
przypadkach, na końcu ID konfiguracji. Każdy wynik z niespełnionymi
warunkami pozostaje diagnostyczny.

## Co jest wspólne, a co zmieniliśmy

Cechy sieci są dokładnie ekstraktorami [przygotowania 18](frozen-feature-preparation.md):
FCN `layer1/layer2`, średnie przestrzenne połączone w 768 wartości;
DINOv2 ViT-S/14, średnia końcowych patch tokens, 384 wartości.
Oficjalne wagi, brak aktualizacji parametrów, buforów i gradientów.
Promienie 24/36, okna sieci 48/72 px; klasyczne cechy i autokorelacja
korzystają z okien 49/73. Ta różnica jest jawna.

Wszystkie cztery rodziny mają wspólne przetwarzanie do grupowania:

1. Normalizacja L2 każdego wektora, zaokrąglenie do 8 miejsc.
2. PCA do maksymalnie 24 składowych, pełny SVD, bez whitening.
3. Podział wszystkich współrzędnych PCA przez medianę odległości do
   szóstego innego sąsiada; zerowe odległości pomijane przy ustalaniu skali.
4. HDBSCAN, `min_cluster_size=12`, `min_samples=6`, EOM,
   `allow_single_cluster=True`, epsilon **0.5 albo 1.5 tej skali**.

To własna heurystyka skalowania, a nie zalecany domyślny wariant biblioteki.
PCA i grupowanie wykorzystują wszystkie miejsca z minimum 50% wsparcia
pomiaru. Dla całego zakresu TTMAPP jest jeden wspólny fit i katalog wyglądu;
każda niezależna kontrola ma własny jednoklatkowy katalog. Większa liczba
centrów zwiększa wagę klatki; zachodzące okna nie są niezależnymi próbami.
Nie wymuszamy liczby grup ani nie przypisujemy nowych klatek do arbitralnych
przykładów. Etykiety kanonizujemy po reprezentantach cech.

**To nowe wspólne grupowanie także dla FFT/EWT.** Wyników nie należy
przedstawiać jako niezmienionej konfiguracji issue 17: tam epsilon wynosiło
0.1/0.25 bez obecnej normalizacji dystansu. Starszy wynik pozostaje
oddzielnym punktem odniesienia; tutaj wszystkie rodziny mają tę samą
procedurę i budżet. Zmiana pogorszyła część klasycznych kontroli jednej sieci.

Łączenie przestrzenne zachowuje regułę z 17: ten sam klaster, siatka do
12√2 px i minimum czterech okien; centra do `min(24, 1.65×mediana
najbliższej odległości)` i minimum ośmiu elementów. Siatkę przenosimy na
centra tylko do odległości 12√2/2 px. Nie budujemy z tych punktów maski
powierzchni materiału ani dokładnego konturu domeny.

## Dwa kryteria porządku

W obu przypadkach szukamy dwóch niekolinearnych maksimów ACF w zakresie
przesunięć 6–24 px, z sinusem kąta ≥0.35, oraz wymagamy drugiego kierunku
widma z mocą ≥25% dominującego i dodatniej energii lokalnej.

- **Dotychczasowa ACF:** wynik z oknem Hanna zapisany w 17.
- **ACF z korektą nakładania:** bez Hanna; korelacja Pearsona wyłącznie
  na nakładających się fragmentach przesuniętego okna. Dla każdego
  przesunięcia przeliczamy średnie i wariancje obu części. Zachowujemy
  to samo odjęcie rozmycia Gaussa σ=3 i regułę pary kierunków.

Próg to kwantyl 0.999 z rozwojowych negatywnych kontroli na siatce,
wyznaczony osobno dla wariantu i promienia:

| Promień | Dotychczasowa ACF | ACF z korektą nakładania |
| --- | ---: | ---: |
| 24 | 0.360777 | 0.512407 |
| 36 | 0.312840 | 0.370542 |

Nowy wynik FFT sprawdzono niezależnym, bezpośrednim obliczeniem korelacji
przesuniętych tablic dla obu promieni, szumu i obrazu okresowego;
maksymalna różnica 3.33e-16. To sprawdzenie implementacji, nie skuteczności
kryterium na STM. Zmiana usuwa część tłumienia wynikającego z okna, lecz
nie rozwiązuje sama wyboru właściwych przesunięć ani rozpoznania porządku.

Brak przejścia jest zapisywany jako niewystarczający dowód, nie pewne
nieuporządkowanie. HDBSCAN może również odmówić przy spełnionym kryterium.
Widok bez tego kryterium pokazuje grupy podobieństwa, nie domeny.

## TTMAPP: nie uzyskano poprawy

Wszystkie wyniki poniżej dotyczą podstawowych ustawień wybranych przed
oceną referencji. Procenty podziałów i scaleń dotyczą tylko przypisanych par.

| Cechy / próbkowanie | Przypisane centra / 1678 | Podziały | Scalenia |
| --- | ---: | ---: | --- |
| Widmo / siatka | 98 = 5.8% | 43.3% | Brak par |
| Widmo / centra | 34 = 2.0% | 0% | Brak par |
| EWT / siatka | 86 = 5.1% | 37.2% | Brak par |
| EWT / centra | 34 = 2.0% | 0% | Brak par |
| FCN / siatka | 86 = 5.1% | 37.2% | Brak par |
| FCN / centra | 34 = 2.0% | 0% | Brak par |
| DINOv2 / siatka | 86 = 5.1% | 37.2% | Brak par |
| DINOv2 / centra | 0 | Brak par | Brak par |

Każde przypisanie leży w BLACK. RED **0/101**, YELLOW **0/274** dla
wszystkich wybranych wariantów. Brak par między regionami nie oznacza
zerowego błędu scalenia. Nie można z tego wyprowadzić trafności całej klatki.

Rozdzielenie etapów na tych samych 1678 centrach:

| Cechy / próbkowanie | Ma grupę wyglądu | Przechodzi porządek | Spełnia oba | Końcowy fragment |
| --- | ---: | ---: | ---: | ---: |
| Widmo / siatka | 1678 | 154 | 154 | 98 |
| Widmo / centra | 1678 | 151 | 151 | 34 |
| EWT / siatka | 1666 | 118 | 118 | 86 |
| EWT / centra | 1664 | 151 | 148 | 34 |
| FCN / siatka | 1678 | 118 | 118 | 86 |
| FCN / centra | 1677 | 151 | 150 | 34 |
| DINOv2 / siatka | 1677 | 118 | 118 | 86 |
| DINOv2 / centra | 0 | 133 | 0 | 0 |

W całym zakresie 24 klatek siedem wybranych wariantów ma **jeden klaster
wyglądu**, a DINO/centra odrzuca wszystkie wektory. Końcowe rozłączne
fragmenty powstają głównie z przerw w akceptacji kryterium porządku i reguły
łączności. Nie jest to odzyskanie trzech orientacji ani katalogu typów sieci.

Przy zachowaniu tej samej konfiguracji FCN/DINO na siatce zamiana
kryterium daje 98 → 86 przypisanych centrów; FCN/centra 34 → 46.
Nie ma ogólnej poprawy. Przełączenie 112 → 224 i percentyli → min–max
przy pozostałych ustawieniach podstawowego wyboru daje te same końcowe
liczby na TTMAPP. **Nie dowodzi to identyczności cech:** ten wynik jest
zdominowany przez dalsze etapy. Pełne zestawienie jest w `diagnostics.json`.

## Kontrole: przypisanie nie oznacza poprawnej domeny

Dla każdego przypadku wykorzystano trzy odłożone ziarna. Poniżej wyniki
molekuł, z liczbą fragmentów dla kolejnych ziaren:

| Wariant | Jedna sieć: przypisanie; fragmenty | Scalenia przy różnicy 8° | Scalenia granicy przesunięcia |
| --- | --- | ---: | ---: |
| Widmo / siatka | 95.3%; 5/5/5 | 0% | 0% |
| Widmo / centra | 96.5%; 7/7/7 | 0% | 0% |
| EWT / siatka | 92.7%; 4/4/6 | 0% | 89.7% |
| EWT / centra | 84.9%; 5/1/4 | 0% | 0% |
| FCN / siatka | 98.8%; 2/2/2 | 100% | 65.1% |
| FCN / centra | 87.1%; 4/4/4 | 100% | 0% |
| DINO / siatka | 97.5%; 2/3/3 | 20.9% | 18.4% |
| DINO / centra | 86.3%; 5/2/2 | 3.8% | 3.1% |

Niski błąd scaleń może współistnieć z wieloma nadmiernymi podziałami;
pełne przypisania, podziały, odmowy i liczniki są w CSV i HTML. Np. FCN
na siatce przypisuje 93.1% centrów przy różnym rozstawie bez scaleń, ale
zwraca 4/3/2 fragmenty zamiast stabilnych dwóch. Większe przypisanie
samej sieci nie oznacza więc rozstrzygnięcia problemu.

Końcowe wyniki: **0/4608** fałszywych próbek w wariantach siatkowych na
sześciu rodzinach negatywnych, **0/3195** przy centrach. Szum i pasy nie
mają centrów, więc brak wyniku wariantu centrowego na nich nie jest
samodzielnym dowodem odporności na teksturę; służy temu kontrola siatki.
Przed oceną porządku siatki wszystkich rodzin tworzą połączone grupy
na 4396–4534 z 4608 negatywnych miejsc. Nie wolno nazywać ich domenami.

Typ strukturalny pozostaje **nieustalony**. Wynik zapisuje osobno grupę
wyglądu, fragment oraz kierunek krótszego z dwóch wektorów ACF modulo 180°.
Ten kierunek może odpowiadać innemu wyborowi bazy lub harmonicznej;
nie jest skalibrowanym pomiarem orientacji sieci. Nie udajemy rozpoznania
wspólnego typu przy obrocie. To dodatkowy brak względem celu programu.

## Powtarzalność i zależności

- **912 zestawów cech sieci siatki** obliczono od nowa po usunięciu centrów,
  bboxów i ID. Są bitowo identyczne. Cache był świeży, obrazy powtórzone
  w kontrolach mogły współdzielić wynik wewnątrz tego powtórzenia.
- **228 klasycznych zestawów siatki** jest identycznych bez centrów.
  FFT/EWT pochodzą z wcześniej zweryfikowanego niezależnego powtórzenia
  17; nową autokorelację przeliczono od nowa.
- Pełne grupowanie i łączenie powtórzono: **1824/1824** wyników ośmiu
  wybranych konfiguracji identyczne. Siatka ma pustą listę oznaczeń;
  centrowe wejście ma odwróconą kolejność klatek i oznaczeń, ponownie
  kanonizowaną przed analizą. W osobnych drzewach analizy brak referencji.
- **96/96** par kontroli braków 10/30/50% i lokalnej luki detekcji zachowuje
  identyczne wyniki siatki. To nie zmiany wyglądu obrazów.
- Kontrast: wynik zmienia się w **21/24** porównań, w tym wszystkich sześciu
  ziarnach EWT, FCN i DINO. Inwersja: zmiany w 4/24, tylko DINO.
  Techniczne ×2: zmiany w 13/24, w tym 5/6 DINO; FCN pozostaje zgodne.
  Zapisano zmiany przyjęcia i relacji par, bez deklaracji ogólnej odporności.
- Zakres 250–254 kontra pełne 24 klatki: ponowny fit PCA/HDBSCAN oraz
  odpowiedni bank EWT. Grupy wyglądu zmieniają członkostwo w **21/40**
  porównań. Końcowe fragmenty są identyczne w 40/40, lecz **puste** na tych
  pięciu klatkach. Zgodność odmowy nie dowodzi stabilnej detekcji.
- 1824 wyniki zwalidowano według wspólnego kontraktu. `type_id` pozostaje
  null; przyjęte kandydatury mają `ordered_untyped`. Zachowano powody
  odmowy, geometrię oraz osobne identyfikatory grup wyglądu.

## Koszt, artefakty i wykonane sprawdzenia

RTX 5090; lokalne netcat, Python 3.12.12, torch 2.9.1+cu128,
torchvision 0.24.1+cu128, sklearn 1.6.1. Bez dodatkowych instalacji.
Ekstrakcja GPU float32, cztery wątki CPU, partie 32; pozostałe obliczenia
z jednym wątkiem BLAS/OpenMP. Szczegółowe wersje i hashe w `provenance.json`.

| Etap | Czas | Szczyt pamięci |
| --- | ---: | --- |
| Cechy obu sieci, 7296 wpisów / 6240 unikalnych | 566.52 s | RSS do 1550692 KiB, ok. 1.48 GiB |
| Nowa ACF i audyt cech klasycznych | 319.95 s | RSS 76828 KiB |
| 160 konfiguracji grupowania i łączenia | 319.16 s | RSS 677004 KiB, ok. 661 MiB |
| Ocena pełnego zestawu | 11.73 s | Nie mierzono osobno |
| Świeże cechy sieci siatki bez oznaczeń | 35.62 s | W metadanych wpisów |
| Ponowna ACF siatki / audyt klasycznych | 178.56 s | RSS 75780 KiB |

Każdy model ma 3120 unikalnych wpisów i 773176 wektorów. Pliki cech FCN
zajmują 2168123034 B, DINO 1131855712 B. Szczyt alokowanych tensorów
CUDA: FCN 339811328 B (324 MiB), DINO 281049600 B (268 MiB); rezerwa
alokatora odpowiednio 574619648 i 364904448 B. To nie pełna pamięć procesu
GPU wraz ze sterownikiem. Czasy nie obejmują treningu i nie są benchmarkiem
268 klatek. Żaden kandydat nie zakwalifikował się do takiego rozszerzenia.

Weryfikacja przeglądarki: **46 kontroli QtWebEngine**, bez błędów JS i bez
poziomego przepełnienia. Obejrzano podgląd i wykres. Przeglądarka wymagała
uruchomienia poza sandboxem; dotyczyło to tylko lokalnego HTML. Sprawdzono
składnię Python/Bash, hashe i diff. Nie testowano natywnej aplikacji.

Kopia lokalna: **35319 plików / 6642599215 B**, wszystkie SHA-256 zgodne;
wewnętrzne symlinki są względne i pozostają poprawne po przeniesieniu.
Wagi pozostają w `.scratch/frozen-feature-assets/`, poza Git.

Jedno polecenie odtworzenia opisuje `README-frozen-domains.md` na gałęzi
prototypu. Runner: `stmdomains/prototypes/run_frozen_domain_trial.sh`,
argumenty: artefakt 17, katalog wag 18 i nowy katalog wyjścia.
Etapy wykonano osobno; wrapper złożono i sprawdzono składniowo, bez
powtarzania całości tylko dla sprawdzenia wrappera.

## Omówienie i możliwe rozwinięcie

Użytkownik wybrał **„Najpierw omówmy lub rozwińmy tę próbę”**. Issue 19
pozostaje `claimed`. Wynik i ustawienia są zachowane, lecz nie ma zgody
na zamknięcie porównania ani wyboru metody. Nie uruchomiono issue 20.

Najbardziej użyteczne następne badanie w obrębie 19 powinno ustalić,
**na którym etapie znika rozróżnienie orientacji/rozstawu**:

1. Na kontrolach porównać odległości cech przed i po PCA, jeszcze bez
   grupowania i kryterium porządku. Sprawdzić, czy różnica 8°/27° i rozstaw
   w ogóle przeważają nad zmiennością wnętrza jednej sieci.
2. Jeśli informacja jest obecna, zbadać ograniczony wariant grupowania
   bez scalającego epsilon oraz wpływ PCA. Obecna mediana dystansu i
   epsilon są naszym założeniem, a wynik jednej grupy nie rozstrzyga
   nieprzydatności samych sieci.
3. Jeśli informacja ginie już w opisie okna, porównać zachowanie przestrzennych
   map/tokenów z obecnym uśrednieniem. Nie zaczynać od obniżania progu,
   które może jedynie nadać etykietę domeny dużej grupie wyglądu.

Tę propozycję następnie **wykonano** w [osobnym badaniu](feature-separation-trial.md),
z nowym protokołem i budżetem ustalonym przed oceną. Dotychczasowe odłożone ziarna
oraz referencje były już oglądane; kolejnego dostrajania nie należy
opisywać jako niezależnej walidacji. Obecna próba nie rozstrzyga innych
poolingów, skal, metryk, grupowania ani cech trenowanych na STM.
