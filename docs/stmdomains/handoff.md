# STM Domains — diagnoza cech, PCA i grupowania, issue 19

Data: 2026-10-26. Dokumentacja `domains/feature-separation-trial`, baza
`1c2eef6`, worktree `/tmp/netcat-stmdomains-feature-separation`.
Źródła prototypu: **`prototype/stmdomains-feature-separation`, `cf88e8a`**,
baza `652ab96`. Nie scalać prototypu do aplikacji. Docelowo dokumentacja
na `domains/start`; commit dokumentacji w wiadomości końcowej.

Na polecenie „wykonaj kolejne badanie” ukończono diagnozę zaproponowaną
w pierwszej próbie 19. [Raport](feature-separation-trial.md),
[manifest](feature-separation-manifest.json), interaktywny podgląd:
`/home/rlew/projekty/NEtCAT-domains/.scratch/feature-separation/index.html`.

24 całe klatki TTMAPP i 204 kontrole, osiem kombinacji cecha/miejsca;
pełne cechy/PCA × dotychczasowe/zerowe epsilon daje 32 konfiguracje.
Protokół zapisany przed oceną, bez treningu, K i dopasowania do ramek.
Wszystkie ziarna były już znane: to diagnoza, nie niezależna walidacja.

Cechy obu modeli zachowują rozróżnienie orientacji 8°/27° i rozstawu
na kontrolach; największa zmiana AUC po PCA to 0.000486. Same zmiany
PCA/epsilon nie naprawiają domen: na TTMAPP 30 wariantów daje jeden
klaster wyglądu, dwa odmawiają. DINO/centra po epsilon=0 odzyskuje
46/1678 oznaczeń, nadal tylko BLACK. Żaden wariant nie spełnia kompletu
warunków. Nie wyznaczono typów, powierzchni ani dokładnych granic.

**19 nadal `claimed`**, do omówienia. Dalszy kierunek: lokalne granice
różnic cech i osobna ocena kryterium porządku. Nie rozpoczęto tego
następnego eksperymentu, treningu 20 ani odbioru 13. Nie ma potrzeby
uruchamiania warunkowej próby przestrzennego poolingu dla wyjaśnienia
utraty obrotu/rozstawu na tych kontrolach; nie oznacza to odrzucenia
innych poolingów dla rzeczywistych STM.

Sprawdzenia: **1824/1824** dokładne odtworzenia starego wariantu (pięć
tablic na wynik), AUC kontra bezpośrednie liczenie z remisami (5.56e-17),
odległości PCA nie większe od pełnych, niezmienione hashe predykcji
podczas oceny. **68 kontroli QtWebEngine**, bez błędów JS; obejrzano
podgląd oraz wykres. Składnia Python/Bash, linki i diff sprawdzone.
Nie powtarzano ekstrakcji, testów modeli ani natywnego GUI; korzystano
z cech i ich wcześniejszej weryfikacji.

Koszt CPU, jeden wątek: PCA 16.16 s, metryki 7.19 s, grupowanie 457.59 s;
szczyt RSS do 589056 KiB (ok. 575 MiB), bez GPU i instalacji pakietów.
Kopia: **2078 plików / 261856765 B**, wszystkie SHA-256 zgodne.
Względne symlinki wskazują zachowany artefakt pierwszej próby 19;
sam HTML jest samowystarczalny. Dane i modele pozostają poza Git.
Runner na gałęzi prototypu; etapy wykonano osobno, wrapper składniowo.

Do aplikacji trafia tylko dokumentacja i manifest. Bez zmian wspólnych
modułów, konfiguracji głównej, produkcyjnego GUI lub Viewer. Integrację
do `stm-next` prowadzi koordynator.

---

## Poprzednie przekazanie — porównanie gotowych cech, issue 19

Data: 2026-10-26. Dokumentacja `domains/frozen-domain-trial`, baza `ad584eb`,
worktree `/tmp/netcat-stmdomains-frozen-domain-trial`, docelowo `domains/start`.
Źródło prototypu: **`prototype/stmdomains-frozen-domains`, `652ab96`**,
baza `ad584eb`. Nie scalać prototypu do aplikacji. Commit dokumentacji
w wiadomości końcowej.

Wykonano issue 19: FCN–ResNet101 i DINOv2, widmo i EWT, siatka i centra,
24 pełne klatki TTMAPP i 204 kontrole. 64 konfiguracje podstawowe ze
wspólnym budżetem oraz 96 dodatkowych wariantów rozdzielczości/normalizacji.
Bez wzorców domen, zadanego K i treningu. Nowe wspólne grupowanie:
L2/PCA, epsilon w jednostkach mediany dystansu sąsiada; dwa kryteria ACF,
w tym nowa korelacja na nakładających się częściach okna. Wagi sieci stałe.

[Raport](frozen-feature-domains-trial.md),
[manifest](frozen-feature-domains-manifest.json),
[audyt grupowania](research-frozen-domain-clustering-audit.md), podgląd:
`/home/rlew/projekty/NEtCAT-domains/.scratch/frozen-feature-domains/index.html`.
Wybrane FCN/DINO przypisują 0–5.1% centrów we wnętrzach TTMAPP, bez
RED/YELLOW. Siedem wariantów ma jeden katalogowy klaster wyglądu;
DINO/centra odmawia wszystkim. Ocena porządku usuwa większość danych.
Pozostają nadmierne podziały pojedynczej sieci i błędy małych orientacji
oraz granic. Żaden ze 160 wariantów nie spełnia wszystkich warunków.
Nie wyznaczono typów strukturalnych, powierzchni ani dokładnych konturów.

Użytkownik: **„Najpierw omówmy lub rozwińmy tę próbę”**. Issue 19 pozostaje
**`claimed`**, bez zamknięcia i bez wyboru metody. Zachowano pełne wyniki;
proponowane rozwinięcie powinno rozdzielić utratę informacji w uśrednieniu,
PCA i grupowaniu. Jest jeszcze niewykonane. Nie uruchomiono treningu 20;
odbiór 13 i jakość 04 nadal otwarte. Nie przypisywać wyniku wyłącznie
modelom ani proponować samego obniżenia progu jako rozwiązania.

Sprawdzenia: 912 świeżych zestawów cech sieci siatki identycznych bez
oznaczeń; 228 identycznych zestawów klasycznych (FFT/EWT z niezależnego
powtórzenia 17, nowa ACF przeliczona); 1824 identyczne wyniki pełnego
powtórnego grupowania wybranych konfiguracji bez referencji. Wariant
centrowy sprawdzony przy odwróceniu kolejności wejścia. 1824 wyniki
zgodne z kontraktem; bez zmian źródeł i ustawień po odczycie referencji.
96 par braków detekcji identycznych na siatce; kontrast/skala zmieniają
wynik. Zakres 5 → 24 zmienia katalog wyglądu w 21/40 porównań; zgodne puste
końcowe wyniki nie dowodzą stabilności detekcji. Bezpośrednia kontrola
numeryczna nowej ACF: błąd do 3.33e-16. QtWebEngine: **46 kontroli**,
bez błędów JS, obejrzano podgląd i wykres. Składnia Python/Bash i diff
sprawdzone. Nie testowano produkcji ani natywnego GUI.

Koszt: sieci 566.52 s na RTX 5090, nowa ACF/audyt 319.95 s CPU,
grupowanie 319.16 s CPU, ocena 11.73 s. Szczyt RSS ekstrakcji ok. 1.48 GiB;
alokowane tensory CUDA 324 MiB FCN / 268 MiB DINO. Same tablice sieci ok. 3.3 GB.
Cały artefakt 35319 plików / 6642599215 B, kopia do Domains zweryfikowana
SHA-256, symlinki względne. Netcat bez instalacji nowych pakietów,
wagi z 18. Etapy runnera wykonano osobno, nie powtarzano całości wrapperem.
Nie kwalifikowano żadnej konfiguracji do benchmarku 268 klatek.

Brak zmian wspólnych modułów, wymagań, aplikacji lub Viewer. Do Domains
trafia tylko dokumentacja i mały manifest; prototyp jest na osobnej gałęzi,
dane pozostają lokalne. Integrację do `stm-next` prowadzi koordynator.

---

## Poprzednie przekazanie — przygotowanie gotowych cech, issue 18

Data: 2026-10-26. Gałąź `domains/frozen-features`, baza `9346d1a`,
worktree `/tmp/netcat-stmdomains-frozen-features`, docelowo `domains/start`.
Kod, testy, audyt źródeł i manifest: **`e6e7248`**. Commit końcowej
dokumentacji w wiadomości końcowej. Zmiany obejmują wyłącznie katalogi
STM Domains; kod służy eksperymentom i nie zmienia uruchamiania aplikacji.

Issue 18 **`resolved`**: działają oba zamrożone ekstraktory, FCN–ResNet101
z `layer1/layer2` i DINOv2 ViT-S/14 z końcowymi patch tokens. Oficjalne
wagi i przypięty kod sprawdzane SHA-256. Wykonano 16 konfiguracji na
12 obrazach (5 TTMAPP i 7 kontroli), na siatce i przy wszystkich centrach:
384 wpisy, 368 unikalnych cache. Zachowane oryginalne współrzędne, maski
pomiaru, okna i podparcie brzegu. Nie wykonywano treningu ani grupowania.

[Raport](frozen-feature-preparation.md),
[manifest](frozen-feature-preparation-manifest.json),
[audyt źródeł](research-frozen-feature-extraction-audit.md),
[instrukcja odtworzenia](../../stmdomains/experiments/frozen/README.md).
Lokalny podgląd:
`/home/rlew/projekty/NEtCAT-domains/.scratch/frozen-features/index.html`.
Krzyżyki siatki, okręgi molekuł i wybrane okno oznaczają miejsca pobierania
cech. To podgląd geometrii, nie wynik wykrywania domen.

Wykonane sprawdzenia: **41 testów pytest**; **192/192** zestawy cech
siatki bitowo identyczne w świeżym powtórzeniu bez centrów, po zmianie
danych referencyjnych; 384 kontrole geometrii/cache; niezmienione hashe
parametrów i buforów modeli przed/po. Osiem kontroli partii i kolejności:
DINO przy zmianie partii 5 → 1 różni się do 4.20e-5; zapisano niepowodzenie
pierwotnej tolerancji i osobną tolerancję 1e-4 dla tego porównania.
Zwykłe powtórzenie jest dokładne. QtWebEngine offscreen: **19 kontroli**,
bez błędów JS; obejrzano podgląd. Składnia Python/Bash i diff sprawdzone.
Nie testowano natywnego GUI, skuteczności domen ani pełnych 268 klatek.
Etapy odtworzenia wykonano osobno, bez powtarzania całości samym wrapperem.

Sprzęt/środowisko: RTX 5090, torch 2.9.1+cu128, torchvision 0.24.1+cu128,
Python 3.12.12 w lokalnym netcat; bez instalacji dodatkowych pakietów.
Ekstrakcja 37.01 s; maksimum alokatora CUDA ok. 324 MiB (FCN), 268 MiB
(DINO), maksimum RSS procesu ok. 1.34 GiB. To koszt pilotażu, bez
przyszłego grupowania. Wyniki lokalne: 1126 plików / 394049728 B;
modele i źródła: 222 pliki / 312982757 B w `.scratch/frozen-feature-assets/`.
Kopie do Domains zweryfikowano SHA-256; duże pliki pozostają poza Git.

**Następne: 19**, gotowe zależności, jeszcze nieuruchomione. Rozszerzyć
zakres wejścia i porównać cechy z klasyczną teksturą; uwzględnić pooling,
normalizację, okna 48/72 wobec 49/73 w 17 i odmowy bramki porządku.
Gotowość techniczna nie dowodzi rozróżniania orientacji, rozstawów ani
granic. Opcjonalnego DINOv3 nie uruchamiano. Trening 20, odbiór 13
i jakość 04 pozostają otwarte. Brak potrzeb zmian wspólnego kodu,
głównych wymagań lub Viewer; integrację do `stm-next` prowadzi koordynator.

---

## Poprzednie przekazanie — tekstura obrazu, issue 17

Data: 2026-10-23. Dokumentacja `domains/texture-trial`, baza `b292f2f`,
worktree `/tmp/netcat-stmdomains-texture`, docelowo `domains/start`.
Źródła: `prototype/stmdomains-texture`, commit `3bb4d36`, baza `e6d3fbc`.
Nie scalać prototypu do aplikacji. Commit dokumentacji w wiadomości końcowej.

Issue 16 zamknięto wcześniej po zatwierdzeniu użytkownika. Następnie wykonano
issue 17: lokalne widmo/autokorelacja i EWT, siatka/centra, 32 konfiguracje,
24 pełne klatki i 204 kontrole. Parametry wybrano na kontrolach rozwojowych;
częściowe referencje i odłożone ziarna oceniono później. Adaptacja EWT jest
jawnie odróżniona od publikacji STM z zadanym K. Nie trenowano modelu.

[Raport](image-texture-domains-trial.md),
[audyt API i publikacji](research-image-texture-adaptation-audit.md), podgląd:
`/home/rlew/projekty/NEtCAT-domains/.scratch/image-texture-domains/index.html`.
Wybrane warianty przypisują 0.3–5.8% centrów w referencjach, wyłącznie BLACK;
RED/YELLOW pominięte. Bramka przepuszcza 9.2–12.6% ocenianych miejsc.
EWT wcześniej tworzy jeden klaster całego zakresu. Na kontrolach scala małe
orientacje; widmo na siatce dzieli pojedynczą sieć. Zero fałszywych przypisań
na losowych punktach nie rekompensuje odmowy na TTMAPP. Filtr doboru nie
miał twardego warunku podziałów pojedynczej sieci; ujawniono brak, bez
zmiany rankingu po wynikach. Większe okno również nie rozwiązuje problemu.

Użytkownik zatwierdził: **„Tak — zachowaj porównanie i zamknij 17”**.
Issue 17 `resolved` jako badanie, bez wyboru metody produkcyjnej. Cechy,
przypisania i reguły zachowano dla 19/21/22. Następne 18 → 19 i niezależne
20 nie są uruchomione. Odbiór 13 i jakość 04 pozostają otwarte. W 19 i 13
zapisano konieczność rozdzielenia jakości cech od odmów bramki oraz oceny
podziałów jednej sieci. Nie mierzono pokrycia ani granic powierzchni.

Sprawdzenia: pełna ponowna ekstrakcja 228 obrazów bez wszystkich anotacji
i bez drzewa referencji — identyczne cechy siatki, 205 banków oraz wyniki
obu wybranych metod obrazowych. 60 dokładnych porównań braków/inwersji;
24 porównania kontrastu/skali z jawnymi drobnymi zmianami FFT. Zakres 5 → 24:
ponowne dopasowanie banku i katalogu; puste wyniki końcowe nie dowodzą
stabilności. 1824 wyniki zgodne z kontraktem, 228 odtworzonych wejść bez
anotacji, zgodność hashy kodu. QtWebEngine offscreen: 42 kontrole bez
błędów JS; obejrzano podgląd i wykres. Sprawdzono składnię Python/Bash
i diff. Etapy wykonano osobno; nie powtarzano całego przebiegu wrapperem.
Nie testowano produkcyjnej aplikacji, natywnego GUI ani pełnych 268 klatek.

CPU, po jednym wątku BLAS/OpenMP: ekstrakcja 842.47 s, predykcja 25.85 s,
ocena 3.64 s, pełna ekstrakcja bez anotacji 785.32 s. Maksymalny RSS
803324 KiB (~785 MiB). `pyewt 1.0.0` i `connected-components-3d 3.26.1`
wyłącznie w izolowanym `/tmp/stmdomains-issue17-deps`; netcat bez zmian.
Artefakty lokalne: 3455 plików, 891338928 B, kopia SHA-256 zgodna.
Brak potrzeb zmian wspólnego kodu lub konfiguracji. Dokumentacja trafia
wyłącznie do Domains; Viewer oraz gałąź integracyjna bez zmian tej sesji.

---

## Poprzednie przekazanie — SBC / MatID, issue 16

Data: 2026-10-23. Dokumentacja `domains/sbc-trial`, baza `9f2b127`,
worktree `/tmp/netcat-stmdomains-sbc`, docelowo `domains/start`.
Źródła: `prototype/stmdomains-sbc`, commit `e6d3fbc`, baza `2b70d0d`.
Nie scalać prototypu do aplikacji. Commit dokumentacji w wiadomości końcowej.

Na polecenie użytkownika przejścia do 16 zakończono issue 15 jako trzy
porównania, bez przyjęcia metody. Wykonano SBC/MatID: 228 próbek,
6 ustawień, surowa biblioteka i dwie jawne adaptacje punktowe. Kalibracja
na 102 kontrolach rozwojowych; pozostałe kontrole i TTMAPP ocenione później.
Żadna konfiguracja nie spełniła kompletu warunków. Wybrany diagnostycznie
wariant: tolerancja 1.8 px, maksymalny wektor komórki 42 px, połączenie
19.8 px, zerowe promienie także wewnątrz walidacji prototypu, zachowanie
wszystkich komponentów ≥8 i odmowa nakładającym się propozycjom.

[Raport](sbc-matid-domains-trial.md), [audyt API](research-sbc-adaptation-audit.md)
i podgląd:
`/home/rlew/projekty/NEtCAT-domains/.scratch/sbc-matid-domains/index.html`.
SBC poprawia 30% braków (99.8% przypisań), deformację i granicę przesunięcia
z błędami centrów (0.2% scaleń przy 52.2% przypisań). Jednak scala różnicę
orientacji 8° i tworzy pozorne obszary z 355/3195 losowych punktów.
TTMAPP: 63.5% przypisań, 5.9% podziałów i 5.5% scaleń warunkowych par,
wobec 70.7% / 2.8% / 0% poprzedniej komórki. Zmiana ziarna powoduje
znaczne zmiany wyniku. Komórka biblioteki jest prototypem, nie globalnym fitem.

Issue 16 **`resolved`**: użytkownik zatwierdził zachowanie porównania
i przejście następnie do tekstury 17. Zakończenie próby nie wybiera
metody produkcyjnej. Odbiór 13 i jakość 04 pozostają otwarte. Nie wybrano metody
produkcyjnej, nie mierzono powierzchni ani nie tworzono katalogu typów.

Sprawdzenia: 228/228 identycznych ponownych wyników i śladów etapów bez
referencji, po przestawieniu punktów i odwróceniu kolejności klatek;
684 wyniki zgodne z kontraktem. Kontrast/inwersja/skala: po 6 par;
obrót 37°: identyczne przypisania na 10 próbkach. Zmiana kategorii H/C
zmienia raw, lecz nie adaptację. Sprawdzono także 2 dodatkowe ziarna,
wejście bez kanonizacji i bezpośrednie zachowanie czyszczenia. 35 kontroli
lokalnego HTML w QtWebEngine bez błędów JS; obejrzano zrzut i wykres.
Sprawdzono składnię Python/Bash i diff. Nie testowano natywnego GUI ani
produkcji, nie wykonano pełnego benchmarku 268 klatek. Ostrzeżenia
numeryczne jednej kontroli zapisano w artefaktach; nie było przerwania próby.

CPU, jeden wątek BLAS/OpenMP: 91.05 s kalibracyjnych predykcji,
224.07 s dla 228 próbek × 6 ustawień; RSS 223844 KiB (~219 MiB).
Zbudowano MatID 2.2.0 z commita `5aa27776` i spglib 2.6.0 w izolowanym
`/tmp/stmdomains-issue16-deps`. Środowisko netcat, kod wspólny i główna
konfiguracja bez zmian. Dane/duże wyniki pozostają lokalne (3594 pliki,
564478701 B; kopia zweryfikowana SHA-256). Dokumentacja trafia wyłącznie
do Domains; Viewer i integracja bez zmian.

---

## Poprzednie przekazanie — orientacja i łączenie, issue 15


Data: 2026-10-23. Dokumentacja: `domains/orientation-trial`, baza `8065aea`,
worktree `/tmp/netcat-stmdomains-orientation`, docelowo `domains/start`.
Źródła: `prototype/stmdomains-orientation`, commit `2b70d0d`, baza `bc3763e`.
Nie scalać prototypu do aplikacji. Commit dokumentacji w wiadomości końcowej.

Wykonano proponowane badanie orientacji oraz łączenia sąsiadów: 31
wariantów, 24 pełne klatki i 204 kontrole. Zamrożono powtarzalność,
minimum 8 elementów i dawny katalog. Główny wynik ocenia obszary bez
warunku typu; katalog stanowi osobne porównanie. Wybrany na kontrolach
wariant komórki wymaga ≥65% dopasowanych punktów, różnicy bazy ≤0.12,
fazy ≤0.30 rozstawu i zgodności z punktem rozpoczynającym obszar.

[Raport](orientation-and-joining-trial.md) i podgląd:
`/home/rlew/projekty/NEtCAT-domains/.scratch/orientation-and-joining/index.html`.
Przy 30% braków: jedna domena, 81.9% przypisań zamiast 2–3 fragmentów
z 46.7%. TTMAPP: 70.7% zamiast 62.5%, scalenia 0/3801 ocenianych par
różnych regionów zamiast 708/2329. RED jednak spada z 28/101 do 14/101;
YELLOW nadal tylko 48/274. Granica przesunięcia z błędem centrów ma 98.1%
scaleń, a łagodna deformacja 51.0% podziałów. Same krawędzie tworzą
łańcuchy łączące różne orientacje; zgodność ze startem ogranicza to kosztem
deformacji. Sprawdzanie fazy na krawędziach nie naprawia trudnej granicy.

Stan **`claimed` do omówienia**. Komórka jest punktem odniesienia, bez
wyboru metody produkcyjnej. Proponowany następny krok: porównanie 16
na rozszerzonych kontrolach, osobno oceniając zaburzoną granicę przesunięcia,
małe różnice orientacji i RED/YELLOW. Nie uruchomiono 16/17 ani treningu;
odbiór 13 i jakość 04 pozostają otwarte. Opis kierunków to wariant
diagnostyczny: żaden nie spełnił wszystkich zapisanych warunków wyboru.

Sprawdzenia: dokładne odtworzenie 204 wcześniejszych wyników głównych
oraz z katalogiem; 1368 wyników zgodnych z kontraktem; kontrast/skala;
obrót 37° czterech kontroli daje identyczne przypisane pary wszystkich
31 wariantów. Przed oceną referencji naprawiono remisy numeryczne i
ponowiono obliczenia. Pełna ponowna ekstrakcja/predykcja bez referencji,
ze zmianą kolejności: 228 identycznych plików cech i 228 wyników.
QtWebEngine offscreen: 14 kontroli bez błędów JS; obejrzano zrzut i wykres.
Nie wykonano testów produkcyjnej aplikacji, natywnego GUI ani benchmarku
268 klatek. Nie oceniano granic pikselowych lub pokrycia warstwy.

CPU, jeden wątek BLAS/OpenMP. Ekstrakcja 205.11 s, wybór 40.47 s,
predykcja 186.77 s, ocena 2.80 s; szczyt procesowego RSS 264000 KiB
(~258 MiB), bez GPU/treningu. Bez instalacji pakietów i zmian wspólnych
modułów, środowiska lub konfiguracji. Artefakty lokalne poza Git.
Dokumentację przenosimy tylko do Domains; Viewer i integracja bez zmian.

---

## Poprzednie przekazanie — kryterium powtarzalności, kontynuacja issue 15

Data: 2026-10-23. Gałąź dokumentacji `domains/recurrence-trial`, baza
`12f3652`, worktree `/tmp/netcat-stmdomains-recurrence`, docelowo `domains/start`.
Źródła prototypu: `prototype/stmdomains-recurrence`, commit `bc3763e`,
baza `1f25b45`. Nie scalać kodu prototypu do aplikacji. Commit dokumentacji
w wiadomości końcowej; duże wyniki pozostają lokalne.

Na polecenie „zbadaj kryterium powtarzalności” wykonano kontrolowane
porównanie 38 wariantów na 24 pełnych klatkach i 180 kontrolach. Zamrożono
katalog SOAP/36 i reguły przestrzenne. Usunięto gwarantowane trafienie
środka przy przesunięciu, porównano promienie, tolerancje i progi
kalibrowane wyłącznie na kontrolach rozwojowych. Wybrany wariant:
R=36 px, tolerancja 24% lokalnego rozstawu, wynik >0.25.

[Raport](recurrence-criterion-trial.md) i podgląd:
`/home/rlew/projekty/NEtCAT-domains/.scratch/recurrence-criterion/index.html`.
Warunek przechodzi 90.9% zamiast 34.0% oznaczeń we wnętrzach referencji;
domenę otrzymuje 62.5% zamiast 31.0%. To nie dokładność: 708/2329 = 30.4%
przypisanych par z różnych regionów scalono w jedną domenę. W YELLOW
nadal tylko 13/274 centrów ma domenę; wiele pozostałych odpada na zbyt
małych składowych zgodnych orientacyjnie. Losowe kontrole: 2/3195 akceptacji,
zero składowych. Przy błędzie centrów 0.72 px akceptacja regularnej sieci
rośnie z 13.3% do 95.5%, lecz duże braki nadal powodują podziały/odmowy.
Rzędy z niezależną fazą pokazują, że lokalna powtarzalność nie wystarcza
jako dowód spójnej domeny 2D; nie mają kompletnej prawdy domen.

**Issue 15 nadal `claimed`**: użytkownik wcześniej wybrał rozwinięcie próby,
a obecne zlecenie dotyczyło tego kryterium, nie zamknięcia całego pytania.
Nie uruchomiono 16 ani treningu. Następny proponowany eksperyment:
estymacja orientacji i lokalnej komórki oraz łączenie sąsiadów, z kontrolą
scaleń, braków i skorelowanych struktur. Katalog rozstawów pozostaje osobną
luką. Bez wyboru metody produkcyjnej; odbiór 13 i protokół 04 nadal otwarte.

Sprawdzenia wykonane: dokładne odtworzenie starego warunku i domen na
156 próbkach, monotoniczność wyniku na 204, obrót/kolejność/kontrast/skala,
walidacja 1020 wyników. Dwa pełne powtórzenia bez referencji, jedno także
z losową kolejnością: po 204 identyczne pliki NPZ z 38 wariantami.
Ponowne przygotowanie wejścia końcowym kodem: identyczne 205 plików analizy
oraz 199 oceny. QtWebEngine offscreen: 13 kontroli bez błędów JS;
obejrzano zrzut i wykres. Nie wykonano testów produkcyjnej aplikacji,
natywnego GUI ani pomiaru 268 klatek. Nowe kontrole bez dopasowanego
katalogu oceniono tylko dla warunku/składowych bez typu; patrz raport.

CPU, jeden wątek BLAS/OpenMP. Ekstrakcja 29.61 s, wybór 3.71 s,
predykcja wszystkich wariantów 24.98 s, ocena 3.10 s; szczyt procesowego
RSS 217 780 KiB (~213 MiB), bez GPU/treningu. Brak instalacji pakietów,
zmian środowiska, wspólnych modułów lub głównej konfiguracji. Artefakty
~230 MB poza Git. Przekazanie ogranicza się do dokumentacji Domains;
nie aktualizowano gałęzi Viewer ani integracyjnej.

---

## Poprzednie przekazanie — pierwsza próba otoczeń molekuł, issue 15

Data: 2026-10-23. Gałąź dokumentacji `domains/local-neighborhood-trial`,
baza `76dd4a3`, worktree `/tmp/netcat-stmdomains-neighborhoods`.
Źródła prototypu: osobna gałąź `prototype/stmdomains-neighborhoods`,
commit `1f25b45`. Nie scalać prototypu do aplikacji.

Wykonano porównanie prostego opisu odległości/kątów i SOAP, promieni
24/36 px, wspólnego HDBSCAN bez K, oceny powtarzalności i przestrzennych
składowych. 24 pełne klatki TTMAPP + 132 kontrole, 624 kompletne wyniki.
[Raport](local-neighborhood-domains-trial.md) zawiera parametry, tabele,
odmowy, stabilność, koszty i ograniczenia. Podgląd lokalny:
`/home/rlew/projekty/NEtCAT-domains/.scratch/local-neighborhood-domains/index.html`.

Stan **`claimed`**, nie `resolved`: użytkownik po przedstawieniu wyniku
wybrał „Najpierw omówmy lub rozwińmy tę próbę”. Nie uruchomiono 16.
SOAP/36 przypisuje 31.0% centrów w referencjach, tylko BLACK; RED/YELLOW
odpadają na kryterium powtarzalności mimo przeważnie wystarczającej liczby
sąsiadów. Proponowana kolejna próba w 15 ma zbadać ten warunek i tolerancję
położeń z kontrolą fałszywego porządku. Nie została jeszcze uruchomiona.
Pozostają też nadmierne podziały prostego opisu i scalenia typów SOAP.

Wykonane sprawdzenia: walidacja 624 wyników, rotacja/kontrast/skala/braki,
rzadki układ, rozszerzenie 5 → 24. Powtórna ekstrakcja/predykcja bez
referencji: 624 pliki identyczne bajtowo. Losowa kolejność oznaczeń/klatek:
624 identyczne zestawy przypisań po sortowaniu ID. QtWebEngine offscreen:
15 kontroli scenariuszy/widoków/referencji, bez błędów JS; obejrzano zrzut.
Naprawiono błąd numeryczny granicy promienia i powtórzono całość przed
końcowym raportem. Nie testowano aplikacyjnego GUI, nie uruchamiano
testów produkcyjnych ani pomiaru 268 klatek. Brak zmian produkcyjnych.

Ekstrakcja 12.24 s, dopasowanie/predykcja/zapis 42.31 s, szczyt RSS
330 636 KiB, CPU, bez GPU. Zależności dodatkowe DScribe 2.1.2 i sparse
0.19.2 wyłącznie w `/tmp/stmdomains-issue15-deps`; `netcat` bez zmian.
Nie ma nowych potrzeb zmian wspólnego kodu ani konfiguracji. Dane,
cechy, duże wyniki i podgląd pozostają lokalne. Mapa i indeks zachowują
otwartą dyskusję; odbiór 13 i jakość 04 nadal otwarte.

---

## Poprzednie przekazanie — przygotowanie wspólnego wejścia, issue 14

Data: 2026-10-23. Gałąź `domains/unsupervised-input`, baza `d134439`.
Worktree `/tmp/netcat-stmdomains-input`, docelowo `domains/start`.
Commit kodu, testów i dokumentacji w wiadomości końcowej.

Wykonano issue 14: `stmdomains.experiments` przygotowuje audytowane obrazy
MPP i bieżące oznaczenia w raw, 132 kontrole syntetyczne oraz osobny pakiet
oceny z 18 referencjami/54 wnętrzami. Pilot ma 24 pełne klatki i 6730
oznaczeń, włącznie z klatką 255. Generator nie uruchamia detektora ani treningu.

[Raport](unsupervised-input-preparation.md) zawiera polecenie odtworzenia;
[protokół](experiment-input-protocol.md) definiuje schematy wejścia/wyniku,
miary z odmowami i warunki porównania. Lokalny artefakt:
`/home/rlew/projekty/NEtCAT-domains/.scratch/unsupervised-input/index.html`.
Dane, obrazy, maski i duże manifesty pozostają poza Git.

Sprawdzenia: 35 testów pytest w `netcat`, oba źródłowe SHA-256, geometria
6730 bboxów (roundtrip 0 px), dokładne odtworzenie 18 PNG i zgodność masek
z poprzednim audytem. Wszystkie 156 próbek przechodzą walidację. Wszystkie
157 plików analizy są identyczne po ponownym przygotowaniu bez referencji.
Obejrzano statyczny arkusz podglądów i sprawdzono składnię JS w QJSEngine;
interakcji DOM w przeglądarce oraz natywnego GUI aplikacji nie testowano.
Przygotowanie końcowe: 5,89 s, RSS 445 916 KiB; bez GPU.

Issue 14 ma status `resolved`. Mapa i indeks wskazują 15 jako następny
zalecany eksperyment; odblokowane także 16, 17, 18 i 20. 04 i 13 pozostają
otwarte. Ograniczenia: adapter tylko dla audytowanego TTMAPP, częściowe
używane już referencje, brak rzeczywistej kalibracji i niezależnej akwizycji.
Nie wykonano nowego algorytmu, pełnego eksportu 268 klatek ani pomiaru pokrycia.

Wykorzystano istniejący czytnik MPP bez zmian. Ekstrakcję referencji
przeniesiono z audytowanego prototypu `4e7a757` do lokalnego modułu oceny.
Brak nowych potrzeb zmian wspólnego kodu, konfiguracji i środowiska.

---

## Poprzednie przekazanie — mapa prób treningu bez etykiet

Data: 2026-10-21. Gałąź `domains/self-supervised-training-map`, baza `63c5d0b`.
Worktree `/tmp/netcat-stmdomains-training-map`, docelowo `domains/start`.
Commit dokumentacji w wiadomości końcowej.

Na polecenie użytkownika rozwinięto ostatnie badanie w
[siedem ticketów 20–26](issues/README.md#trening-bez-etykiet-domen):
przygotowanie treningu, porównanie AE/rVAE, lokalne SSL, decyzję po pierwszych
próbach oraz warunkowe grafy, maskowany AE i adaptację gotowego modelu.
Wszystkie mają status `open`; żadnego modelu nie wytrenowano.

Przygotowanie 20 zależy od wspólnego wejścia 14. Próby 21 i 22 zależą od
20 oraz wyniku tekstury 17, mogą być prowadzone niezależnie. Zestawienie 23
czeka na 19, 21 i 22. Odbiór 13 uzupełniono o 23. Rozszerzenia 24–26 są
warunkowe i nie blokują odbioru, dopóki nie wybierzemy ich w 23; wtedy
należy dodać odpowiednie zależności 13 i krawędzie diagramu. Tracker wyklucza
niewybrane rozszerzenia z frontier mimo spełnienia samych zależności.

Zakres zachowuje pełne pola pomiarowe, brak etykiet domen i zadanej liczby
grup, osobne typ/orientację, kontrolę rozstawu oraz granic. Protokół oddziela
opis obecnej serii od oceny przenoszenia, z podziałem przed wycinaniem okien,
kontrolą przecieku, budżetem, powtórzeniami i odtwarzalnymi checkpointami.
Pierwszy sprzęt to RTX 5090; 96 GB i Colab są opcjami uzasadnianymi pomiarem.

Zaktualizowano mapę, indeks z diagramem, odnośniki ze wcześniejszego planu,
README i badania oraz wspólne wejście 14. Zakres 18–19 pozostaje zamrożony,
statusy zakończonych prób 10–12 i mapa szkieletu bez zmian. Następny krok
badawczy nadal to 14. Nie zmieniono kodu ani współdzielonych zależności.

Sprawdzenia dokumentacji: lokalne linki, unikatowe ID, zgodność `Blocked by`
z `Dependencies` i diagramem, brak cykli oraz `git diff --check`.
Nie uruchamiano testów aplikacji, GUI, modeli ani nowych pomiarów sprzętu.
Brak nowych potrzeb zmian współdzielonych modułów.

---

## Poprzednie przekazanie — trening bez etykiet do odkrywania domen

Data: 2026-10-21. Gałąź `domains/self-supervised-training-research`, baza `a298c1d`.
Worktree `/tmp/netcat-stmdomains-training-research`, docelowo `domains/start`.
Commit dokumentacji w wiadomości końcowej.

Na polecenie użytkownika, z użyciem `research`, przygotowano
[przegląd metod uczonych bez etykiet](research-self-supervised-domain-learning.md).
Użytkownik dopuścił własny trening i wskazał RTX 5090 32 GB VRAM / 128 GB RAM,
a przy dobrych wynikach drugi komputer z Blackwell Max-Q 96 GB VRAM lub Colab.
Zgoda na trening nie zmienia zakazu uczenia klas z ręcznie wskazanych domen
ani wymagań zero/jedna/wiele domen i rozdzielenia typu od orientacji.

Raport rozróżnia bezpośrednie precedensy STM/AFM/PFM od adaptacji ogólnego
uczenia reprezentacji. Zaleca najpierw ciągły rVAE i lokalne uczenie cech,
następnie rozważenie grafu molekuł lub maskowanego autoenkodera. Zawiera
ograniczenia narzuconej liczby kategorii, utraty orientacji/fazy, przecieku
danych i kosztu. Potrzebne są osobne oceny obecnej serii oraz uogólnienia.

Mapę, README i plan uzupełniono o nowy zakres. We wspólnym wejściu usunięto
ogólne wykluczenie treningu; dotychczasowe tickety przygotowania i porównania
gotowych cech nadal dotyczą modeli zamrożonych. Nie dodano ani nie zamknięto
ticketów treningowych przez samo badanie źródeł.

Sprawdzenia: publikacje i repozytoria autorów, lokalne odnośniki, zachowanie
metadanych ticketów i `git diff --check`. Odczytano GPU/sterownik przez
`nvidia-smi` poza piaskownicą oraz metadane lokalnego `netcat`; brak pomiarów
wydajności treningu i pełnego sprawdzenia zgodności bibliotek. Nie uruchamiano
modeli, nie instalowano zależności, nie pobierano wag ani nie przenoszono
danych na drugi komputer lub do Colab. Bez zmian kodu i testów aplikacji.
Brak nowych potrzeb zmian współdzielonych modułów.

---

## Poprzednie przekazanie — zadania przygotowania i porównania ML

Data: 2026-10-21. Gałąź `domains/training-free-ml-map`, baza `abf7869`.
Worktree `/tmp/netcat-stmdomains-ml-map`, docelowo `domains/start`.
Commit aktualizacji dokumentacji w wiadomości końcowej.

Na polecenie użytkownika rozwinięto wnioski przeglądu ML w dwa otwarte
tickety istniejącej mapy `wayfinder`:

- [Przygotowanie gotowych cech bez własnego treningu](issues/18-frozen-feature-preparation.md)
  — task / AFK, po wspólnym wejściu. Modele, geometria cech, zapis
  konfiguracji i sprawdzenie odtwarzalności; bez oceny skuteczności domen.
- [Porównanie domen z gotowych cech](issues/19-frozen-feature-domains.md)
  — prototype / HITL, po przygotowaniu cech i wyniku klasycznej tekstury.
  FCN–ResNet101 i DINOv2, opcjonalnie DINOv3, bez uczenia na ramkach
  i bez treningu wag. Grupowanie nienadzorowane jest dozwolone.

Próba tekstury zachowuje autokorelację/EWT; jej wynik jest punktem
odniesienia dla ML, nawet jeśli nie wykrywa domen poprawnie. Geometria
otoczenia molekuł pozostaje niezależnym porównaniem. Wspólne wejście
uzupełniono o metadane modeli i kontrolę skalowania; nie czeka na wagi.
Odbiór metod zależy również od wyniku porównania ML. DINOv3 i własny trening
sieci nie są nowymi obowiązkowymi etapami. Zaktualizowano mapę, indeks,
diagram zależności, README oraz odnośniki w planie i raporcie badawczym.

Sprawdzenia: lokalne odnośniki, kompletność metadanych i indeksu, zgodność
zależności z linkami i diagramem, brak cykli oraz `git diff --check`.
Bez uruchamiania eksperymentów, instalacji, pobierania wag, testów aplikacji
i odbioru GUI. Wszystkie nowe zadania pozostają `open`, bez prowadzącego.
Nie zmieniono danych, kodu ani konfiguracji wspólnych modułów.

---

## Poprzednie przekazanie — ML bez własnego treningu do odkrywania domen

Data: 2026-10-21. Gałąź `domains/training-free-ml-research`, baza `2a35377`.
Worktree `/tmp/netcat-stmdomains-ml-research`, docelowo `domains/start`.
Commit aktualizacji dokumentacji w wiadomości końcowej.

Na polecenie użytkownika, z użyciem `research`, przygotowano
[przegląd ML i gotowych sieci](research-training-free-ml-domain-discovery.md)
na podstawie publikacji, kodu i kart modeli autorów. Odróżniono grupowanie
nienadzorowane, użycie zamrożonego modelu i własny trening bez etykiet.
Pierwsze dwa kierunki pozwalają wykonać próby bez uczenia na zaznaczonych
domenach użytkownika; nie potwierdzono gotowego rozwiązania całego zakresu.

Do [kroku 17](issues/17-image-texture-domains.md) dodano propozycję
porównania autokorelacji/EWT z wczesnymi cechami FCN–ResNet101 oraz DINOv2,
opcjonalnie DINOv3. Gotowe cechy obrazowe można próbkować na siatce i przy
istniejących centrach. Krok 15 zachowuje niezależną bazę geometryczną.
Mapę i README uzupełniono o raport; numeracja, zależności i statusy ticketów
pozostają aktualne. Następny krok badawczy to nadal przygotowanie wejścia
14, potem próby 15–17 i odbiór 13 z protokołem jakości 04.

Sprawdzenia: źródła pierwotne, lokalne odnośniki, zachowanie metadanych
ticketów i `git diff --check`. Bez uruchamiania modeli, pobierania wag,
instalacji zależności, testów aplikacji i odbioru GUI. Wydajność oraz
skuteczność na TTMAPP wymagają dopiero eksperymentu. Brak zmian danych,
kodu produkcyjnego i nowych potrzeb wspólnych modułów.

---

## Poprzednie przekazanie — nowe tickety prób samodzielnego wykrywania domen

Data: 2026-10-21. Gałąź `domains/unsupervised-experiment-map`, baza `5a7209c`.
Worktree `/tmp/netcat-stmdomains-experiment-map`, docelowo `domains/start`.
Commit aktualizacji dokumentacji w wiadomości końcowej.

Na polecenie użytkownika przeniesiono plan eksperymentów do istniejącej
[mapy metod i zapisu](map-methods-and-save.md), zgodnie z lokalnym trackerem
`wayfinder`. Dodano cztery otwarte zadania/pytania:

- [Wspólne wejście i kontrole](issues/14-unsupervised-input-and-controls.md) — task / AFK.
- [Otoczenie zaznaczonych molekuł](issues/15-local-neighborhood-domains.md) — prototype / HITL.
- [SBC/MatID z niepełnych centrów](issues/16-sbc-matid-domains.md) — prototype / HITL.
- [Lokalna tekstura STM](issues/17-image-texture-domains.md) — prototype / HITL.

Przygotowanie wejścia zależy od rozstrzygniętych kontraktów importu i pojęć;
trzy niezależne próby zależą od tego przygotowania. Rozszerzono zależności
[odbioru metod](issues/13-method-acceptance.md) o wyniki trzech prób.
[Pełny protokół jakości](issues/04-reference-and-quality.md) nadal jest
wymagany do odbioru, ale nie blokuje wstępnego porównania na obecnych danych.
Zakończonych badań pokrycia, typów i granic nie otwarto ponownie.

Następny krok w tym cyklu badawczym to przygotowanie wspólnego wejścia;
pierwszą zalecaną próbą jest otoczenie molekuł. Analiza obejmuje pełne pola
klatek bez dostępu do ramek referencji, z przypadkami zero/jedna/wiele domen.
Zaktualizowano rejestr, diagram i README; mapa jest indeksem, a dawny plan
prowadzi do ticketów przechowujących szczegóły. Nie rozwiązano nowych pytań
ani nie uruchomiono eksperymentów przez tę aktualizację.

Sprawdzenia dokumentacji: lokalne odnośniki, kompletność metadanych,
zgodność zależności z linkami i diagramem, brak cykli oraz `git diff --check`.
Bez testów aplikacji, analizy danych, instalacji zależności i odbioru GUI.
Brak zmian produkcyjnych lub nowych potrzeb wspólnych modułów. Wcześniejsze
wyniki i ustalenia integracyjne poniżej pozostają aktualne.

---

## Poprzednie przekazanie — samodzielne wyszukiwanie domen w STM/AFM

Data: 2026-10-21. Gałąź `domains/stm-afm-unsupervised-research`,
baza `53e5fb4`. Worktree `/tmp/netcat-stmdomains-stm-afm-research`,
docelowo `domains/start`. Commit dokumentacji w wiadomości końcowej.

Na bezpośrednie polecenie użytkownika, z użyciem `research`, przygotowano
[przegląd STM/AFM](research-stm-afm-unsupervised-domain-discovery.md)
i [plan kolejnych eksperymentów](unsupervised-domain-experiments.md).
Publikacje dostarczają nienadzorowanych sposobów analizy, lecz w sprawdzonych
źródłach nie potwierdzono jednego gotowego rozwiązania całego zakresu.
Sprawdzono szczególnie narzucaną liczbę grup, wybór wzorców oraz różnicę
między odtworzeniem komórki, grupowaniem cech i domeną przestrzenną.

Doprecyzowanie użytkownika: gotowe oznaczenia molekuł są wejściem; nie
zakładamy istnienia domen i nie trenujemy klasyfikatora na wybranych domenach.
Plan obejmuje analizę pełnych pól klatek, bez masek referencji na wejściu,
oraz kontrole zero/jedna/wiele domen. Ramki służą wyłącznie późniejszej,
częściowej ocenie. To rozszerzenie zakresu następnej próby względem lokalnych
badań wnętrz w krokach 10–12, nie zmiana dawnych wyników. Nieoznaczone
obszary nie stają się negatywnymi przykładami.

Kolejność planu: wspólne kontrole i opis otoczenia centrów, potem SBC/MatID
oraz lokalna tekstura obrazu na tym samym wejściu. Porządek, podobieństwo,
spójność przestrzenna i powierzchnie materiału pozostają rozdzielone.
Plan nie został wykonany, metody nie wybrano. Kroki 10–12 nadal `resolved`
jako zakończone badania; protokół 04 i odbiór 13 pozostają otwarte.

Sprawdzenia: źródła pierwotne, teksty metod i wskazane repozytoria autorów;
kontrola lokalnych odnośników nowych/zmienionych dokumentów oraz
`git diff --check`. Bez instalacji zależności, nowego przetwarzania TTMAPP,
testów aplikacji i odbioru GUI. Nie zmieniono danych ani kodu produkcyjnego.
Brak nowych potrzeb wspólnych modułów; wcześniejsze ustalenia poniżej.

---

## Poprzednie przekazanie — badanie metod domen i klastrowania obiektów

Data: 2026-10-21. Gałąź `domains/general-domain-clustering-research`,
baza `035bc11`. Worktree `/tmp/netcat-stmdomains-general-research`,
docelowo `domains/start`. Commit dokumentacji w wiadomości końcowej.

Na polecenie użytkownika i z użyciem umiejętności `research` przygotowano
[przegląd źródeł pierwotnych](research-domain-discovery-and-object-clustering.md).
Obejmuje grupowanie centrów, opis otoczenia obiektów, SBC/MatID, teksturę
obrazu oraz łączenie przestrzenne z użyciem grafów. Rozróżnia wyniki publikacji,
właściwości dostępnego kodu i nasze propozycje transferu do STM Domains.

Rekomendowane porównanie obejmuje trzy kierunki: cechy otoczenia i grupowanie,
SBC dla periodycznych punktów oraz teksturę obrazu. MolTrack pozostaje
porównaniem. Nie wybrano metody, nie wykonano nowego eksperymentu i nie
zmieniono statusów 10–13. Nie rozszerzono produkcyjnego zakresu aplikacji.

Wykonano przegląd publikacji, dokumentacji i wskazanych fragmentów kodu,
kontrolę lokalnych odnośników i `git diff --check`. Odczytano wersje pakietów
z metadanych `netcat`; nie instalowano zależności ani nie uruchamiano metod,
testów aplikacji czy GUI. Wydajność i jakość kandydatów na TTMAPP pozostają
do sprawdzenia. Brak nowych potrzeb zmian wspólnych modułów; wcześniejsze
ustalenia integracyjne zachowano poniżej.

---

## Poprzednie przekazanie — audyt MolTrack

Data: 2026-10-21. Gałąź `domains/moltrack-method-audit`, baza `2e0c8d1`.
Worktree `/tmp/netcat-stmdomains-moltrack-audit`, docelowo `domains/start`.
Commit dokumentacji podany w wiadomości końcowej.

[Audyt](moltrack-method-audit.md) opisuje rzeczywiste ścieżki M6, M3/M6,
teksturę A/B/C oraz ograniczenie klasyfikatora do wcześniej wyznaczonych
domen. Rozróżnia przybliżenie powierzchni wokół centrów od sumy masek/bboxów;
żadne nie jest automatycznie powierzchnią całego płata.

Użytkownik wskazał potrzebę ogólnego znajdowania domen poza wariantami
znanego układu. Zapisano propozycję próby lokalnego wzoru obrazu w kilku
skalach, z osobnym typem i orientacją. MolTrack jest materiałem porównawczym.
Nie zatwierdzono nowego algorytmu ani wymagania pracy całkowicie bez oznaczeń.
Kroki 10–12 pozostają `resolved`; odbiór 13 i protokół jakości 04 są otwarte.

Wykonano audyt kodu i odnośników oraz `git diff --check`. Nie uruchamiano
algorytmów, testów aplikacji ani GUI. Brak zmian produkcyjnych, nowych danych
i nowych potrzeb wspólnych modułów. Dotychczasowe potrzeby integracyjne
opisane niżej pozostają aktualne.

---

## Poprzednie przekazanie — krok 12

Data: 2026-10-21. Gałąź dokumentacji: `domains/phase-boundaries`.
Baza `a103f99`, claim `2cd4e02`; commit raportu podany w wiadomości końcowej.
Worktree `/tmp/netcat-stmdomains-boundaries`, docelowo `domains/start`.
Źródła: **`prototype/stmdomains-boundaries`, `c33cc5b` — nie scalać do aplikacji.**

[Krok 12](issues/12-phase-boundaries.md) zakończono jako eksperyment (`resolved`).
[Raport](phase-boundaries-trial.md) obejmuje 7 wariantów, 19 kontroli
syntetycznych i 18 klatek / 54 wnętrza TTMAPP. Wynik gotowy do oceny użytkownika;
nie deklarujemy zatwierdzenia metody ani parametrów.

Niedopasowanie wektorów między centrami rozdziela proste domeny kontrolne
przy przesunięciu 4/8 px bez dzielenia przez pojedynczy defekt. Nie wykrywa
1 px, zależy od centrów i wiarygodnej sieci. Dwa piki przyjęto tylko w 7/54
wnętrz TTMAPP. Prosta faza obrazu daje nadmierne cięcia i myli odwrócenie
kontrastu z granicą. Komponenty grafu nie są powierzchniami domen; rozłączenie
przez brak danych nie oznacza wyznaczonej linii. Dokładność granic realnych
nie jest dostępna z obecnych przybliżonych ramek orientacyjnych.

Podgląd: `/home/rlew/projekty/NEtCAT-domains/.scratch/phase-boundaries-trial/index.html`.
Obok pełny JSON, CSV, inspekcje i zrzuty. Parametry, hashe, metryki i polecenie
odtworzenia są w raporcie i README prototypu. Poza wnętrzami nie pobierano
pikseli do obliczeń; dane źródłowe i maski pozostały niezmienione.

Wykonane sprawdzenia: tożsamość wejścia i geometria, 95 389 węzłów we wnętrzach,
6854 środków cięć, 87 365 pełnych okien fazy; 76 niezależnych kontroli miar par;
6 niezmienionych wyników fazowych po usunięciu samych centrów i niezależność
od otoczenia referencji na kontroli oraz TTMAPP 258. QtWebEngine: 37 przypadków,
7 metod, 24 kroki, wybory/nakładki/gamma/nawigacja/tabela/reset/brak wyniku;
bez błędów JS, obejrzano zrzuty. Generator 3,91 s przed końcowym JSON/CSV,
588,59 MiB RSS; HTML 4 500 199 B. Sprawdzono linki i `git diff --check`.
Nie uruchamiano testów aplikacji ani nie wykonywano odbioru użytkownika.

Próby 10–12 są zakończone. Ograniczenia przekazano do otwartego odbioru 13;
04 opisuje konkretną przyszłą potrzebę referencji granicy przesunięcia.
Nowych anotacji nie żądano przed zakończeniem eksperymentu. Brak zmian
wspólnych i produkcyjnych. Wcześniejsze ustalenia integracyjne poniżej.

---

## Poprzednie przekazanie — krok 11

Data: 2026-10-21. Gałąź dokumentacji: `domains/structural-type-catalogue`.
Baza `8b16b8c`, claim `d8cdd77`; commit raportu i przekazania podany w wiadomości
końcowej. Worktree `/tmp/netcat-stmdomains-types`, docelowo `domains/start`.
Źródła: **`prototype/stmdomains-types`, `f2608c7` — nie scalać do aplikacji.**

[Krok 11](issues/11-structural-type-catalogue.md) zakończono jako eksperyment
(`resolved`). [Raport](structural-type-catalogue-trial.md) obejmuje 9 wariantów,
18 klatek / 54 wnętrza TTMAPP oraz 19 kontroli syntetycznych. Użytkownik
wyjaśnił, że kolory oznaczają głównie różne orientacje tej samej sieci.
Wynik przygotowano do obejrzenia; nie deklarujemy zatwierdzenia algorytmu.

Cechy rozstawu i różnic odległości pozwalają rozdzielić proste struktury
kontrolne bez zmiany typu po obrocie. Cecha rozwijana na tych kontrolach nie
ma niezależnej walidacji. Na TTMAPP tworzy 34 grupy kandydatów; zmiana zakresu
zmienia 11,29% relacji par. Ubytki centrów, defekty, rozmiar okna i fałszywy
porządek w szumie pozostają problemem. Wąski RED często nie mieści pełnego
pomiaru; taki brak danych nie oznacza nieporządku. Nie wybrano metody.
Luki przekazano do otwartego odbioru 13; krok 12 osobno bada granice.

Podgląd: `/home/rlew/projekty/NEtCAT-domains/.scratch/type-catalogue-trial/index.html`.
Obok JSON, CSV dostępności/cech/przypisań, zestawienie i raporty inspekcji.
Źródła, parametry, hashe i polecenie odtworzenia opisują raport oraz README
prototypu. Pełny obszar każdej cechy mieści się w referencji i fizycznym polu.

Wykonane sprawdzenia: tożsamość wejścia i geometria, 7014 pomiarów z poprawnym
wsparciem, 349 średnic grup i 81 okien niezależnych od otoczenia. FFT pozostaje
identyczne po usunięciu samych centrów. QtWebEngine: 37 przypadków, 9 wariantów,
26 kroków scenariuszy, wybory/nakładki/gamma/nawigacja/reset/brak wyniku;
bez błędów JS. Obejrzano zrzuty. Generator: 7,10 s przed CSV / 618,43 MiB RSS;
HTML 16 068 171 B. Sprawdzono linki dokumentacji i `git diff --check`.
To inspekcja eksperymentu; nie uruchamiano testów aplikacji ani nie wykonano
odbioru użytkownika. Kod produkcyjny, dane i maski źródłowe pozostały bez zmian.

Brak nowych potrzeb wspólnych modułów. Wcześniejsze ustalenia integracyjne
pozostają w przekazaniach poniżej. Duże wyniki lokalne, bez publikacji.

---

## Poprzednie przekazanie — zakończenie kroku 10

Data: 2026-10-21. Gałąź dokumentacji: `domains/coverage-and-scale`.
Raport próby: `25c6aba`; obecna zmiana zamyka status po omówieniu wniosków.
Worktree: `/tmp/netcat-stmdomains-coverage`; docelowo `domains/start`.
Commit dokumentacji podany w wiadomości końcowej. Źródła prototypu:
**`prototype/stmdomains-coverage`, `e67ca93` — nie scalać do aplikacji.**

[Próba zadania 10](coverage-partial-reference-trial.md): wykonano 10 wariantów
na 18 klatkach / 54 wnętrzach częściowej referencji. Dodano cztery ubytki
centrów klatki 250 oraz kontrolę całego pola. Parametrów nie dostrajano.
Dane i maski referencji pozostały niezmienione; nie oceniano obszarów poza nimi.

Mediana zachowania znanego materiału: fixed45 97,71%, fixed65 99,51%, bright3
45,00%, texture3 23,87%. Ubytek do 25% centrów w klatce 250 obniża fixed45
z 97,63% do 26,30%; przy trzech centrach auto65 obejmuje całe pole. Wyniki
uzasadniają ograniczenia tych kandydatów, nie wybór gotowej metody.

Podgląd: `/home/rlew/projekty/NEtCAT-domains/.scratch/coverage-partial-trial/index.html`.
Obok `results.json`, CSV klatek/regionów, 22 NPZ masek, zestawienia PNG i raporty
inspekcji. Polecenie odtworzenia, parametry i hashe są w raporcie i README prototypu.

Wykonano kontrolę hashy wejścia, geometrii raw/PNG, wyłączenia kreski/paddingu,
zgodności metryk 238 masek i 10 masek klatki 268 z pierwszą próbą. Metody
obrazowe są niezmienne przy ubytkach centrów. QtWebEngine: 22 przypadki,
15 kroków scenariuszy, wybory i nakładki, gamma, nawigacja, reset, brak wyniku;
bez błędów JS. Obejrzano zrzut i zestawienia wszystkich klatek dla dwóch metod.
Generator: 28,49 s / 590,40 MiB RSS, HTML 3 839 863 B. Sprawdzono linki dokumentacji
oraz `git diff --check`. Nie uruchamiano testów ani nie zmieniano kodu aplikacji.

Próba wykonana i omówiona; [ticket 10](issues/10-coverage-and-scale.md) ma status
`resolved` jako zakończony eksperyment, bez zatwierdzenia metody pomiarowej.
Nie czeka na krok 11. Odbiór metod nadal obejmuje nierozstrzygnięte granice,
nadmiar maski i warunki odmowy; zmiana statusu nie zalicza tych sprawdzeń.
Brak nowych referencji nie blokował
próby; nie poproszono o dodatkowe dane. Pełna ocena nadmiaru maski poza ramkami
pozostaje niedostępna. Można kontynuować lokalne porównania na obecnych danych.
Nie zgłoszono nowych zmian wspólnych; wcześniejsze potrzeby integracyjne
pozostają w zachowanym przekazaniu poniżej.

Przy zmianie statusu sprawdzono spójność odwołań i `git diff --check`.
Nie uruchamiano ponownie eksperymentów ani testów aplikacji. Krok 11 nie został
rozpoczęty tą zmianą dokumentacji.

---

## Poprzednie przekazanie — wstępna próba pokrycia i skali

Data: 2026-10-21. Gałąź dokumentacji: `domains/coverage-and-scale`, baza `c80d9e9`.
Worktree: `/tmp/netcat-stmdomains-coverage`; docelowo `domains/start`.
Claim: `fd0c119`; commit niniejszego przekazania podany w wiadomości końcowej.
Źródła prototypu: `prototype/stmdomains-coverage`, commit `3f2dee6`.
**Nie scalać gałęzi prototypu do aplikacji.**

[Pokrycie i skala](issues/10-coverage-and-scale.md): wykonano i omówiono
porównanie wstępne; pytanie nadal `claimed`. Użytkownik potwierdził dalszą próbę
z referencjami. Następnie dostarczył częściowe oznaczenia domen opisane
w uzupełnieniu poniżej i zaakceptował ich użycie na najbliższe próby.
Nie zwalidowano metody; pełny odbiór nadal wymaga protokołu jakości.

[Raport](coverage-and-scale-pilot.md): 25 obrazów, 10 wariantów, oddzielny wpływ
skali, braków oznaczeń, kontrastu i wygładzania. Na kontrolach wykazano błędne
scalenia/podziały i fałszywy materiał na samym szumie. Wspólna skala usuwa
rozrost maski z trzech centrów, lecz nie dostarcza pełnej granicy warstwy.
Metryki TTMAPP bez referencji pozostają niedostępne.

Doprecyzowanie użytkownika: pokrycie obejmuje materiał na dowolnym widocznym
poziomie warstwy. Ciemne miejsca bez rozpoznawalnych molekuł i innych
wystarczających przesłanek pozostają nierozstrzygnięte, nie są automatycznie
podłożem ani potwierdzoną niższą warstwą. Zaktualizowano słownik, kontekst
referencji oraz zastosowanie dotychczasowych reguł statystyk częściowych.
Nie zmieniono liczebności oznaczeń ani ich mianownika.

Artefakt lokalny:
`/home/rlew/projekty/NEtCAT-domains/.scratch/coverage-and-scale/index.html`.
Obok są metryki, inspekcja, porównanie powtarzalności i podglądy ośmiu klatek
bez nakładek w `reference-candidates/`. To kandydaci do referencji, nie ich maski.
Odtworzenie jednym poleceniem opisuje raport i README na gałęzi prototypu.

Wykonano: kontrolę hashy wejścia i liczby centrów, powtórzenie 230 pierwotnych
wariantów z identycznymi maskami/metrykami, inspekcję scenariuszy HTML,
przełączników, gamma i braków wyniku w QtWebEngine oraz oglądanie zrzutów.
Ostateczny generator: 28,91 s, 589,81 MiB RSS (pełny odczyt i generowanie),
HTML 2,38 MiB. Kontrola lokalnych linków, statusów, grafu i `git diff --check`
przed commitem. Nie dodawano testów prototypu ani nie uruchamiano testów
produkcyjnej aplikacji; kod produkcyjny pozostaje bez zmian.

Następny krok badawczy: wykorzystać obecne oznaczone wnętrza do lokalnego
porównania. Dodatkowe referencje pozyskiwać dopiero po wykazaniu konkretnej
potrzeby; nie są warunkiem rozpoczęcia tej próby. Nie utworzono duplikatu ticketu.
Budowa szkieletu z pierwszej mapy może przebiegać niezależnie. Do integratora nie
zgłoszono nowych zmian wspólnych; wcześniejsze potrzeby środowiska i importu
pozostają poniżej.

## Uzupełnienie: częściowe referencje domen

Użytkownik dostarczył `data/ttmapp_frames_250_268_domain_review` i wyjaśnił,
że ramki są przybliżonymi granicami wybranych domen, a podobne skupiska mogą
występować poza nimi. [Audyt i zasady użycia](partial-domain-reference-audit.md)
ograniczają ocenę do zaznaczonych obszarów; reszta nie jest podłożem ani
fałszywą detekcją. Kolory są etykietami referencji, nie wyborem typów sieci.

18 par PNG, brak klatki 255; dla wszystkich zgodność rekonstrukcji z MPP
piksel w piksel. Przygotowano 54 robocze wnętrza regionów, maski raw/PNG,
manifest z hashami i galerię; obejrzano wnętrza oraz źródłowe ramki.
Kod przygotowania: `prototype/stmdomains-coverage`, commit `4e7a757`.
Lokalny HTML: `/home/rlew/projekty/NEtCAT-domains/.scratch/partial-domain-reference/index.html`.
Nie scalać kodu prototypu do aplikacji. Dane i duże artefakty są poza Git.

Nie przeliczono klasyfikatorów ani nie oceniono skuteczności pokrycia na tych
referencjach; nie uruchamiano testów aplikacji. Ramki są przybliżone, margines
wnętrz nie jest skalibrowaną tolerancją. Do pełnej walidacji nadal brakuje
negatywnych przykładów podłoża, niepewności i niezależnej próby. Nie zgłoszono
nowych potrzeb wspólnych. Dokumentacja i stan ticketu zostały uzupełnione.

Uzupełnienie po akceptacji zbioru przez użytkownika: dokumentacja dopuszcza
lokalne próby na tej referencji mimo otwartego pytania 04. Commit bazowy audytu:
`c0cc0f4`; commit tej decyzji podany w wiadomości końcowej. Obecna zmiana
obejmuje tylko dokumentację: sprawdzono lokalne linki i `git diff --check`.
Nie uruchamiano ponownie eksperymentów ani testów aplikacji.

---

## Poprzednie przekazanie — specyfikacja szkieletu gotowa do implementacji

Data: 2026-10-19.
Gałąź: `domains/implementation-handoff`, baza `7378c21`.
Worktree: `/tmp/netcat-stmdomains-implementation-handoff`.
Gałąź docelowa: `domains/start`. Claim: `52b5139`.
Commit rozstrzygnięcia podany w wiadomości końcowej. Przeniesienie dokumentacji
przez fast-forward po kontroli gałęzi, HEAD i czystości worktree.

## Wynik

[Przekazanie do implementacji](issues/09-implementation-handoff.md) ma status
`resolved`. Zakończono [pierwszą mapę decyzji](map.md); nie oznacza to wykonania
aplikacji. Kod produkcyjny nadal zawiera startowe okno PyQt6.

Użytkownik potwierdził dwa pozostałe zachowania: pełną kolejność klatek
podczas play, ze spowolnieniem w razie potrzeby, oraz automatyczny kontrast
każdej klatki. Raw/aligned tej samej klatki używają wspólnej skali jasności.

Przygotowano [trzy zadania wykonawcze](implementation/README.md), wszystkie `todo`:

1. Import MolTrack, lokalny model serii, kodek masek i geometria.
2. Natywny podgląd C, otwieranie, zadania w tle i nawigacja.
3. Automatyczne sprawdzenia, pełny TTMAPP oraz odbiór GUI i raport.

Zadania nie są nowymi pytaniami `wayfinder`. Kolejny krok to
[import, model serii i geometria](implementation/01-import-model.md).
Dopiero wykonanie zadań i potwierdzony odbiór programu otwierają zwykły tok
etapu 2. Wcześniejsze decyzje na bezpośrednie polecenia użytkownika są zachowane.

## Kierunek implementacji

Publiczny czytnik `nanotrack.io.mpp_loader.load_mpp_sequence` za lokalnym
adapterem; własne rekordy zachowujące braki i kodowane maski. Jeden układ
geometrii z całej zapisanej rejestracji, obraz/oznaczenia pojedynczej klatki
przygotowywane razem. Nie kopiować pełnego loadera sesji MolTrack ani jego
modeli wymagających pełnych masek lub domyślnego confidence/jakości.

Mały lokalny widok PyQt6 zamiast dziedziczenia całych widgetów NanoTrack/MolTrack.
Odrębne tło paddingu, jednostki px, scene coordinates zgodne z krawędziami
pikseli i bboxów. Kontrast percentylami 2–98 finite próbek oryginału, gamma
wyłącznie podglądu. Cache masek i wyrównania jest ograniczony; nie budować
całego wyrównanego stosu ani wszystkich masek przy otwarciu.

Lokalny kontroler importu i nawigacji odrzuca spóźnione odpowiedzi workerów,
zachowuje poprzednią serię do zatwierdzenia nowej i nie miesza obrazu/oznaczeń.
Wątki GUI i pracy są oddzielone; pauza nie publikuje dodatkowego kroku.
Przyszła analiza dostanie model serii; nie tworzyć teraz ogólnego systemu metod.

## Wykonane sprawdzenia

- Audyt istniejącego okna, czytników, modeli, kodeków, geometrii, widgetów,
  zależności i testów. Nie zmieniano ich kodu.
- Małe próby importów modułów bez danych w `netcat`. Pełne `session_store`
  załadowało 171 modułów `moltrack.analysis`; lekki czytnik MPP nie ładuje ich.
  To kontrola sprzężeń, nie benchmark przyszłej aplikacji.
- Próba starego ViewerWidget w Qt/offscreen: bez ustawienia row-major obraz
  `(2,4)` dostał wymiary 2×4 zamiast 4×2; osie pozostawały nm bez kalibracji;
  NaN w podglądzie były zastępowane medianą. Uzasadnia to lokalny prosty widok.
- Kontrola lokalnych linków, statusów i grafów zależności, kompletności zadań,
  zgodności zakończonej mapy z jej decyzjami oraz `git diff --check` przed commitem.

Nie uruchamiano ponownie dawnych sześciu testów importu, pełnego TTMAPP ani
nowej aplikacji. Prototyp HTML i wcześniejsze testy nie zastępują odbioru
natywnego programu. Przyszłe sprawdzenia opisuje
[zadanie odbioru](implementation/03-acceptance.md); wszystkie pozostają do wykonania.

## Potrzeby integracyjne i środowisko

Produkcja według tego planu: PyQt6 + NumPy + SciPy. Testy: pytest i pytest-qt.
Lokalne `netcat` ma potrzebne zależności. Nie potrzeba modeli, Torch,
QtWebEngine, pyqtgraph ani skimage w produkcyjnej ścieżce szkieletu.

Do integratora: uzupełnienie `requirements/stm-apps.txt` (obecnie tylko PyQt6)
o NumPy/SciPy i objęcie nowych testów właściwym CI. Root requirements/workflow
nie były zmieniane w tej sesji. Dotychczasowy plik nie jest jeszcze podstawą
do deklaracji kompletnej nowej instalacji programu.

Wydzielenie wspólnego lekkiego kodeka masek lub renderera pojedynczej klatki
może być późniejszym refaktorem integracyjnym; lokalna implementacja zgodnego
podzbioru nie musi na to czekać. Stare problemy importu opisane niżej nie są
rozwiązywane przez bezwarunkowe przejęcie pełnego loadera MolTrack.

## Zachowany kontekst poprzednich prac

[Kontrakt importu](issues/01-import-and-geometry.md),
[audyt geometrii](import-geometry-audit.md) i
[definicje wysp/typów/domen](issues/02-order-types-and-domains.md) pozostają aktualne.
Przekazania wcześniejszych zadań są w commitach `3c7c680`, `af7888e`, `ed5da11` i `1a81bc7`.
[Definicje statystyk](issues/06-frame-statistics.md) pozostają aktualne;
ręczne rozstrzyganie konfliktów domen należy do późniejszego UI analizy,
bez rozszerzania podglądu pierwszego etapu.

[Pilotaż metod](method-comparison-pilot.md) nie wybrał algorytmu do aplikacji.
Jego źródła pozostają na `prototype/stmdomains-method-comparison`, commit
`f9ea1d602a8c2bcd1bc5eb410765706d2ae43fca`; nie scalać tej gałęzi do aplikacji.
Lokalny HTML: `/home/rlew/projekty/NEtCAT-domains/.scratch/method-comparison/pilot.html`.
Wynik inspekcji prototypu oraz sześciu dawnych testów importu dotyczy poprzednich
zadań; nie przedstawiamy ich jako sprawdzeń obecnej zmiany.

Zgłoszenia integracyjne pozostają aktualne: dobór czasów do wybranych klatek
MolTrack, walidacja duplikatów i shape masek, zachowanie przy zmienionym mtime
oraz koszt pełnej materializacji masek. Adapter STM Domains może powstać bez
czekania na wspólne poprawki. Dawne zgłoszenie odwracania STP/S94 w NanoTrack
jest poza zakresem importera z jednym MPP. Zmiany tych wspólnych modułów nie blokują lokalnego importera.
Aktualne wymaganie dotyczące środowiska opisano powyżej.

Wybór podglądu jest zakończony: [jeden obraz i pasek miniatur](issues/07-browsing-and-comparison.md),
commit dokumentacji `92e589d`. Źródła jego prototypu pozostają na
`prototype/stmdomains-browsing`, commit `cb51fbf04802620637dd7d10acc19863717de083`;
nie scalać do aplikacji. Lokalny HTML:
`/home/rlew/projekty/NEtCAT-domains/.scratch/browsing-prototype/index.html`.

[Kontrakt zapisu i eksportu](issues/08-save-and-export.md) rozstrzygnięto
w `7378c21`: samowystarczalny `.stmdomains`, opcjonalnie jeden wynik,
odtwarzanie bez przeliczania oraz CSV/PNG. Zapis pozostaje w etapie 2,
także wariant pracy przed analizą. Nie powstał jeszcze serializer.
