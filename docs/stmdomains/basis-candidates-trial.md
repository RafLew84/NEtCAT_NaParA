# Kandydaci baz i nowe powtórzenia — issue 19

Data: **2026-10-31**. Kontynuacja [diagnostyki jakości](fit-quality-diagnosis.md),
wykonana na bezpośrednie polecenie użytkownika.

**Dzielniki kandydatów naprawiają konkretny błąd wyboru wielokrotności
okresu: 9/9 celowanych kontroli odzyskuje prawidłową sieć i bezbłędnie
przewiduje nowe rzędy. Nie uzyskano jednak ogólnej poprawy na TTMAPP.**
Przy wspólnym progu liczba potwierdzonych otoczeń TTMAPP pozostaje taka sama
jak dla pojedynczej bazy. Próba zakończona; **19 pozostaje `claimed`, do
omówienia, 20 odłożone**. Nie przyjęto metody do programu.

Podgląd: `/home/rlew/projekty/NEtCAT-domains/.scratch/basis-candidates/index.html`.
Wyświetla 42 obrazy, trzy obszary danych, wszystkie dopasowane kandydatury,
wybór na osobnym pierścieniu oraz końcowe wyniki. Ręczny podgląd kandydata
nie zmienia wyboru ani oceny. Kwadraty oznaczają miejsca oceny otoczeń,
kółka — dostarczone centra molekuł. Nie są to oznaczenia wykrytych domen.
[Manifest](basis-candidates-manifest.json), CSV i wykres PNG/PDF zachowują
parametry, identyfikację danych i wyniki.

## Protokół bez wyboru według końcowego wyniku

**97 obrazów**: 19 unikalnych wcześniejszych geometrii negatywnych,
24 pełne klatki TTMAPP i 54 nowe syntetyki (18 przypadków × ziarna
10101–10103). 15152 otoczenia, 512272 dopasowania kandydatów, trzy
warianty wyboru i dwie końcowe miary — **90912 decyzji**. 18 klatek
TTMAPP ma częściowe referencje, sześć nie ma referencji.

Środki otoczeń co 24 px, od `(12,12)`, promienie **48 i 64 px**. Każde
otoczenie ma trzy rozłączne części:

| Część | Zasięg | Zastosowanie |
| --- | --- | --- |
| Dopasowanie | do .55R | Propozycje baz i dopasowanie ich parametrów |
| Wybór | .55R–.75R | Wybór najlepiej przewidującego kandydata |
| Końcowa ocena | .75R–R | Przewidywania nieużyte do dopasowania i wyboru |

Minimum osiem centrów do dopasowania i sześć do wyboru. Po wyborze nie
dopasowujemy modelu ponownie. Nie przełączamy go na inny dlatego, że
końcowy test jest niedostępny lub nieudany. Ani liczba domen, ani ramki
TTMAPP nie uczestniczą w tych operacjach.

Porównano pule:

- `single`: jedna wcześniejsza propozycja z histogramu przesunięć 6–24 px;
- `peaks`: ta propozycja oraz do sześciu odrębnych baz z pików histogramu
  6–30 px; dziesięć pików, pary o sinusie kąta ≥.35;
- `divisors`: powyższe oraz dzielenie wektorów przez `(2,1)`, `(1,2)`,
  `(2,2)`, `(3,1)`, `(1,3)`, `(3,3)`, jeśli najkrótszy zredukowany
  wektor kandydata nadal ma ≥4 px. Równoważne bazy deduplikujemy.

Wszystkie warianty stosują pięć iteracji Huber z tolerancją 2 px i limitem
korekty afinicznej 15%, wyłącznie na części dopasowania. Kanoniczna redukcja
po dopasowaniu ustala osie końcowej oceny. Rozszerzenie `peaks` zmienia
również zakres przesunięć, a `divisors` zakres możliwych krótkich okresów;
nie przypisujemy całej różnicy samej liczbie kandydatów.

Ocena dopasowania **F** wykorzystuje optymalne przypisanie jeden-do-jednego
między centrami a przewidywanymi węzłami, z wagą `exp(−d²/8)`:

`F = 2 × suma wag dopasowanych par / (liczba centrów + liczba węzłów)`.

Liczą się wszystkie przewidywane węzły danego obszaru w zmierzonym polu,
także bez pobliskich oznaczeń. To ogranicza pozorne dopasowanie nadmiernie
gęstej sieci. Jednocześnie karze prawdziwą sieć za braki oznaczeń: przy
idealnym położeniu i 70% obserwowanych węzłów oczekiwany wynik to około
.824, przy 40% — .571. Niska F nie oznacza automatycznie fizycznego nieporządku.

Kandydata wybiera najwyższa F na pierścieniu wyboru. Końcowo zapisujemy:

1. F na całym zewnętrznym pierścieniu, przy ≥6 centrach i ≥6 węzłach.
2. Mniejszą F z dwóch rozłącznych sektorów **nowych rzędów**. Poziom indeksu
   jest nowy tylko wtedy, gdy jego cała idealna linia nie przecina dysku
   `.75R` użytego do dopasowania i wyboru. Brakujące oznaczenia w tym dysku
   nie mogą pozorować nowego rzędu. Sektory wyznacza większa prostopadła
   odległość poziomu od środka otoczenia. W każdej osi potrzeba co najmniej
   dwóch nowych poziomów z ≥2 centrami na poziom, ≥4 centrów i ≥4 węzłów.

Niewystarczające nowe rzędy dają **brak oceny**, nie potwierdzenie lub
odrzucenie domeny. Dwa poziomy obu osi są minimalnym sprawdzianem
przewidywania; nie gwarantują pełnej statystycznej niezależności.

Progi q99 ustalono na wcześniejszych negatywach osobno dla promienia,
puli i miary, przed nowymi syntetykami. Wszystkie 12 komórek miały ≥100
dostępnych okien z ≥3 geometrii. Są to empiryczne progi skorelowanych
otoczeń, bez gwarancji p-value lub poziomu fałszywych odkryć.

W ocenie pokazujemy również **wspólny próg** — maksimum trzech już
zamrożonych progów danej miary/promienia. To diagnostyka tych samych
wyników, która oddziela zmianę modelu od zmiany kalibracji; nie wpływa na
wybór kandydata. Dla obu kierunków przy R64 własne progi wynoszą
.73135 / .72709 / .64667. Przy R48: .79063 / .81512 / .81501.

## Odzyskanie okresu zamiast jego wielokrotności

Celowane kontrole mają w rdzeniu o promieniu 36 px brak co drugiej kolumny,
co drugiego rzędu albo co drugiej kolumny po obrocie 27°. Poza rdzeniem
oznaczenia są kompletne. Przy środku `(84,84)` i R64 pierścień wyboru
sięga poza rdzeń, więc zawiera informację rozróżniającą okresy.

| Wynik dziewięciu celowanych otoczeń R64 | `single` | `peaks` | `divisors` |
| --- | ---: | ---: | ---: |
| Dostępny wybrany model | 7 | 9 | 9 |
| Prawidłowy okres | 0 | 0 | **9** |
| Oba kierunki ponad wspólnym progiem | 0 | 0 | **9** |

`peaks` wybiera komórkę o dwukrotnie większym polu, z F całego testu
.63–.70. `divisors` odzyskuje rzeczywistą komórkę; F całego pierścienia
i nowych rzędów obu osi wynosi **1 we wszystkich dziewięciu przypadkach**.
Prawdziwy model znany z generatora służył tylko późniejszej ocenie.
Podwojone pole komórki nie oznacza podwojenia obu okresów.

Przy R48 żadna pula nie odzyskuje okresu w tych dziewięciu otoczeniach.
Cały pierścień wyboru leży jeszcze w niepełnym rdzeniu — dane użyte do
wyboru nie rozróżniają sieci od regularnego braku oznaczeń. To granica
dostępnej informacji, nie uzasadnienie wyboru według końcowego testu.

Pojedynczy błędny model `peaks` w kontroli obróconej przekracza swój
własny próg obu kierunków (.727273 wobec .727095), choć nadal ma podwojone
pole komórki; odpada przy wspólnym progu. Samo przejście sprawdzianu nie
gwarantuje, że wybrano najmniejszy rzeczywisty okres.

Szerszy przekrój nowych kontroli, R64, na **192 otoczenia** każdego przypadku:

| Kontrola | Zgodny okres: single / peaks / divisors | Oba kierunki ponad wspólnym progiem |
| --- | --- | --- |
| Czysta sieć 12 px | 192 / 192 / 192 | 58 / 58 / 58 |
| Błąd pozycji 1.2 px | 177 / 189 / 191 | 1 / 1 / 1 |
| Brak 30% oznaczeń | 171 / 174 / 174 | 39 / 40 / 40 |
| Błąd 1.2 px + brak 30% | 137 / 159 / 163 | 0 / 0 / 0 |
| Rzeczywisty rozstaw 6 px | 1 / 17 / 192 | 1 / 17 / 192 |

Rozstaw 6 px leży na granicy starego zakresu wektorów; poprawa tej kontroli
pokazuje też znaczenie zakresu propozycji. Zgodność okresu oceniamy po
dopuszczeniu równoważnej całkowitej zmiany bazy, tolerancji .2 w macierzy
przejścia i stosunku pól .75–1.25. To miara na znanej syntezie, nie etykiety
wyznaczone dla TTMAPP. Odrębnie zapisano brak modelu i dostępność oceny.

Na czystej sieci tylko 58/192 otoczenia mają dostatecznie dużo nowych
rzędów, także przy **dokładnym modelu generatora**. Wszystkie pozostałe
134 przecina brzeg obrazu. Większa liczba poprawnych baz nie odzyskuje
informacji poza kadrem. Nakładających się otoczeń nie należy traktować
jako niezależnych próbek lub liczby domen.

## Fałszywe zgodności i granice tej miary

Nowe rzędy ograniczają część pozornych zgodności. Przy R64 pojedyncza baza
na poziomych niezależnych rzędach przechodzi test całego pierścienia
w 16/192 otoczeniach, lecz test nowych rzędów w 0/192. Nie jest to pełne
rozwiązanie: dla rzędów obróconych 27° wszystkie trzy pule pozostawiają
**4/192** fałszywe akceptacje przy wspólnym progu. Losowe punkty dają zero.

Dwupunktowy motyw jest regularny, ale pojedyncza sieć nie przedstawia go
w pełni. Wybór wielu baz przy wspólnym progu daje 49/192 otoczenia ponad
próg, wobec 28/192 dla pojedynczej propozycji; nie jest to odzyskanie
pełnego motywu. Nie wdrażano modelu z kilkoma pozycjami w komórce.

Usunięcie co drugiej kolumny **na całym obrazie** jest z samych centrów
nierozróżnialne od sieci o większym okresie. W obrazie kontrolnym molekuły
pozostają, ale ta próba nie wykorzystuje ich intensywności. W ocenie
zapisano osobno bazę widocznych centrów i bazę obrazu. Nie deklarujemy
odtworzenia ukrytych oznaczeń. Warunek nowych rzędów jest tu niedostępny
dla wszystkich otoczeń R64 nawet przy prawdziwej bazie widocznych centrów.

Przewidywana sieć nadal nie jest dowodem materiału. Kontrole przerwy
pozostają w raporcie, ale nie powstała nowa maska pokrycia ani granic.

## TTMAPP: brak ogólnej poprawy

Pomiary obejmują pełne klatki. Po ich zamrożeniu oznaczono otoczenia
z ≥80% centrów w jednym znanym obszarze, mieszane z ≥20% w każdym z dwóch
obszarów oraz nierozstrzygnięte. Pierwsza kategoria ma pierwszeństwo
przy dokładnej proporcji 80/20. Pozostałe miejsca nie są negatywnymi
przykładami. Referencje są częściowe, wielokrotnie używane do oceny,
więc nie stanowią niezależnego zbioru potwierdzającego uogólnienie.

Wyniki całych 24 klatek, po 2904 otoczenia na promień:

| Promień i miara | single | peaks | divisors |
| --- | ---: | ---: | ---: |
| R48, dostępny test obu kierunków | 230 | 227 | 242 |
| R48, ponad własny próg obu kierunków | 3 | 1 | 1 |
| R48, ponad wspólny próg obu kierunków | **1** | **1** | **1** |
| R64, dostępny test obu kierunków | 834 | 829 | 864 |
| R64, ponad własny próg obu kierunków | 0 | 0 | 3 |
| R64, ponad wspólny próg obu kierunków | **0** | **0** | **0** |

W R48 jest to **to samo otoczenie** we wszystkich pulach: klatka 262,
środek `(108,60)`, F=.84558. Trzy wyniki R64 po dodaniu dzielników wynikają
z łagodniejszej kalibracji, a nie stanowią dowodu poprawy dzięki kandydatom.
W tych trzech otoczeniach wybrano dokładnie te same modele co w `peaks`;
żaden nie pochodził z kandydatów uzyskanych przez dzielenie okresu.
W znanych wnętrzach R64 mediana F całego pierścienia pozostaje .5715,
a F obu osi .4284 dla wszystkich trzech pul. Lepsze propozycje są użyteczne
na kontrolach, ale nie wystarczają do wiarygodnego dopasowania STM.

Nie należy porównywać tych liczb z wcześniejszymi przypisaniami molekuł.
Nie wyznaczono komponentów domen, granic ani udziałów powierzchni.

## Wniosek i dalszy krok

Zachowujemy **porównanie kandydatów i ich dzielników** jako sprawdzony
mechanizm naprawy części aliasów okresu, z wyborem przed końcową oceną.
Zachowujemy też osobny stan braku nowych powtórzeń. Nie przyjmujemy tego
mechanizmu jako kompletnego wykrywania domen ani bezbłędnego sprawdzianu
regularności.

Kolejna próba powinna oddzielić **zgodność powtarzalnego motywu od
kompletności oznaczeń**: porównać jeden punkt z kilkoma pozycjami w komórce,
kontrolując złożoność na danych niewykorzystanych do dopasowania i wyboru.
Na kontrolach trzeba osobno zmieniać braki oznaczeń i rzeczywiste
odkształcenia/nieporządek. Obecna miara karze wszystkie nieobsadzone węzły,
a sama poprawna baza nie zapewnia wysokiej zgodności pozycji. Nie dowodzi
to jeszcze, że TTMAPP wymaga konkretnego wielopunktowego motywu.

Dopiero po poprawie tej oceny warto wrócić do testu jednego modelu kontra
dwa po stronach granicy. Materiał i lokalny szum pozostają osobnym wątkiem.
Nie rozpoczęto następnego badania, treningu ani implementacji w aplikacji.

## Odtworzenie i sprawdzenia

Źródła na `prototype/stmdomains-basis-candidates`, **`b450c4f`**, baza
`481194a`; [manifest](basis-candidates-manifest.json). Polecenie z checkoutu:
`bash stmdomains/prototypes/run-basis-candidates.sh /tmp/nowa-proba-baz`.
Wymagane poprzednie lokalne artefakty i środowisko netcat. HTML/CSV/wykresy
są samodzielne.

- 48 sprawdzeń liczbowych: znane sieci i ich wielokrotności, równoważne
  bazy, przesunięcia i kolejność centrów, brak wpływu zmiany końcowego testu
  na kandydatów i wybór, remisy połowy okresu; 54 odtworzenia generatora.
- Audyt wykrył niestabilne przypisywanie punktu dokładnie w połowie
  okresu. Ustalono lokalne konwencje remisów najbliższych węzłów i osi,
  numerycznie zerowej koncentracji fazy oraz plateau histogramu i wyboru.
  Powtórzono kalibrację i wszystkie pomiary. Faza nierozstrzygnięta jest
  ustawiana na zero we współrzędnych wycentrowanych na danych uczących;
  jest to konwencja, nie dowód właściwej fazy. Historyczne moduły bez zmian.
- Niezależny audyt: 928 redukcji baz, 140 kontroli enumeracji i przypisań,
  72 inwarianty końcowego kodu. Maksymalna różnica ocen kierunkowych
  9.22×10⁻¹⁵. 1008 punktów porównania przypisań Python/JS, także przy remisach.
- Pełne odtworzenie 97 pomiarów i 90912 decyzji z blokadą referencji;
  identyczne wyniki w **86.52 s**, zapis w `blind-replay-verification.json`. Historyczny łańcuch
  wejścia pozostał zapisanym źródłem, nie odtwarzano go od początku.
- Podgląd: **86 kontroli QtWebEngine**, bez błędów JS, zrzut i wykres obejrzane; szczegóły
  w `browser-verification.json`. Python/Bash sprawdzone składniowo,
  wrapper wykonany etapami. Nie testowano produkcyjnego GUI.

CPU, cztery procesy po jednym wątku. Końcowe pomiary: kalibracja 14.95 s,
syntetyki 44.42 s, TTMAPP 31.22 s. Maksymalny RSS procesu 115652 KiB,
nie łączny szczyt. Czasy bez generowania, oceny referencyjnej i podglądu.
Bez GPU i nowych zależności. Duże wyniki pozostają lokalne; dokumentacja
i źródła prototypu na osobnych gałęziach. Brak potrzeb zmian wspólnych modułów.

Zachowano snapshot źródła użytego do pomiarów. Późniejsza zmiana jednego
komentarza nie zmienia drzewa składni Python; potwierdzenie w
`source-comment-verification.json`. Odtworzenie używa końcowego źródła.

Kopia lokalna: **248 plików / 154293746 B**, wszystkie sumy SHA-256 zgodne;
następnie dopisano `copy-verification.json`. Względny link `previous`
prowadzi do `../fit-quality-diagnosis`.
