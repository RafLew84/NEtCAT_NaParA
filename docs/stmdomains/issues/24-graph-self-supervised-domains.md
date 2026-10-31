# Czy uczenie grafu otoczeń molekuł poprawia wykrywanie domen?

ID: 24
Type: prototype
Labels: wayfinder:prototype
Mode: HITL
Status: claimed
Assignee: Codex — domains/start
Parent: [STM Domains — etap 2: metody i zapis wyników](../map-methods-and-save.md)
Blocked by: 15, 23

## Podjęcie — 2026-11-01

Bezpośrednie polecenie użytkownika „wykonaj 24” wybiera tę próbę po
zakończeniu 23. [Protokół 24](../graph-self-supervised-protocol.md) zapisuje
hipotezę, porównanie z geometrią15 i własną inicjalizacją, jawne adaptacje
20, nowe kontrole i limit dziewięciu fitów. Wynik15 jest użytecznym,
lecz ograniczonym punktem odniesienia; jakość centrów podlega kontroli.
13 czeka także na wynik24. 25/26 i dodatkowe MPP/STP pozostają odłożone.

## Warunek podjęcia

Rozszerzenie warunkowe: krok 23 wskazuje tę próbę i jej hipotezę, a wynik
kroku 15 pozwala ocenić przydatność centrów. Samo spełnienie zależności nie
uruchamia zadania. Próbę wybrano późniejszym bezpośrednim poleceniem
użytkownika, opisanym powyżej.

**Decyzja 23 — 2026-11-01:** użytkownik zakończył obecny pilot bez wyboru
tej próby. Ticket pozostaje `open`, niewybrany i warunkowy; nie ma nowego
budżetu ani zgody na rozpoczęcie treningu przez samo zakończenie 23.

## Question

Czy uczenie bez etykiet na grafie zaznaczonych molekuł daje coś ponad
klasyczne cechy sąsiedztwa? GraphMAE z [przeglądu](../research-self-supervised-domain-learning.md)
jest inspiracją zadania uczenia, nie sprawdzonym detektorem domen STM.

## Porównanie

- Węzły reprezentują centra oznaczeń, krawędzie lokalne sąsiedztwo.
  To graf rozmieszczenia molekuł na powierzchni, nie atomów i wiązań
  wewnątrz molekuły. Nie zakładać określonej komórki, symetrii ani sześciu
  sąsiadów. Zapisać regułę budowy krawędzi i jej wrażliwość na braki.
- Maskować i odtwarzać informacyjne cechy geometryczne węzłów/otoczeń:
  odległości, kierunki lub ich jawny opis. Stały wektor „molekuła” nie
  daje użytecznego zadania. Samo odtworzenie sąsiedztwa nie dowodzi porządku.
- Zachować bezwzględny rozstaw w dostępnych jednostkach i informację
  orientacji. Sprawdzić, czy normalizacja i strata kosinusowa nie usuwają
  skali; porównać jawny składnik straty dla odległości. Nie wymuszać
  niezmienniczości, która usuwa badane granice lub różnice typów.
- Dopasować wspólny katalog bez liczby klas, z oceną porządku i spójności.
  Rozłączenie grafu przez brak detekcji nie stanowi wykrytej granicy,
  a otoczka węzłów nie jest pomiarem powierzchni materiału.
- Porównać z geometrią z kroku 15 na tych samych centrach i kontrolach
  ubytków, duplikatów oraz błędów położenia. Dodatkowe cechy obrazu mogą
  być osobnym wariantem, z kontrolą grafu bez nich, w uzgodnionym budżecie.

## Wynik do omówienia

Obowiązują protokół treningu kroku 20 i miary kroku 14. Pokazać pełne pola,
orientację/rozstaw, granice, odmowy, stabilność i koszt. Przy podziale danych
ograniczyć także zasięg sąsiedztwa grafu; w próbie przenoszenia węzły testu
nie mogą przesyłać informacji do treningu. Referencje nie uczą modelu.

Raport i prototyp mają określić korzyść z uczenia oraz zależność od jakości
oznaczeń. Udokumentowany brak poprawy kończy próbę po omówieniu. Wynik
trafia do odbioru 13, którego zależności aktualizuje się przy wyborze próby.
Nie stanowi samodzielnego potwierdzenia pokrycia ani gotowego pomiaru domen.

## Dependencies

- [Czy otoczenie zaznaczonych molekuł pozwala samodzielnie znaleźć domeny?](15-local-neighborhood-domains.md)
- [Czy trening daje poprawę i które rozszerzenie warto wykonać?](23-training-comparison-and-next-step.md)
