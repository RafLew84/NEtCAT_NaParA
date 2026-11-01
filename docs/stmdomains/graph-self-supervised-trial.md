# Uczenie grafu otoczeń molekuł — próba 24

Data: **2026-11-01**. Realizacja [ticketu 24](issues/24-graph-self-supervised-domains.md)
na bezpośrednie polecenie użytkownika po zamknięciu pilota 23.
[Protokół](graph-self-supervised-protocol.md),
[odtworzenie obliczeń](../../stmdomains/experiments/training/graph_ssl/README.md),
[manifest dowodów](graph-self-supervised-manifest.json).
Lokalna galeria: `.scratch/graph-ssl-24/index.html`.
Źródła prototypu zachowuje gałąź `prototype/stmdomains-graph-self-supervised`;
implementację i protokół zapisano w `f53611b`.

## Wynik

**Nie wykazano użytecznej przewagi uczenia grafu nad klasyczną geometrią
i własną inicjalizacją.** Wszystkie dziewięć treningów działa poprawnie,
ale żadna z czterech głównych konfiguracji reżim × podział ani dwóch
diagnostycznych konfiguracji samego SCE nie spełnia kryteriów kontynuacji.
Są niezerowe przypisania; ich liczba nie oznacza poprawnego wykrycia domen.
FH często scala różne regiony, a MWS traci centra lub nadmiernie dzieli sieć.
Nie przyjęto detektora ani fizycznego katalogu typów.

W transferze główny model z FH przypisuje **178–183/204 (87,3–89,7%)**
ocenialnych centrów, lecz scala **100% ocenianych par różnych referencji**.
MWS po odmowach daje **0/204**. W transdukcji główny FH zachowuje
1070–1093/1175 centrów, ale scala 73,0–87,4% ocenianych par różnych regionów.
MWS zachowuje 517–632/1175, mniej od klasycznej geometrii: 815/1175.

Próbę kończymy jako wykonany eksperyment. Wynik trafia do otwartego odbioru
13; 25/26 i przygotowanie dodatkowych MPP/STP pozostają niewybrane/odłożone.
Nie otwieramy ponownie 19 ani nie zmieniamy wyników 21/21a/22/23.

## Co zmieniło się wobec 21/22

Wejściem są **rzeczywiste centra zapisanych oznaczeń molekuł**, z pełnym
otoczeniem 72 × 72 px. Punkty w galerii odpowiadają tym oznaczeniom;
kliknięcie pokazuje wykorzystane okno. Nie są regularną siatką wycinków.
Nie wykonujemy nowej detekcji molekuł ani nie potwierdzamy poprawności
każdego wejściowego oznaczenia.

Geometria 57 cech opisuje kierunki i odległości sąsiadów. Mały encoder
grafowy odtwarza zamaskowane cechy. Główny cel to SCE + MSE odległości,
a samo SCE jest kontrolą diagnostyczną. Własne wagi początkowe, klasyczne
cechy i model po uczeniu korzystają z tej samej procedury dopasowania adaptera,
podziału FH/MWS i bramki. Parametry adaptera dopasowuje się osobno do każdej
reprezentacji, na dozwolonym zbiorze treningowym.
Implementacja jest inspirowana [GraphMAE](https://arxiv.org/abs/2205.10803),
z własną agregacją i wejściem geometrycznym; nie reprodukuje publikacji.

Bramka porządku pochodzi z powtarzalności geometrii 15, z minimum ośmiu
spójnych centrów. Zastępuje obrazową bramkę poprzednich prób. Osobno
odtworzono pełną procedurę komórki 15 na nowym ograniczonym wsparciu.
**Wzrost przypisań względem 0/174 z 21/22 nie mierzy korzyści uczenia**:
zmieniły się wejście, wsparcie, bramka i mianowniki. Wnioski o encoderze
opierają się wyłącznie na porównaniach wewnątrz 24.

## Dane i zakres oceny

| Zakres | Liczba |
| --- | ---: |
| Klatki TTMAPP / wszystkie zapisane centra | 24 / 6730 |
| Centra z pełnym wsparciem w całej serii | 3795 |
| Transfer: train / validation / test | 76 / 27 / 831 |
| Centra z częściową referencją: test / cała seria | 204 / 1175 |
| Kontrole syntetyczne | 93 = 31 rodzin × 3 realizacje |
| Wszystkie centra syntetyczne / z pełnym wsparciem | 19629 / 8350 |

Train transferu pochodzi tylko z klatek 1 (66 otoczeń) i 50 (10).
Klatka 100 nie mieści pełnego otoczenia w swoim dozwolonym pasie.
Validation ma 19/8 otoczeń klatek 150/200; zachowano bloki i bufory 20.
Najpierw wycinamy centra do otoczenia, potem obliczamy jego cechy i warstwy
grafowe. Padding nie staje się obserwacją. Test ma osobny graf, bez tras
przez pozostałą część klatki. Maksymalne dostępne otoczenie ma 67 węzłów
przy limicie 128. Kontrole i referencje nie dopasowują wag, PCA ani progów.

To jedna skorelowana akwizycja, mały zbiór treningowy i niepewna rejestracja.
Jednostką TTMAPP pozostaje px, bez deklarowania kalibracji nm. Liczba
otoczeń nie jest liczbą niezależnych przykładów. Referencje obejmują tylko
wybrane dodatnie wnętrza; nie mierzą pełnego recall, podłoża ani powierzchni.
Nie sprawdzono przenoszenia na inne molekuły, podłoża lub akwizycje.

## TTMAPP: przypisania i błędy

W tabeli wyniki **po odmowach**. Zakresy obejmują wszystkie trzy ziarna;
każda kolumna ma własny zakres, bez składania korzystnych wartości w jeden
fikcyjny wynik. Błędy par dotyczą tylko par z obydwoma przypisanymi końcami.
Puste porównanie ma brak miary, a nie błąd równy zero.

| Reżim | Cechy / podział | Przypisania | Błędne scalenia | Błędne podziały |
| --- | --- | ---: | ---: | ---: |
| Transfer | Geometria / FH | 176/204 | 100% | 0% |
| Transfer | Graf uczony / FH | 178–183/204 | 100% | 0% |
| Transfer | Geometria / MWS | 0/204 | — | — |
| Transfer | Graf uczony / MWS | 0/204 | — | — |
| Transdukcja | Geometria / FH | 1105/1175 | 87,2% | 0% |
| Transdukcja | Graf uczony / FH | 1070–1093/1175 | 73,0–87,4% | 1,7–2,5% |
| Transdukcja | Geometria / MWS | 815/1175 | 0% | 15,7% |
| Transdukcja | Graf uczony / MWS | 517–632/1175 | 1,7–4,6% | 16,0–30,8% |

Model bez uczenia z FH zachowuje 183–188/204 w transferze i 1097–1117/1175
w transdukcji; bez uczenia z MWS odpowiednio 0/204 i 661–758/1175.
Główny model nie spełnia warunku przewagi nad własną inicjalizacją.
Transdukcyjny MWS uczony zachowuje jednak część wszystkich trzech grup
referencji, podczas gdy geometryczny MWS odrzuca całą drugą grupę i niemal
całą trzecią. Jest to kompromis kosztem mniejszej liczby przypisań i większych
błędów, nie spełnienie kryteriów kontynuacji.

W transferze główny FH scala odpowiednio 36/36, 42/42 i 36/36 przypisanych
par między różnymi regionami; klasyczny FH 24/24. Zakres jest mały, więc nie przenosimy
tego odsetka na całe STM. Pełny dostępny test ma 201 centrów pierwszej grupy,
3 drugiej i żadnego trzeciej. W transdukcji mianowniki grup to 1049, 8 i 118.

Przed odmowami wszystkie podstawowe reprezentacje przypisują cały ocenialny
zakres. Dla transferu FH mediany błędów scalenia/podziału wynoszą
57,8%/17,9% dla geometrii, 93,3%/7,6% bez uczenia i 86,7%/8,6% po uczeniu.
Transferowy MWS dzieli medianowo około 99% par jednego regionu; późniejsze
minimum ośmiu połączonych centrów usuwa jego wynik. Problem występuje zatem
już przed bramką.

Przy wspólnym pokryciu główny FH w transferze poprawia medianę średniego
błędu względem własnej inicjalizacji przed odmowami o 2,48 pp, poniżej
wymaganych 5 pp; wobec geometrii pogarsza ją o 10,15 pp. Po odmowach
transdukcyjny FH ma medianę poprawy 3,61 pp wobec geometrii, lecz pogorszenie
3,12 pp wobec własnej inicjalizacji. Żadna główna konfiguracja nie uzyskuje
wymaganej przewagi na TTMAPP ani na całym zestawie kontroli, przed lub po
odmowach. Pełne wyniki każdego ziarna zawierają lokalne `report/ttmapp.csv`
i `evaluation/pooled-comparisons.json`.

### Pełna procedura 15

Dostosowana procedura komórki przypisuje 165/204 w transferze i 926/1175
w transdukcji, wyłącznie pierwszą grupę referencji. Jej błąd scaleń ma
wartość **null**: nie zachowała żadnej ocenialnej pary różnych regionów.
Nie przedstawiamy tego jako dowodu poprawnego oddzielania domen.
W galerii obie kolumny tej procedury pokazują gotowy wynik, bo nie ma
osobnej predykcji przed odmowami. Historyczne 70,7% z 15 dotyczy innego
wsparcia; nie jest dodatkowym wierszem wspólnego rankingu 24.

Procedura 15 zalicza wszystkie trzy realizacje każdej z kontroli jitteru
0,36 px, jitteru 0,72 px i duplikatów — łącznie 9/9 w każdym reżimie.
Nie przenosi się to na granice: przy granicy przesunięcia z jitterem
przypisuje 258/271 centrów i scala 100% ocenianych par różnych części.
Na ujemnej kontroli niezależnych rzędów błędnie przyjmuje 230/300 centrów.

## Kontrole i zależność od oznaczeń

Poniżej liczba zaliczonych ocen głównego modelu po odmowach, na dziewięć
połączeń trzech ziaren modelu i trzech realizacji kontroli. To nadal tylko
trzy realizacje danych. Wymagania obejmują również błędy i granicę,
nie samo zachowanie centrów.

| Kontrola | Transfer FH | Transfer MWS | Transdukcja FH | Transdukcja MWS |
| --- | ---: | ---: | ---: | ---: |
| Jedna pełna sieć | 0/9 | 9/9 | 0/9 | 9/9 |
| Dwie orientacje | 0/9 | 0/9 | 0/9 | 0/9 |
| Różnica orientacji 8° | 0/9 | 0/9 | 0/9 | 0/9 |
| Różny rozstaw | 0/9 | 0/9 | 0/9 | 3/9 |
| Granica przesunięcia | 0/9 | 0/9 | 0/9 | 0/9 |
| Granica przesunięcia + jitter 0,72 px | 0/9 | 0/9 | 0/9 | 0/9 |
| Niezależne rzędy | 0/9 | 0/9 | 0/9 | 0/9 |
| Brak 10% centrów | 6/9 | 0/9 | 3/9 | 5/9 |
| Brak 30% centrów | 2/9 | 0/9 | 7/9 | 0/9 |
| Brak 50% centrów | 3/9 | 0/9 | 3/9 | 0/9 |
| Brak centrów w pasie | 0/9 | 0/9 | 0/9 | 0/9 |
| Lokalny brak centrów | 0/9 | 9/9 | 0/9 | 9/9 |
| Jitter 0,36 px | 7/9 | 0/9 | 8/9 | 0/9 |
| Jitter 0,72 px | 5/9 | 0/9 | 6/9 | 0/9 |
| Duplikaty 10% oznaczeń | 3/9 | 0/9 | 4/9 | 3/9 |

Na samej granicy przesunięcia transdukcyjny FH poprawia medianę średniego
błędu wobec własnej inicjalizacji o 14,00 pp po odmowach. Nadal nie zalicza
tej kontroli: medianowe F1 wynosi 0,452, a błąd podziału około 46%.
Na pasie nieuporządkowania ma częściowy zysk 6,91 pp względem geometrii,
przy medianie utraty pokrycia 5,64 pp. Te korzyści nie obejmują całego zestawu
lub TTMAPP. Nie pomijamy ich, ale nie wybieramy na ich podstawie modelu.

Dodanie jitteru do granicy przesunięcia silnie pogarsza FH: w transdukcji
scala 73,0–100% przypisanych par różnych części; F1 wynosi 0–0,204.
MWS daje F1 0,036–0,154. Niezależne rzędy otrzymują 100% przypisań głównego
modelu w obu reżimach i podziałach, mimo że powinny pozostać negatywem.
Żadna uczona konfiguracja nie zalicza pełnej kontroli stabilności ziaren.

Kontrole prawdziwej przerwy materiału i brakujących oznaczeń w pasie mają
**identyczne wejście i identyczne wyniki geometryczne** w każdym wariancie
i każdej z trzech realizacji. Graf bez obrazu nie może rozstrzygnąć przyczyny
tej przerwy. Kontrole szumu i pasków mają zero centrów: brak domen potwierdza
tylko obsługę pustego wejścia, nie rozpoznawanie negatywnych obrazów.

### Dlaczego FH dzieli nawet pełną sieć

Diagnoza zapisanych otoczeń wyjaśnia około 29% błędnych podziałów `single`.
Ze 121 dostępnych centrów 100 ma pełne otoczenie 7 × 7 węzłów, a 21 przy
brzegach pola ma 6 × 7 lub 6 × 6. Generator nie tworzy centrów
na współrzędnej 192, choć mierzone okno może się tam kończyć. Wszystkie
100 pełnych kontekstów i ich embeddingi są bitowo identyczne wewnątrz każdego
wariantu. FH oddziela je od otoczeń brzegowych; samo rozłączenie tych grup
daje 28,93% błędnych par jednej sieci.

Efekt występuje także przed treningiem. Klasyczne cechy samego korzenia
są identyczne we wszystkich 121 miejscach i nie tworzą tego podziału.
To wykazana wrażliwość grafowego kontekstu na skończone pole, nie błąd
arytmetyki ani dowód fizycznej granicy. Diagnozę wykonano na zapisanych
wejściach i cechach, bez nowych fitów, progów lub korekty predykcji.

## Trening, skala i koszt

Model ma **27 154 parametry**, bez dodatkowych bibliotek DGL/PyG lub wag
zewnętrznych. Wykonano 9/9 fitów i 17 400 kroków optymalizacji, bez pominiętych
kroków i restartów. Transfer: sześć razy 2000 kroków. Główny cel wybrał
1700/1800/1900, samo SCE 400/600/1000; transdukcja dostała ustaloną medianę
1800 kroków dla każdego z trzech ziaren. Wybór korzystał wyłącznie ze stałych
masek walidacyjnych, bez referencji domen.

Dodany składnik skali działa zgodnie z przeznaczeniem: MSE odległości na
walidacji ma medianę **0,0427**, wobec **0,1889** przy samym SCE, czyli spadek
około 77,4%. Mediana SCE jest odpowiednio 0,0566 i 0,0468. Sama poprawa
odtwarzania odległości nie daje poprawnych granic. Samo SCE z FH zachowuje
181–188/204 centrów transferu, również ze 100% scaleń ocenianych par różnych
regionów; z MWS 0/204. Pięć zerowych celów walidacyjnych pominięto w SCE
zgodnie z planem; oceniono 159 niezerowych zamaskowanych węzłów i 502
dostępne kanały odległości.

Diagnostyczny transfer z samym SCE i FH ma też korzyść cząstkową na pasie
nieuporządkowania: po odmowach mediana poprawy średniego błędu względem
geometrii wynosi 6,31 pp, przy utracie coverage 0,30 pp. Nie daje to przewagi
na całym zestawie kontroli ani na TTMAPP.

Treningi na RTX 5090 zajęły łącznie **122,86 s**. Maksimum tensorów GPU
wyniosło 98,69 MiB, a RSS procesu około 1,96 GiB. 183 pliki checkpointów
zajmują 131 517 871 B. Nie ma uzasadnienia sprzętowego dla przejścia na
większą kartę w tej próbie. Osobny audyt wznowienia zużył 12 kroków
technicznych; jego wag nie użyto do predykcji.

Geometria, encoding i podział zajęły odpowiednio 56,83 / 40,18 / 90,91 s CPU.
Pozostałe zmierzone etapy i audyty mają osobne raporty zasobów w manifeście;
pozostały daleko poniżej budżetu 7200 s. **CPU/RSS pierwszego przygotowania
nie były mierzone**. Osobny identyczny replay kosztował 9,90 s CPU;
nie zastępuje pomiaru oryginalnego wykonania. Kosztów kopii raportów nie
liczymy ponownie. To zestawienie zmierzonych etapów, nie kompletny pomiar
czasu całej interaktywnej sesji.

## Weryfikacja, galeria i artefakty

- Przypięto 18 źródeł numerycznych i protokół przed fitami; przed oceną
  zamrożono 12 131 plików lokalnych i 137 zewnętrznych. Pierwsza próba
  uruchomienia wykryła błąd typu ścieżki w sprawdzaniu hashów, przed
  utworzeniem runu i przed jakąkolwiek optymalizacją. Zachowano poprzedni
  plan i poprawkę techniczną; nie zmieniono modelu lub parametrów.
- Przygotowanie wszystkich 117 próbek odtworzono dokładnie. Sprawdzono
  izolację kontekstu i pasów, permutację, translację, resampling i duplikaty.
  Pełna historyczna geometria zgadza się z 15 na 823 centrach; ograniczone
  otoczenie nie odczytuje sąsiadów spoza swojego wsparcia.
- Audyt potwierdził 174 okresowe checkpointy, parowanie 6000 batchy obu
  celów i własne inicjalizacje. Wznowienie zachowało bitowo wagi, optimizer,
  scheduler, RNG, sampler i przebieg strat.
- Zapisano 4212 pełnych wyników i 504 dodatkowe archiwa testowe. Audyt
  sprawdził 1 090 254 wiersze JSON/NPZ, 17 adapterów z właściwymi train ID,
  brak przypisań bez wsparcia i poza testem oraz 258 odtworzeń procedury 15.
- Niezależny audyt odtworzył wszystkie 4212 rekordów, 8424 etapy przypisań
  i par, 6696 ocen granic oraz 792 warunki przewagi. Mianowniki, porównania
  przy wspólnym pokryciu i brak kwalifikacji zgadzają się z raportem.
- Galeria obejmuje 117 obrazów, 19 wariantów, sześć scenariuszy, oba podziały,
  osobny test i podgląd otoczenia. QtWebEngine: **78 interakcji, zero błędów
  JavaScript, pięć zrzutów obejrzanych wizualnie**. Galeria czyta zapisane
  wyniki i nie uruchamia treningu lub predykcji.

Katalog HDBSCAN dopasowano na dozwolonym train, bez zadanej liczby klas.
Jego ID oznaczają wyłącznie podobieństwo deskryptorów; pola fizycznego typu,
orientacji i materiału pozostają nieokreślone. Nie zamieniamy otoczki centrów
w pomiar powierzchni. Duże dane, modele, HTML i pełne CSV pozostają lokalne
poza Git. Zmiany dotyczą tylko Domains; aplikacja produkcyjna, wspólne moduły
i inne worktree pozostają poza zakresem próby.
