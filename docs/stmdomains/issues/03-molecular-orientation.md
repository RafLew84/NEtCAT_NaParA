# Jak mierzyć orientację molekuły i oznaczać wynik niepewny?

ID: 03
Type: prototype
Labels: wayfinder:prototype
Mode: HITL
Status: closed
Assignee:
Parent: [STM Domains — etap 2: metody i zapis wyników](../map-methods-and-save.md)
Blocked by: 01

## Scope disposition

2026-10-16: użytkownik zatwierdził najpierw szkielet, następnie próby metod
wykrywania wysp i domen orientacji/uporządkowania sieci oraz zapis wyników.
Pomiar orientacji pojedynczej molekuły odłożono poza oba etapy. Ticket zamknięto
ze względu na zakres, bez rozstrzygnięcia metody lub wiarygodności pomiaru.
Nie blokuje pozostałych ticketów. Poniższe pytanie zachowano jako kontekst;
powrót do niego wymaga nowego zakresu pracy.

## Question

Jaki widoczny motyw na wycinku stanowi kierunek molekuły, które obroty są
równoważne i jaki wynik powinien otrzymać wycinek bez rozróżnialnego kierunku?

Zbudujmy niewielki materiał do wspólnej oceny na poprawnie odtworzonych obrazach:
porównanie osi kształtu, obracanego wzorca i profili kątowych wraz z niepewnymi
przykładami. Użytkownik wskazuje znaczenie motywu; agent nie ustala za niego osi
chemicznej ani symetrii TTMAPP.

Do decyzji należą odniesienie i zakres kąta, wpływ centrowania i sąsiadów,
przydatność opcjonalnych masek, obsługa wielu dobrych dopasowań oraz miara jakości.
Czy informacja z tego obrazu pozwala mierzyć użyteczną orientację, a jeżeli tylko
częściowo, jaki wynik przekazujemy dalej? Nie uzupełniamy brakujących kątów przez
założenie, że molekuła musi być zgodna z siecią sąsiadów.

Rozstrzygnięcie zapisuje wybrany opis pomiaru, przykłady i ograniczenia; próba nie
jest implementacją produkcyjnego estymatora. Materiał do obejrzenia linkujemy.

Kontekst: [metody i kontrola danych](../research-molecular-orientation.md).

## Dependencies

- [Jak zapis wejściowy odtwarza obrazy, oznaczenia i rejestrację?](01-import-and-geometry.md)
