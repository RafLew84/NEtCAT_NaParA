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
do implementacji. Następnie na jego polecenie rozpoczęto
[kontrakt zapisu i eksportu](issues/08-save-and-export.md) przed odbiorem metod.
Zatwierdzone dotąd wymagania i otwarte pytania są w tickecie; pozostaje on
`claimed`. Pozostałe warunki etapowania obowiązują.

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

Materiały do porównań: [przegląd wykrywania domen](research-general-domain-detection.md)
oraz [wyspy, orientacja sieci i level set](research-domain-detection-level-sets.md).
To propozycje kandydatów i eksperymentów, nie zatwierdzenie algorytmu.

Zasady `wayfinder`, rodzaje pytań i zależności opisuje
[wspólny rejestr](issues/README.md). Ta mapa określa decyzje; produkcyjne zmiany
powstaną w zadaniach wynikających z ustaleń i wyników prób.

## Decisions so far

- [Jak definiujemy wyspę, typ uporządkowania i domenę sieci?](issues/02-order-types-and-domains.md):
  wyspa jako płat warstwy; typ oddzielony od orientacji; domeny, granice
  niedopasowania, małe skupiska i stany niepewności uzgodnione na przykładach.
- [Jak porównać metody wykrywania wysp i domen w serii?](issues/05-stable-types-across-frames.md):
  katalog wspólny dla wybranego zakresu; pilotaż ujawnił luki w doborze skali,
  rozróżnianiu rozstawu i granicach domen. Dalsze próby mają osobne tickety.
- [Jak dokładnie liczymy ilości i udziały na każdej klatce?](issues/06-frame-statistics.md):
  dwa udziały powierzchni, liczebności według środka oznaczenia, jawne braki
  i korekty konfliktów; wyniki osobno dla klatek, bez agregatów serii.

Nie wybrano ani nie zwalidowano metody i nie ustalono kontraktu zapisu wyników.

## Not yet specified

Próby na kolejnych akwizycjach mogą ujawnić dodatkowe klasy błędów, potrzebę
innych cech lub ograniczenia obecnych oznaczeń. Zakres dostrojenia aplikacji
i formatów ustalimy na podstawie wyników tych prób.

## Out of scope

- Pomiar orientacji pojedynczej molekuły —
  [pytanie odłożone poza oba etapy](issues/03-molecular-orientation.md),
  bez rozstrzygnięcia naukowego. Jego ewentualny powrót wymaga nowego zakresu.
- Detekcja YOLO, tworzenie oznaczeń i trenowanie detektora.
- Śledzenie konkretnych molekuł i domen, historii podziałów, scaleń i narodzin.
- Stały ROI całej serii, ponowne liczenie rejestracji oraz rozwój STM Viewer.
