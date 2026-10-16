# Jak dokładnie liczymy ilości i udziały na każdej klatce?

ID: 06
Type: grilling
Labels: wayfinder:grilling
Mode: HITL
Status: open
Assignee:
Parent: [STM Domains — etap 2: metody i zapis wyników](../map-methods-and-save.md)
Blocked by: 01, 02

## Question

Jak zdefiniować liczby molekuł według typu, powierzchnie, udziały oraz liczbę
oddzielnych domen, żeby wartości były jednoznaczne i porównywalne w serii?

Osobno zdefiniujmy pokrycie i wyspy oraz domeny sieci wewnątrz materiału.
Liczba wysp nie jest liczbą domen orientacyjnych. Ustalmy mianownik udziału
domen sieci: całe poprawne pole klatki, pokrycie lub obie jawnie nazwane miary.

Pole odniesienia jest już ustalone: oryginalny rozmiar każdej klatki przesunięty
według rejestracji. Dopełnienie większego obrazu nie wchodzi do statystyk.
Nie wracamy tu do wyboru stałego ROI.

Pozostaje ustalić: czy powierzchnia domeny to obszar między molekułami, suma ich
masek czy inna jawna definicja; jakie są mianowniki udziału powierzchni i udziału
liczebności; jak traktujemy nieprzypisane molekuły, nakładanie obszarów, brak
wyniku i domeny przecinające krawędź klatki. Co pokazujemy w pikselach przy braku
kalibracji i jak przechodzimy na jednostki fizyczne po jej uzupełnieniu?

Jak przedstawiamy zmiany po numerach klatek przy niewiarygodnych czasach eksportu,
wybór zakresu klatek oraz rozróżnienie zera od braku pomiaru? Zmiana liczby obszarów
w klatkach nie jest dowodem narodzin lub zaniku konkretnej domeny.

Rozstrzygnięcie zawiera definicje wielkości, jednostki i przykłady obliczeń na
prostym układzie z domeną na brzegu, pustym dopełnieniem i niepewnymi wynikami.
Te statystyki powstają w etapie 2; ich definicja nie blokuje podstawowego podglądu.

## Dependencies

- [Jak zapis wejściowy odtwarza obrazy, oznaczenia i rejestrację?](01-import-and-geometry.md)
- [Jak definiujemy wyspę, typ uporządkowania i domenę sieci?](02-order-types-and-domains.md)
