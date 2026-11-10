# Otoczenie molekuł — pierwsza próba issue 15

2026-10-23. **Próba obliczeniowa wykonana, issue pozostaje `claimed`.**
Po przedstawieniu wyniku użytkownik wybrał „Najpierw omówmy lub rozwińmy tę
próbę”. Nie zamykamy pytania i nie przechodzimy automatycznie do issue 16.

Najważniejszy wynik: geometria centrów pozwala odróżnić proste regularne
sieci od losowych punktów, ale **ta konfiguracja nie daje ogólnego wykrywania
domen na TTMAPP**. Najwięcej przypisań ma SOAP/36: 521 z 1678 oznaczeń
w częściowych referencjach (31,0%), wszystkie w BLACK. RED i YELLOW
pozostają bez rozpoznanej domeny. Nie jest to dowód, że wszystkie metody
geometryczne muszą zawieść; zidentyfikowano konkretną lukę oceny porządku.

Podgląd pełnych klatek:
[/home/rlew/projekty/NEtCAT-domains/.scratch/local-neighborhood-domains/index.html](/home/rlew/projekty/NEtCAT-domains/.scratch/local-neighborhood-domains/index.html).
Najbardziej użyteczne zakładki: „Obrót i rozstaw”, „Braki centrów”,
„Pełne TTMAPP”; widoki „Surowe klastry”, „Domeny”, „Przypisania i odmowy”
oraz „Wynik powtarzalności”. Referencję włącza się osobno.

## Zakres, pochodzenie i rozdzielenie oceny

Wejście z [issue 14](unsupervised-input-preparation.md): 24 pełne klatki
TTMAPP, 6730 oznaczeń, oraz 132 kontrole/27 390 centrów. Razem 34 120
obserwacji i 624 pliki wynikowe dla czterech wariantów. Klatka 255 została
przeanalizowana mimo braku ręcznej referencji. Pole raw, bieżące bboxy,
bez paddingu, masek SAM i dawnych klas MolTrack; fizyczna kalibracja
pozostaje nieznana. Obrazy służą podglądowi, obliczenia używają centrów.

Ekstrakcja cech i predykcja przyjmują wyłącznie `analysis/`. Ocena czyta
osobny `evaluation/`, po zapisie konfiguracji i wyników. Wyjątkiem celowo
dozwolonym przez protokół jest kalibracja kryterium porządku na **dziewięciu
losowych kontrolach rozwojowych**, bez odczytu masek TTMAPP. Kontrole
rozwojowe i kontrolne mają wspólny katalog nieopisanych cech: to grupowanie
transdukcyjne, nie test klasyfikatora na niewidzianych obserwacjach.
Ziarna 2701–2703 nie służyły kalibracji progu. Idealne niezaszumione centra
części regularnych kontroli są identyczne między ziarnami; trzy powtórzenia
nie oznaczają trzech niezależnych struktur ani akwizycji.

Nie dobrano miejsc analizy, liczby klas, rozmiaru okien ani parametrów
do ramek BLACK/RED/YELLOW. Podczas sprawdzania obrotu znaleziono błąd
numeryczny ścisłego odcięcia punktów dokładnie na promieniu. Wprowadzono
tolerancję 1e-7 px i odtworzono wszystkie cechy/predykcje/oceny. Nie była
to optymalizacja do referencji; wcześniejszych wyników nie mieszamy
z końcowym wariantem opisanym tutaj. Referencje były już oglądane w
poprzednich zadaniach i nie są niezależnym zbiorem testowym.

## Dokładnie porównana metoda

| Etap | Ustawienie tej próby |
| --- | --- |
| Sąsiedztwo | Dwa osobne promienie 24 i 36 px; w syntetycznym powiększeniu ×2 uwzględniono `pixel_spacing=0.5` |
| Prosty opis | Wygładzony rozkład odległości, koszyki co 2 px, sigma 1 px; moduły harmonicznych kątowych 1–12; lokalna mediana odległości najbliższych sąsiadów /24 |
| SOAP | DScribe 2.1.2, `n_max=6`, `l_max=6`, sigma 1, bez periodycznych warunków; jedna umowna species, centra w płaszczyźnie z=0; normalizacja długości wektora i osobno zachowany rozstaw /24 |
| Katalog | PCA do 24 składowych, bez whitening i bez skalowania kolumn do jednostkowej wariancji; HDBSCAN `min_cluster_size=20`, `min_samples=10`, `allow_single_cluster=True`, EOM, epsilon 0.15 |
| Populacje | Jeden katalog dla wszystkich 132 kontroli; osobny dla wszystkich 24 klatek TTMAPP. Bez zadania K |
| Powtarzalność | Przesunięcia do 1.8 lokalnego rozstawu; odsetek trafień w centra w tolerancji 0.12 rozstawu, co najmniej 8 prób; wymagane dwa niezależne kierunki (sin kąta ≥0.3) |
| Próg porządku | Ścisłe `score > max(0.6, kwantyl 99.5% kontroli rozwojowych)` oraz ≥8 sąsiadów; dla obu promieni otrzymano 0.6 |
| Orientacja | Pierwsza lokalna powłoka do 1.35 rozstawu; dominująca harmoniczna 2–12, preferowana niższa spośród ≥95% maksimum; moduł ≥0.5 |
| Domeny punktowe | Zgodny typ/harmoniczna, różnica kierunku ≤12° modulo symetria, odległość ≤1.65 mniejszego rozstawu; spójna składowa z ≥8 centrami |

Nie narzucono liczby sąsiadów odpowiadającej M6 ani innej klasie sieci.
Są jednak istotne założenia: lokalna dwukierunkowa periodyczność,
skończona rodzina harmonicznych i stałe progi wsparcia. Estymator kąta
jest uproszczeniem, nie rozwiązaniem dowolnej symetrii. SOAP w tym użyciu
opisuje punkty w px, nie atomy o znanej chemii ani odległości w Å.
API sprawdzono w [DScribe](https://singroup.github.io/dscribe/latest/tutorials/descriptors/soap.html)
i [scikit-learn 1.6](https://scikit-learn.org/1.6/modules/generated/sklearn.cluster.HDBSCAN.html).

Cztery warianty mają wspólną regułę oceny porządku i łączenia punktów.
Nie wykonano pełnego strojenia parametrów każdej rodziny. Epsilon 0.15
działa w różnych metrykach opisów, więc porównanie dotyczy konkretnych
konfiguracji; wynik nie dyskwalifikuje SOAP jako rodziny. Prosty opis
nie rozdziela poprawnie całego zestawu struktur, dlatego pokazano także
SOAP zgodnie z warunkiem ticketu. Nie dostarczono gotowego algorytmu.

HDBSCAN „noise” oznacza brak stabilnej grupy cech, nie fizyczny nieporządek.
Surowe klastry, wynik kryterium porządku, stan i domena są zapisane osobno.
Niepotwierdzona powtarzalność daje niejednoznaczność, małe wsparcie — brak
danych. Zero centrów na szumie/pasach to brak danych dla tej metody,
nie dowód analizy tekstury obrazu. Nie tworzono maski pokrycia materiałem.

## Kontrole: co działa, a co zawodzi

Poniżej nowe ziarna 2701–2703. „Przypisane” odnosi się do centrów w znanych
domenach poza pasami granic; nie do powierzchni obrazu. Liczba domen jest
podana dla trzech prób. Pełny zestaw obu podziałów i czterech wariantów
jest w `evaluation/summary.json`, `evaluation/per-sample.json` i
`per-sample.csv` obok podglądu.

| Kontrola | Prosty opis/36: domeny; przypisane | SOAP/36: domeny; przypisane |
| --- | --- | --- |
| Jedna sieć | 1/1/1; 98.4% | 1/1/1; 98.4% |
| Dwie orientacje tego samego typu | 2/2/2; 84.2% | 2/2/2; 88.7% |
| Różne rozstawy 12/16 | 4/4/4; 84.0% | 2/2/2; 93.6%, lecz **jeden typ** |
| Jedna sieć o większym rozstawie | 5/5/5; 88.9% | 1/1/1; 91.7% |
| Sieć skośna | 5/5/5; 93.4% | 1/1/1; 98.0% |
| Dwa rozłączne płaty | 2/2/2; 96.2% | 2/2/2; 96.2% |
| Pas nieuporządkowany | 2/2/2; 77.6% | 2/2/2; 84.9% |
| Granica przesunięcia | 3/3/3; 97.5% | 3/3/3; 97.9% |
| Jeden defekt | 1/1/1; 98.4% | 1/1/1; 98.4% |
| Brak 10% centrów | 1/1/1; 86.2% | 1/1/1; 87.7% |
| Brak 30% centrów | 1/2/3; 36.7% | 2/2/3; 46.4% |
| Brak 50% centrów | 0/0/0; 0% | 1/0/0; 2.6% |
| Lokalna luka oznaczeń | 1/1/1; 98.3% | 1/1/1; 98.3% |
| Zmienny/odwrócony kontrast i powiększenie ×2 | 1/1/1; 98.4% | 1/1/1; 98.4% |
| Przycięcie pola | 1/1/1; 97.6% | 1/1/1; 97.6% |

Na losowych punktach, z minimalnym odstępem i gradientem gęstości:
**0/2304 fałszywych akceptacji porządku**, zero domen w każdym wariancie.
Nie jest to „sukces przez odrzucenie wszystkiego”: pojedyncza regularna
sieć przechodzi. Warunek zatrzymania za brak rozróżnienia zero/jedna
nie został spełniony, ale pozostałe kryteria ujawniły istotne błędy.

Małe otoczenie 24 px zachowuje jedną domenę przy 56.3% przypisań, ale
odrzuca całą regularną sieć o rozstawie 16. Przy granicy przesunięcia
ma poprawne dwie składowe, lecz tylko 50% przypisań. Przy 36 px powstają
trzy składowe zamiast dwóch, z około 11.3% nadmiernie rozdzielonych par.
Sama obecność podziału nie potwierdza poprawnej granicy fazowej.

We wspólnym katalogu kontrolnym prosty opis/36 ma 18 surowych grup;
SOAP/36 ma jedną. Dla znanych typów we wszystkich klatkach kontrolnych
prosty opis/36: 87.5% przypisań, 1.38% podzielonych par wspólnego typu,
0% scaleń różnych typów. SOAP/36: 89.8% przypisań, **100% scaleń par
różnych typów**. Dwie przestrzenne składowe SOAP przy różnych rozstawach
nie naprawiają błędnego wspólnego typu. Metryki par są warunkowe względem
przypisania obu elementów; przypadek bez par ma null, nie zero błędu.

## TTMAPP i zlokalizowana przyczyna odmów

18 częściowych referencji obejmuje 1678 centrów: BLACK 1303, RED 101,
YELLOW 274. Nieoznaczone otoczenie nie jest tłem ani negatywnym przykładem.

| Wariant | Centra z rozpoznaną domeną we wnętrzach | Podziały par w jednym regionie |
| --- | --- | --- |
| Prosty/24 | 66/1678 = 3.9% | 0%, przy bardzo małym przypisaniu |
| Prosty/36 | 71/1678 = 4.2% | 0%, przy bardzo małym przypisaniu |
| SOAP/24 | 89/1678 = 5.3% | 0%, przy bardzo małym przypisaniu |
| SOAP/36 | 521/1678 = 31.0% | 8.0% |

Wszystkie rozpoznania dotyczą BLACK; dla SOAP/36 to 521/1303 = 40.0%
tej grupy. Nie ma przypisanych par między różnymi referencyjnymi regionami
w tej samej klatce, więc **nie da się ocenić ich scalenia**. Nie raportujemy
„0% błędu rozdzielenia orientacji”. Kolory nie dają prawdy strukturalnych
typów ani dokładnych kątów; pola JSON `raw_type`/`gated_type` dla TTMAPP
opisują jedynie relację klastra do kolorów, nie trafność typów.

Po odpowiedzi użytkownika wykonano dodatkową diagnozę przy niezmienionych
predykcjach (`reference-gate-diagnostics.json`). Dla promienia 36 px:

| Referencja | ≥8 sąsiadów | Przechodzi powtarzalność >0.6 | Mediana wyniku powtarzalności |
| --- | --- | --- | --- |
| BLACK | 1302/1303 | 571/1303 | 0.571 |
| RED | 101/101 | 0/101 | 0.250 |
| YELLOW | 267/274 | 0/274 | 0.200 |

**Główną przyczyną zaniku RED/YELLOW jest kryterium powtarzalności, a nie
samo grupowanie SOAP ani brak minimalnej liczby sąsiadów.** Maksimum
wyniku to 0.5 w RED i 0.455 w YELLOW. Nie dowodzi to fizycznego nieporządku.
Próg 0.6 jest konserwatywnym założeniem; kwantyl rozwojowych kontroli
losowych wynosił przy 36 px około 0.154, maksimum 0.2. Narzucone minimum
0.6 dominuje więc nad empiryczną kalibracją. Dopiero kolejna próba może
ocenić, czy niższy próg lub inna tolerancja poprawi wykrywanie bez fałszywego
porządku i łączenia domen. Nie obniżono go po obejrzeniu ramek.

Hipotezy do sprawdzenia: niedokładne centra, lokalne odkształcenia,
nieodpowiednie długości wektorów lub okna obejmujące różne orientacje.
Obecna diagnoza nie rozstrzyga, która z nich odpowiada za niższą
powtarzalność. Nie mierzono całkowitej liczby domen TTMAPP, IoU granic
ani powierzchni materiału. Małe błędy na przypisanych elementach nie
zastępują wyniku dla pozostałych fragmentów.

## Stabilność i odtwarzalność

- Obrót identycznej, nieprzyciętej chmury o 37°: maksymalna zmiana
  prostego opisu <1.6e-14, SOAP <6.3e-15; wynik powtarzalności identyczny.
  To kontrola inwariancji, nie dowód skuteczności na zniekształconych STM.
- Kontrast, odwrócenie kontrastu i techniczne ×2: identyczne przypisania
  i stany na wspólnych ID we wszystkich wariantach. Braki i przycięcie
  porównano na zachowanych ID, zapisując także brakujące obiekty.
- Rozszerzenie katalogu z klatek 1/50/100/150/200 do 24: wspólnych 980
  centrów. Surowe przypisanie zmienia się dla 5/0/4/9 centrów w kolejności
  prosty24/prosty36/SOAP24/SOAP36. Przy prostym opisie początkowy katalog
  odrzuca wszystkie centra; przy SOAP ma jeden typ. Domeny na tych pięciu
  klatkach nie zmieniają się, ale taka stabilność pustego lub scalonego
  wyniku nie dowodzi poprawności.
- Rzadki układ: jedna pełna skośna sieć obok 20 kopii pola kwadratowego,
  udział 4.76% obserwacji dopasowania. Prosty/36 dzieli dwa znane typy
  na 9 grup (przy równowadze: 6). SOAP/36 w obu proporcjach daje 2 grupy,
  ale scala 23.4% par różnych typów i dzieli 18.0% par jednego typu.
  To sztuczna nierównowaga częstości, nie mała wyspa i nie niezależne dane.
- Powtórna ekstrakcja i predykcja z kopii wejścia **bez katalogu oceny**:
  wszystkie 624 pliki wynikowe identyczne bajtowo.
- Losowa kolejność klatek i wierszy oznaczeń, ponowne hashe i ekstrakcja:
  wszystkie 624 zestawy przypisań identyczne. Wynika to m.in. z jawnego
  sortowania po ID; nie jest obietnicą naturalnej niezależności HDBSCAN
  od kolejności. Całe pliki zmieniają hashe, bo zmieniła się identyfikacja
  wejścia i katalogu; przypisania pozostają takie same.
- Każdy wynik przeszedł walidację kontraktu. Podgląd otwarto w QtWebEngine
  offscreen: 6 scenariuszy, 8 trybów i przełączenie referencji — 15 kontroli
  DOM/renderowania, bez błędów JavaScript. Obejrzano zrzut pełnej klatki.
  To nie jest odbiór natywnej aplikacji ani pełny test każdej kombinacji UI.

## Koszt i artefakty

CPU, jeden wątek BLAS/OpenMP, bez GPU/treningu. Końcowa ekstrakcja czterech
opisów: 12.24 s, szczyt RSS 243 408 KiB. Dopasowanie katalogów, domeny
i zapis 624 wyników: 42.31 s, RSS 330 636 KiB (około 323 MiB).
Ocena: 0.62 s; dodatkowe kontrole katalogu/obrotu: 1.75 s.
RSS mierzono przez Linux `getrusage.ru_maxrss`, osobno dla procesu;
VRAM jest nieużywany, nie podajemy go jako zmierzonego zera.

NumPy 2.2.5, SciPy 1.15.2, scikit-learn 1.6.1, DScribe 2.1.2,
ASE 3.25.0; dodatkowo sparse 0.19.2. DScribe/sparse zainstalowano
wyłącznie w `/tmp/stmdomains-issue15-deps`, bez zmiany `netcat` ani
głównych requirements. Nie wykonano pomiaru 268 klatek: warianty nadal
nie spełniają wymagania katalogu typów i zakresu rozpoznań. Sprawdzono
rozszerzenie 5 → 24; pełny koszt nie zastępuje naprawy tych błędów.

Źródło na odrębnej gałęzi **`prototype/stmdomains-neighborhoods`**,
commit **`1f25b45`**, baza `76dd4a3`; nie scalać prototypu do aplikacji.
README i skrypt `stmdomains/prototypes/run_neighborhood_trial.sh` podają
jedno polecenie odtworzenia. Worktree źródła:
`/tmp/netcat-stmdomains-neighborhoods-prototype`.

Pakiet lokalny `.scratch/local-neighborhood-domains/` (~143 MB) zawiera
HTML, cechy, konfigurację, wersje/hash kodu i wejścia, pełne przypisania
i odmowy w JSON, tabele JSON/CSV, kontrole stabilności, osobną diagnozę
referencji oraz dowody obu powtórzeń. Hashe każdego wyniku są w
`predictions/manifest.json`; brak dużych danych i obrazów w Git.
SHA-256 głównego skryptu użytego w końcowych obliczeniach:
`013326d6108a3b5d75ffefb356ae9acca6f9a028d593338526bd5ffa054b6779`.

## Dalszy zakres do omówienia

Użytkownik nie przyjął jeszcze zamknięcia próby i przejścia do 16.
Proponowany następny eksperyment **w ramach 15**: oddzielnie zbadać
kryterium powtarzalności i tolerancję położenia, zanim ponownie ocenimy
SOAP/HDBSCAN. Dodać kontrolowane zaburzenia położeń i odkształcenia sieci,
porównać tolerancje oraz kalibrację na losowych kontrolach bez stałego
minimum 0.6, a następnie sprawdzić podziały/scalenia, braki centrów
i częściowe referencje. Parametry zamrozić przed tą oceną. Ponieważ
problem wskazała obecna referencja, wynik będzie rozwojowy, nie nowy
niezależny test. Nie wymuszać przejścia konkretnych kolorów ani trzech klas.

**Aktualizacja 2026-10-23:** na polecenie użytkownika wykonano tę próbę;
[osobny raport kryterium powtarzalności](recurrence-criterion-trial.md)
zawiera 38 wariantów, nowe kontrole błędów centrów i wynik przy zamrożonym
katalogu. Warunek przechodzi 90.9% zamiast 34.0% oznaczeń we wnętrzach
referencji; domenę otrzymuje 62.5% zamiast 31.0%, lecz nadal występują
scalenia oraz brak dużych zgodnych składowych RED/YELLOW. Są to wyniki
rozwojowe, nie dokładność wykrywania. Następnie na polecenie użytkownika
wykonano [badanie orientacji i łączenia sąsiadów](orientation-and-joining-trial.md).
Komórka sieci poprawia część wyników, lecz zachowuje istotne ograniczenia;
raport proponuje porównanie 16 po omówieniu tej próby.

Katalog rozstawów i granice pozostają osobnymi lukami. Issue 15 nadal
`claimed`; nie wybrano metody do programu, nie uruchomiono issue 16 ani
treningu. Odbiór 13 i protokół jakości 04 nadal otwarte.
