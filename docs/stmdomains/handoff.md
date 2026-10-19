# STM Domains — przekazanie definicji wysp, typów i domen

Data: 2026-10-19.
Gałąź zadania: `domains/order-types-contract`, baza `3c7c680`.
Docelowa gałąź aplikacji: `domains/start`.
Commit przypisania: `dde20e6`; commit rozstrzygnięcia podany w końcowej wiadomości.
Przygotowanie w osobnym worktree `/tmp/netcat-stmdomains-order-types-contract`;
przeniesienie do wskazanego worktree Domains przez scalenie commitów.

## Zakres i wynik

Rozstrzygnięto ticket `02`:
[Jak definiujemy wyspę, typ uporządkowania i domenę sieci?](issues/02-order-types-and-domains.md).
Użytkownik wskazał go do wykonania przed odbiorem szkieletu. To wyjątek dla
decyzji pojęciowej z etapu 2; pozostałe warunki etapowania pozostają w mocy.

Po trzech rundach odpowiedzi zapisano `Answer` i status `resolved`:
wyspa obejmuje płat warstwy, typ opisuje układ i rozstaw niezależnie od obrotu,
a domeny rozdzielają przerwy, pasy bez uporządkowania i linie niedopasowania.
Uzgodniono także stany niepewności, małe skupiska i domeny ucięte brzegiem.
Pełne definicje i przypadki graniczne pozostają w tickecie.

Zaktualizowano słownik, indeks drugiej mapy, wyjątek kolejności w rejestrze,
README oraz pytania o referencje, próby i statystyki. Te powiązane pytania
pozostają otwarte — nie wybrano metod, progów jakości ani mianowników statystyk.
Dołączono [schematy przypadków](assets/order-types-examples.svg); są ilustracją
do rozmowy, nie danymi STM ani wynikiem segmentacji.

## Ograniczenia

Użytkownik oczekuje głównie pasa bez uporządkowania między różnymi orientacjami,
a nie płynnego wygięcia sieci. Nie ustalono ogólnej reguły dzielenia gradientu;
jego obsługa nie jest kryterium pierwszych prób. Pojawienie się takiego wejścia
wymaga doprecyzowania zamiast automatycznego nazywania go nieporządkiem.

Tolerancje rozstawu, kąta, przerw i minimalnej wielkości należy wyznaczyć
na referencjach i w próbach. Brak tych liczb nie blokuje rozstrzygnięcia pojęć,
lecz nie pozwala deklarować skuteczności metody. Granica niedopasowania może
rozdzielać domeny o tym samym typie i orientacji, co musi uwzględnić walidacja.

## Sprawdzenia

- Odczyt istniejących przeglądów i kodu: klasy A/B/C w gałęzi teksturowej
  oraz typy M6 mają odmienne znaczenia; żadne nie stało się automatycznie
  definicją STM Domains.
- Wizualna kontrola schematów i poprawności SVG, kontrola lokalnych odnośników,
  statusów/zależności ticketów oraz `git diff --check`.
- Brak zmian kodu aplikacji; nie uruchamiano testów aplikacji, GUI ani metod
  wykrywania. Nie oceniano skuteczności na danych STM w tym zadaniu.

## Następny krok

Pierwsza mapa nadal prowadzi do działającego szkieletu. Jej następne pytanie:
[Jak przeglądać obrazy i oznaczenia w szkielecie?](issues/07-browsing-and-comparison.md).
Definicje usuwają zależność merytoryczną pytań o referencje i statystyki etapu 2,
lecz nie uruchamiają automatycznie prób metod przed odbiorem szkieletu.

## Zachowany kontekst importu i integracji

[Kontrakt importu](issues/01-import-and-geometry.md) i
[audyt importu/geometrii](import-geometry-audit.md) pozostają aktualne.
Ich przekazanie oraz wynik 6 istniejących testów są w commicie `3c7c680`;
nie powtarzano tych testów dla obecnej zmiany dokumentacji.

Aktualne pozostają zgłoszenia z tamtego przekazania: dobór czasów do wybranych
klatek w odtwarzaczu MolTrack, walidacja duplikatów i shape masek, zachowanie
przy zmienionym mtime oraz koszt pełnej materializacji masek. Adapter STM Domains
może powstać bez czekania na zmianę wspólnych modułów. Wcześniejsze zgłoszenie
odwracania listy STP/S94 w NanoTrack jest poza zakresem importera z jednym MPP.
W tym zadaniu nie powstała nowa wymagana zmiana współdzielonego kodu.
