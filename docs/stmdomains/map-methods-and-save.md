# STM Domains — etap 2: metody i zapis wyników

ID: stmdomains-methods-map
Labels: wayfinder:map
Status: open
Assignee:

## Destination

Uzgodnione na próbach metody wykrywania pokrycia/wysp i domen orientacji oraz
uporządkowania sieci, wraz z oceną jakości, statystykami i kontraktem zapisu
wyników. Ustalenia mają pozwolić rozwinąć odebrany szkielet STM Domains.

## Notes

Etap odłożony do czasu odbioru działającego szkieletu z
[pierwszej mapy](map.md), zgodnie z decyzją użytkownika z 2026-10-16.
Jego otwarte pytania nie blokują implementacji ani odbioru etapu 1.

Wyjątki wskazane przez użytkownika 2026-10-19: wcześniej rozpatrzono
[definicje wyspy, typu i domeny sieci](issues/02-order-types-and-domains.md)
i wykonano [pilotaż porównania metod](issues/05-stable-types-across-frames.md).
Pilotaż wskazał konkretne braki; nie zastępuje odbioru szkieletu ani walidacji.
Na polecenie użytkownika dodano dalsze pytania o pokrycie, typy, granice
i odbiór metod. Następnie na jego bezpośrednie polecenie uzgodniono
[statystyki klatek](issues/06-frame-statistics.md), nadal jako definicje
do implementacji. Na kolejne polecenie uzgodniono też
[kontrakt zapisu i eksportu](issues/08-save-and-export.md) przed odbiorem metod.
Kontrakt jest niezależny od algorytmu; odbiór sprawdzi jego realizację
na wynikach prób. Pozostałe warunki etapowania obowiązują.

Na bezpośrednie polecenie z 2026-10-21 wykonano
[wstępną próbę pokrycia i skali](issues/10-coverage-and-scale.md).
Użytkownik przyjął potrzebę dalszej próby z referencjami i doprecyzował, że
pokrycie dotyczy materiału na dowolnym widocznym poziomie warstwy; ciemne
obszary bez wystarczających przesłanek pozostają nierozstrzygnięte.
[Raport](coverage-and-scale-pilot.md) nie wybiera metody. Po wstępnej próbie
pytanie pozostawało `claimed`; pełny odbiór nadal wymaga protokołu referencji i jakości.
Następnie użytkownik dostarczył
[częściowe oznaczenia wybranych domen](partial-domain-reference-audit.md).
Zweryfikowano ich geometrię i przygotowano wnętrza; obszary poza ramkami są
nieoznaczone. Dane umożliwiają lokalne porównanie, ale nie pełną ocenę pokrycia.
Użytkownik zaakceptował ten zbiór na najbliższe próby: nie czekamy na dodatkowe
anotacje ani zamknięcie całego pytania 04, aby wykonać porównania w oznaczonym
zakresie. Potrzebę kolejnych referencji uzasadni konkretny wynik próby.
Następnie [wykonano porównanie na tych referencjach](coverage-partial-reference-trial.md):
18 klatek, 54 wnętrza i kontrole ubytków. Warianty z centrów zachowują materiał
przy pełnych oznaczeniach, lecz są wrażliwe na ich braki; proste warianty
jasności i amplitudy odrzucają znaczne części wnętrz. Po omówieniu wyniku
ticket 10 ma status `resolved` jako zakończona próba, bez zatwierdzenia metody.
Nie czeka na krok 11; nierozstrzygnięte warunki pełnego pomiaru pokrycia
pozostają w zakresie odbioru metod, z możliwością wskazania kolejnych prób.

Na kolejne bezpośrednie polecenie wykonano
[próbę wspólnego katalogu typów](structural-type-catalogue-trial.md).
Użytkownik doprecyzował kolory referencji jako głównie różne orientacje tej
samej sieci. Ticket 11 ma status `resolved` jako zakończony eksperyment:
kontrole wskazały przydatność rozstawu i zróżnicowania odległości, a dane
rzeczywiste — nadmierne dzielenie i zależność od zakresu. Wynik przygotowano
do obejrzenia; nie deklarujemy zatwierdzenia metody ani parametrów przez użytkownika.

Na kolejne polecenie wykonano [próbę granic przesunięcia](phase-boundaries-trial.md).
Ticket 12 jest `resolved` jako zakończony eksperyment, bez zatwierdzenia metody.
Niedopasowanie wektorów między centrami działa na prostych kontrolach tego
samego typu i kąta, ale wymaga wiarygodnej sieci; prosta faza obrazu daje
fałszywe oraz wielokrotne cięcia. Dokładnych błędów granic TTMAPP nie policzono
z przybliżonych ramek orientacyjnych. Ograniczenia pozostają w odbiorze 13.

- Rozpatrujemy dwa wyniki: pokrycie materiałem/wyspy oraz domeny orientacji
  i uporządkowania sieci. Orientacja pojedynczej molekuły jest odłożona.
- Korzystamy z odtworzonych obrazów i gotowych oznaczeń. Możemy porównywać
  cechy obrazu i geometrię sąsiedztwa; żaden istniejący algorytm nie jest
  wybrany przez sam fakt obecności w MolTrack.
- Typy uporządkowania mają zachowywać znaczenie w całej serii. Nie zakładamy
  katalogu A/B/C ani obowiązkowej symetrii M6.
- Docelowe wyniki ilościowe obejmują liczby molekuł według typu, powierzchnie,
  udziały i liczby oddzielnych obszarów. Ich dokładne definicje ustala ticket
  o statystykach, rozróżniając wyspy i domeny sieci.
- Polem odniesienia pozostaje oryginalne pole danej klatki przeniesione
  zgodnie z rejestracją. Padding nie jest powierzchnią próbki ani pomiarem.
- Najpierw definiujemy referencje i porównujemy metody na danych; zapis wyników
  rozwijamy po określeniu, co wyniki oznaczają. Szkielet nie wymaga wcześniej
  docelowego schematu pliku ani wybranego algorytmu.
- Próba, która wykazuje nieskuteczność metody, jest wynikiem badania.
  Nie wolno uznać jej za gotową metodę tylko dlatego, że program się uruchamia.

Po próbach 10–12 użytkownik poprosił o przegląd MolTrack i podkreślił potrzebę
ogólnego znajdowania domen, również poza wariantami jednej znanej sieci.
[Audyt implementacji MolTrack](moltrack-method-audit.md) potwierdza ograniczenia
modeli M3/M6 oraz prototypów tekstury TTMAPP. MolTrack pozostaje porównaniem,
nie metodą docelową. Następna proponowana próba dotyczy lokalnego wzoru obrazu
w kilku skalach, z osobnym typem i orientacją oraz oceną korzyści z centrów.
Nie zatwierdzono algorytmu ani wymagania działania całkowicie bez oznaczeń.

Materiały do porównań: [przegląd wykrywania domen](research-general-domain-detection.md)
oraz [wyspy, orientacja sieci i level set](research-domain-detection-level-sets.md).
To propozycje kandydatów i eksperymentów, nie zatwierdzenie algorytmu.

Zasady `wayfinder`, rodzaje pytań i zależności opisuje
[wspólny rejestr](issues/README.md). Ta mapa określa decyzje; produkcyjne zmiany
powstaną w zadaniach wynikających z ustaleń i wyników prób.

## Decisions so far

- [Jak rozdzielać domeny o tym samym typie i orientacji?](issues/12-phase-boundaries.md):
  wykonano 7 wariantów na 19 kontrolach i 18 klatkach TTMAPP. Niedopasowanie
  wektorów centrów wykrywa kontrolne granice przesunięcia 4/8 px bez dzielenia
  przez pojedyncze defekty. Nie daje jeszcze gotowej metody: estymata sieci
  dostępna w 7/54 wnętrz, zależność od braków detekcji i brak dokładnej
  referencji rzeczywistej granicy. Faza obrazu wymaga dalszej oceny kontrastu.
- [Jak rozpoznawać typy przy obrocie, zmianie rozstawu i rzadkich wzorach?](issues/11-structural-type-catalogue.md):
  wykonano 9 wariantów na 18 klatkach i 19 kontrolach. Dodanie rozstawu
  i różnic odległości rozdziela proste kontrolne sieci bez zmiany typu przy
  obrocie; nie daje jeszcze stabilnego katalogu TTMAPP. Dobór sąsiedztwa,
  rozmiaru okna i warunki odmowy wymagają dalszych prób przed odbiorem 13.
- [Jak wyznaczać pokrycie bez mylenia luk oznaczeń z podłożem?](issues/10-coverage-and-scale.md):
  zakończono próbę na częściowych referencjach. Maski z centrów zależą od
  kompletności detekcji; proste cechy jasności/amplitudy gubią znany materiał.
  Nie wybrano metody pomiarowej; pełna ocena granic, nadmiaru maski i odmów
  pozostaje do odbioru metod. Krok 11 jest osobnym eksperymentem.
- [Jak definiujemy wyspę, typ uporządkowania i domenę sieci?](issues/02-order-types-and-domains.md):
  wyspa jako płat warstwy; typ oddzielony od orientacji; domeny, granice
  niedopasowania, małe skupiska i stany niepewności uzgodnione na przykładach.
- [Jak porównać metody wykrywania wysp i domen w serii?](issues/05-stable-types-across-frames.md):
  katalog wspólny dla wybranego zakresu; pilotaż ujawnił luki w doborze skali,
  rozróżnianiu rozstawu i granicach domen. Dalsze próby mają osobne tickety.
- [Jak dokładnie liczymy ilości i udziały na każdej klatce?](issues/06-frame-statistics.md):
  dwa udziały powierzchni, liczebności według środka oznaczenia, jawne braki
  i korekty konfliktów; wyniki osobno dla klatek, bez agregatów serii.

- [Co zapisujemy i eksportujemy po próbach metod?](issues/08-save-and-export.md):
  samowystarczalny plik z obrazem, oznaczeniami i opcjonalnie jednym wynikiem;
  otwarcie bez przeliczania, korekty oraz eksport CSV/PNG uzgodnione.

Nie wybrano ani nie zwalidowano metod. Kontrakt zapisu jest ustalony;
jego implementacja i odbiór na wynikach metod pozostają do wykonania.

## Not yet specified

Próby na kolejnych akwizycjach mogą ujawnić dodatkowe klasy błędów, potrzebę
innych cech lub ograniczenia obecnych oznaczeń. Szczegółowe metadane metod
i dostrojenie aplikacji ustalimy na podstawie prób, zachowując przyjęty
kontrakt zapisu i znaczenia danych.

## Out of scope

- Pomiar orientacji pojedynczej molekuły —
  [pytanie odłożone poza oba etapy](issues/03-molecular-orientation.md),
  bez rozstrzygnięcia naukowego. Jego ewentualny powrót wymaga nowego zakresu.
- Detekcja YOLO, tworzenie oznaczeń i trenowanie detektora.
- Śledzenie konkretnych molekuł i domen, historii podziałów, scaleń i narodzin.
- Stały ROI całej serii, ponowne liczenie rejestracji oraz rozwój STM Viewer.
