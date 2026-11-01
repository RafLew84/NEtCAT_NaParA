# Opis otoczenia i sztuczne granice — wynik 24a

Data: 2026-11-01. [Ticket 24a](issues/24a-graph-context-boundaries.md)
wykonano jako ograniczoną diagnozę, bez treningów. **Usunięto artefakt
podziału pojedynczej sieci, ale nie uzyskano poprawnego rozpoznawania granic
domen.** Wynik nie kwalifikuje poprawki jako naprawy detektora.

[Protokół](graph-context-boundary-protocol.md) ustalono przed obliczeniami;
[manifest](graph-context-boundary-manifest.json) przypina źródła i wyniki.
Galeria lokalna: `.scratch/graph-context-24a/index.html`. Porównuje ten sam
model i solver przed zmianą oraz po niej, z przełącznikiem przed/po odmowach.

## Zakres i pytanie

W 24 jednorodna sieć była sztucznie dzielona wzdłuż prawego i dolnego brzegu
dostępnego pola. Zamknięte okno 72 zawierało 49 węzłów dla 100 centrów,
42 dla 20 oraz 36 dla jednego; wzór był ten sam, ale kontekst grafu inny.
Sprawdziliśmy konwencję półotwartą `[-36,36)` oraz wyłączenie agregacji.

Użyto 93 **znanych kontroli 24**, czyli 31 rodzin × 3 realizacje. Nie jest
to nowy test held-out. Macierz: 19 reprezentacji × FH k=4/MWS × 93 kontrole
= **3534 wyniki**, w tym 1302 oryginalne wyniki bazowe. Wagi to trzy
transferowe modele SCE+scale z 24 i ich własne inicjalizacje. Nie oceniano
ponownie TTMAPP, transdukcji ani SCE-only.

| Tryb | Zmiana |
| --- | --- |
| `closed72` | Dokładne zapisane cechy i predykcje 24 |
| `halfopen72` | Jednolita konwencja brzegu ego; promień krawędzi pozostaje przypięty z 24 |
| `root_only` | Tylko 57 cech centrum i te same warstwy z pętlą własną; ablacja agregacji |
| `root57` | Klasyczna geometria z 24, wspólny punkt odniesienia |

**0 fitów, 0 kroków optymalizacji, 0 ponownych dopasowań adapterów.** Wagi,
PCA, kwantyle, katalog, graf podziału i bramka geometryczna pozostają
zamrożone. Każdy wariant zachowuje te same 8350 dostępnych centrów S24
spośród 19 629 oznaczeń. Odmowy pozostają w mianownikach. Wycięcie sąsiada
z brzegu ego nie usuwa ocenianego centrum.

## Wynik według ustalonych kryteriów

**A — pojedyncza sieć: zaliczone.** `halfopen72` daje dokładnie jedną domenę
i **121/121 przypisań**, przed i po odmowach, we wszystkich trzech ziarnach
modelu i realizacjach kontroli, zarówno dla wag wyuczonych, jak początkowych,
z FH i MWS. To samo uzyskuje ablacja `root_only`. Nie odrzucono 21 centrów
brzegowych. Stary FH nie przechodził A; stary MWS i geometria już je spełniały.
Poprawa także bez uczenia wskazuje na problem budowy kontekstu.

**B — rzeczywiste granice: niezaliczone we wszystkich grupach.** Żaden tryb
nie spełnia wspólnie wymagań pokrycia ≥50%, każdej części ≥30%, błędu scaleń
≤2%, podziałów ≤10% i F1 granicy ≥0,70, przed i po odmowach. Dotyczy to
dwóch orientacji, różnicy 8°, różnego rozstawu i granicy przesunięcia.

Poniżej F1 granicy **po odmowach, FH k=4**. Mediana po trzech ziarnach modelu;
wartość każdego ziarna sumuje liczniki trzech realizacji. Mediany służą opisowi,
natomiast kryteria sprawdzają każdy przypadek i każde ziarno osobno.

| Reprezentacja | Dwie orientacje | Różnica 8° | Różny rozstaw | Przesunięcie |
| --- | ---: | ---: | ---: | ---: |
| Geometria root57 | 0,161 | 0,272 | 0,000 | 0,452 |
| Wyuczone, closed72 | 0,095 | 0,033 | 0,000 | 0,327 |
| Wyuczone, halfopen72 | 0,130 | 0,098 | 0,000 | 0,399 |
| Wyuczone, root_only | 0,000 | 0,000 | 0,000 | 0,452 |
| Początkowe, closed72 | 0,182 | 0,210 | 0,000 | 0,330 |
| Początkowe, halfopen72 | 0,214 | 0,000 | 0,000 | 0,399 |
| Początkowe, root_only | 0,000 | 0,000 | 0,000 | 0,452 |

Przy czystym przesunięciu błąd podziałów wyuczonego FH spada z mediany
73,7% do 57,1%; bez agregacji do 46,0%. To częściowy zysk, daleki od 10%.
W MWS końcowy F1 pierwszych trzech rodzin wynosi 0 we wszystkich trybach.
Dla fazy mediana wyuczonego MWS zmienia się z 0,459 na 0,452. Wyniki przed
odmowami również nie spełniają B, więc problem nie leży wyłącznie w bramce.

**C — brak regresji: niezaliczone dla zmienionych wyuczonych modeli**,
zarówno FH, jak MWS. Przykład: F1 orientacji 8° dla ziarna 20261103 maleje
z 0,255 do 0,162 po zmianie na `halfopen72`; dla 20261101 z 0,033 do 0.
Tolerancja wynosiła 0,02. Wśród zmienionych modeli początkowych tylko
`halfopen72` z MWS spełnia C, nadal bez B. Nie wybrano korzystnego ziarna.

## Kontrole obciążające i interpretacja

Granica przesunięcia z błędem centrów nie zyskuje na `halfopen72`.
Wyuczony FH ma nadal błędy scaleń 84,5%, 100% i 62,1% dla kolejnych ziaren,
a MWS po odmowach 0/271 przypisań. `root_only` częściowo zmienia ten wynik,
lecz także nie daje wiarygodnych domen. Niezależne rzędy otrzymują 300/300
fałszywych przypisań we wszystkich trybach, obu stanach wag i solverach.
Nie ma stałej poprawy przy duplikatach; dla ziarna 20261103 wyuczony FH
zwiększa błąd podziałów z 30,5% do 52,3% po zmianie konwencji brzegu.

W `halfopen72` zmieniamy tylko punkty dokładnie na górnej granicy okna.
To wyjaśnia skuteczność na idealnej regularnej sieci i ograniczoną wartość
dla zaburzonych pozycji. Audyt potwierdza zmianę węzłów w 5896/8350 ego,
w pojedynczej sieci w 120/121 na realizację. W fazie z jitterem nie zmienia
się żadne z 301 ego S24 (271 centrów należy do ocenianych regionów);
wszystkie 36 par wyników ma identyczne etykiety przed i po odmowach.
Ablacja bez przekazywania informacji między węzłami
nie jest poprawionym GNN. Geometria i początkowe wagi osiągają część tych
samych wyników; nie wykazano tu przewagi uczenia.

Certyfikat dwóch kroków agregacji i opisów R24 jest diagnostyką kompletności
względem nieuciętego sąsiedztwa, przy przypiętym promieniu. Nie filtruje S24.
Spełnia go 339/8350 centrów w closed72 i tyle samo w halfopen72, wobec
8350/8350 w ablacji. Dla pojedynczej sieci odpowiednio 0/363 i 363/363.
Ograniczone ego było definicją modelu 24; ten audyt nie stwierdza wycieku danych.
Zmiana konwencji brzegu nie rozwiązuje całej kwestii zasięgu zależności grafu.

Puste grafy szumu/pasków nie potwierdzają rozpoznawania negatywnych obrazów.
Przypisania centrów nie są wykrywalnością molekuł ani pomiarem powierzchni.
Adaptery pochodzą ze starego wejścia; diagnoza nie ocenia modelu wytrenowanego
od początku z nową konwencją. Nie przenosimy tego wyniku na TTMAPP ani inne
molekuły/podłoża. Wyniki 24 pozostają nienaruszone.

## Weryfikacja i odtworzenie

- Zamrożono kod/protokół/plan przed predykcjami; predykcje przed ponownym
  otwarciem referencji. Ewaluator zweryfikował 9703 lokalne pliki zamrożenia.
- Audyt techniczny: 3534 archiwa, 745 902 wiersze przypisań, 8350 centrów
  w każdym trybie, 651 identycznych archiwów cech i 1302 identyczne archiwa
  bazowych predykcji, 19 niezmienionych adapterów.
- Dziewięć kontroli mechaniki obejmuje brzegi, permutację, translację,
  padding i limit węzłów. Replay CPU starych cech mieści się w 1e-5;
  największa różnica bezwzględna 1,67e-6. Bazowych etykiet nie zastąpiono.
- Niezależny audyt odtworzył 3534 rekordy, 7068 etapów metryk i liczników
  krawędzi przez granicę z 0/1/2 przypisanymi końcami, 14 136 etapów porównań,
  1178 agregatów i 14 kryteriów. Wszystkie 1302 bazowe rekordy metryk są
  zgodne z 24. Zachowano także porównania na wspólnych przypisanych ID.
- Galeria: 40 sprawdzeń, 26 par konfiguracji, pięć scenariuszy, zero błędów JS.
  Obejrzano trzy zrzuty: pojedyncza sieć, faza z jitterem i ablacja centrum.
- Końcowo potwierdzono niezmienność 21 883 plików zamrożenia i źródeł,
  kompilację siedmiu modułów, 409 lokalnych odnośników, graf 28 ticketów
  bez cykli oraz `git diff --check`.

Obliczenia wykonano na CPU, bez instalacji i GPU. Predykcje zajęły 60,79 s CPU,
audyt techniczny 23,79 s, ocena 15,12 s. Pełna ewidencja zmierzonych etapów
i szczytów RSS jest w manifeście: łącznie **114,60 s CPU**, szczyt **1,57 GiB**;
limit to 1800 s CPU i 4 GiB na proces.
Koszt edycji i krótkiego nieudanego sprawdzenia zabawkowego przed zamrożeniem
nie był mierzony jako CPU; nie uruchamiał predykcji kandydatów. Pomiar procesu
Qt nie obejmuje osobno zasobów jego procesów renderujących.

Źródła: `stmdomains/experiments/training/graph_context/`,
[instrukcja odtworzenia](../../stmdomains/experiments/training/graph_context/README.md).
Podjęcie `959fde3`, implementacja i protokół `ee73c83`; prototyp zachowuje
gałąź `prototype/stmdomains-graph-context-boundaries`. Artefakty, HTML
i modele są lokalne poza Git. Nie wdrażano metody do aplikacji.

## Rozstrzygnięcie

24a jest `resolved` jako wykonana próba: **A tak, B nie; C nie dla wyuczonych
wariantów**. Potwierdzono i usunięto konkretny artefakt wycinania kontekstu,
bez uzyskania poprawnego detektora. Odbiór 13 pozostaje otwarty. Dalszy trening,
25/26 i przygotowanie dodatkowych MPP/STP nie zostały wybrane w tej próbie.
