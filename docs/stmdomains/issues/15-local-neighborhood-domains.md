# Czy otoczenie zaznaczonych molekuł pozwala samodzielnie znaleźć domeny?

ID: 15
Type: prototype
Labels: wayfinder:prototype
Mode: HITL
Status: open
Assignee:
Parent: [STM Domains — etap 2: metody i zapis wyników](../map-methods-and-save.md)
Blocked by: 14

## Question

Czy geometria dostępnych centrów wystarcza do znalezienia spójnych
obszarów podobnego uporządkowania bez przykładów domen?

1. Zbudować lokalne opisy kilku rozmiarów sąsiedztwa: rozkłady odległości
   i kątów oraz powtarzalność otoczenia. Zachować rozstaw w px; normalizacja
   nie może ukryć różnicy rozstawu. Porównać prosty opis z SOAP, jeśli prosty
   opis nie rozdziela kontrolnych struktur. Nie narzucać liczby sąsiadów
   odpowiadającej jednej symetrii.
2. Grupować opisy we wspólnym katalogu całego wybranego zakresu, bez zadania
   `K`. Kandydatem jest HDBSCAN z dopuszczonym jednym klastrem. Typ ma być
   odporny na obrót; kąt analizować osobno, z symetrią oszacowanej struktury.
3. Łączyć przestrzennie sąsiednie, zgodne obiekty. Oddzielić rozłączne
   fragmenty. Zgodność opisu nie wystarcza: wymagać dowodów powtarzalności
   wykraczających poza kontrole losowe. Nie traktować etykiety „noise”
   algorytmu jako fizycznego nieuporządkowania.

Zapisać osobno wynik grupowania i wynik po ocenie porządku. Mierzyć
nadmierne podziały, scalanie, pozostawione bez przypisania molekuły i wpływ
braków centrów. Warunek zatrzymania: brak ustawień odróżniających kontrole
losowe od regularnej pojedynczej domeny. Nie naprawiać tego ręcznym `K=3`.
Uzasadnienie i biblioteki: [przegląd grupowania](../research-domain-discovery-and-object-clustering.md).

Sprawdzić także rzadki układ, zmianę kolejności i rozszerzenie zakresu
katalogu. Zachować znaczenie typów przy obrocie, a różne rozłączne domeny
tego samego typu liczyć oddzielnie. Wykazać ograniczenia przy granicy
przesunięcia; sama zgodność lokalnego opisu nie potwierdza jej rozpoznania.

## Dane i kryteria porównania

Obowiązuje [wspólne wejście, kontrole i format oceny](14-unsupervised-input-and-controls.md).
Analiza obejmuje całe pola klatek, bez ramek domen na wejściu; częściową
referencję odsłaniamy po zapisaniu predykcji. Powtórzenie ze zmienioną lub
usuniętą referencją ma zachować identyczny wynik analizy. Parametry i źródła
ich doboru są jawne, bez dopasowywania liczby grup do BLACK/RED/YELLOW.

Ocenić zero/jedną/wiele domen, fałszywy porządek, scalenia/podziały, odmowy,
braki detekcji i stabilność zakresu. Nie wymuszać domeny na szumie ani nie
zaliczać odrzucenia wszystkich danych jako sukcesu. Spójność klastra,
rozpoznanie struktury i powierzchnia materiału pozostają odrębne.

## Wynik do omówienia

Odtwarzalny prototyp, pełne nakładki klatek, tabela wspólnych kontroli,
przypisania i odmowy oraz raport z parametrami, wersjami, kosztem i pamięcią.
Wynik syntetyczny rozdzielić od ograniczonej oceny częściowych referencji
TTMAPP. Nie deklarować dokładności nieoznaczonych fragmentów ani granic,
których referencja nie określa.

Omówić z użytkownikiem, czy kierunek zasługuje na dalsze rozwijanie i jakie
ograniczenia zostają. Udokumentowany wynik negatywny także odpowiada na to
pytanie. Zakończenie próby nie zatwierdza metody produkcyjnej; ten wybór
pozostaje w [odbiorze metod](13-method-acceptance.md). Kod prototypu oraz
lokalne duże wyniki nie stają się automatycznie częścią aplikacji.

## Dependencies

- [Jak przygotować wspólne wejście i kontrole bez narzucania domen?](14-unsupervised-input-and-controls.md)

## Kontekst

- [Przegląd samodzielnego wyszukiwania domen w STM/AFM](../research-stm-afm-unsupervised-domain-discovery.md)
- [Przegląd domen i grupowania obiektów](../research-domain-discovery-and-object-clustering.md)
