# STM Domains — przekazanie

Data: 2026-10-14. Gałąź: `domains/start`.

## Zakres i wynik

Utworzono mapę
[STM Domains — specyfikacja analizy typów uporządkowania w serii](map.md)
na podstawie rozmowy z użytkownikiem i umiejętności `wayfinder`, `grilling`
oraz `domain-modeling`. [Rejestr pytań](issues/README.md) zawiera dziewięć
otwartych ticketów decyzyjnych z zależnościami i instrukcją lokalnego trackera.
Dodano [słownik](GLOSSARY.md) i zaktualizowano README. Nie rozstrzygnięto żadnego
ticketu i nie rozpoczęto implementacji.

Zakres został zawężony w rozmowie: wejściem jest gotowy zapis z innego programu
oraz powiązane obrazy doczytywane automatycznie, z naprawą ścieżki. Na razie nie
ma osobnego importu STP/MPP/S94 ani tworzenia oznaczeń przez YOLO lub ręcznie.
Analiza obejmuje położenia i orientacje molekuł, przeglądanie klatek oraz stałe
typy uporządkowania w całej serii. Nie obejmuje historii konkretnych domen.

Użytkownik wybrał wszystkie statystyki: liczby molekuł według typu, powierzchnie,
udziały oraz liczbę oddzielnych domen. Obszarem odniesienia jest oryginalne pole
każdej klatki przesunięte zgodnie z rejestracją; dopełnienie obrazu po wyrównaniu
nie jest obszarem pomiarowym. Stały ROI dla całej serii jest poza zakresem.

Następne pytanie według kolejności trackera:
[Jak zapis wejściowy odtwarza obrazy, oznaczenia i rejestrację?](issues/01-import-and-geometry.md).
Niezależnie można podjąć
[Jak definiujemy typ uporządkowania i pojedynczą domenę?](issues/02-order-types-and-domains.md).
Przed pracą trzeba przypisać pytanie i zapisać `Status: claimed`.

## Korekta materiału wejściowego

Audyt ścieżki importu ujawnił, że wcześniejszy lokalny podgląd molekuł pomijał
obrót o 180° wykonywany przez loader MPP używany w MolTrack. Poprawiono skrypt
oraz PNG w `.scratch/stmdomains/orientation-inspection/`, ponownie obejrzano
wycinki i opisano korektę w [notatce orientacji](research-molecular-orientation.md).
Liczby detekcji, rozmiary bboxów i anizotropia masek pozostały bez zmian.
Nie wyznaczano końcowych kątów molekuł. Dla importu wymagane jest potwierdzenie
zgodności całego przekształcenia obrazu i adnotacji, nie tylko rozmiarów macierzy.

## Commit

Wcześniejsze materiały badawcze: `a5d6601`, `0e45ee3`, `44969c1`.
Bieżący commit zawiera mapę, tickety, słownik, korektę notatki, README i ten plik.
Identyfikator commita znajduje się w końcowej wiadomości sesji.

## Wykonane sprawdzenia

- Odczyt instrukcji aplikacji, konwencji lokalnego trackera i umiejętności.
- Audyt czytników oraz lokalnych modeli sekwencji, rejestracji i agregatów domen.
- Ponowne uruchomienie skryptu inspekcji z orientacją MPP zgodną z loaderem;
  wizualna kontrola poprawionych wycinków.
- Kontrola zgodności wybranych klatek z produkcyjną ścieżką importu MolTrack.
- Kontrola metadanych ticketów, lokalnych odnośników, braku cykli zależności,
  zgodności diagramu i aktualnego frontier oraz `git diff --check`.

## Ograniczenia i integracja

Mapa określa zakres i pytania, nie stanowi ukończonej specyfikacji ani potwierdzenia
skuteczności algorytmów. Testów aplikacji i GUI nie uruchamiano; nie instalowano
zależności. Dane i diagnostyka pozostają lokalne poza Git. Parametry fizyczne
nagłówka MPP i definicja orientacji pozostają nieustalone.

Nie zmieniano wspólnych modułów. Ich ewentualne wykorzystanie i potrzebne zmiany
zostaną rozstrzygnięte w pytaniu o przekazanie specyfikacji do implementacji.
Podczas audytu zauważono dodatkowo problem poza obecnym zakresem: odwrócona
seria wielu STP/S94 w NanoTrack zapisuje już odwróconą listę źródeł, a przy
odtworzeniu odwraca ją ponownie. Sprawdzenie w pamięci na dwóch lokalnych S94
zmieniło kolejność pierwszej klatki; nie zapisano ani nie naprawiano sesji.
Warto przekazać ten przypadek integracji przed ponownym użyciem tego wariantu
wczytywania. Nie blokuje mapy opartej na dostarczonym zapisie pojedynczego MPP.
