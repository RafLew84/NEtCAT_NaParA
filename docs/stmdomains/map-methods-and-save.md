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

<!-- Brak wybranej i zwalidowanej metody oraz kontraktu zapisu wyników. -->

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
