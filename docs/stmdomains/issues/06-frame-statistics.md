# Jak dokładnie liczymy ilości i udziały na każdej klatce?

ID: 06
Type: grilling
Labels: wayfinder:grilling
Mode: HITL
Status: claimed
Assignee: Codex — domains/frame-statistics
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

Z [definicji wysp, typów i domen](02-order-types-and-domains.md#answer--2026-10-19)
wynika już, że wyspa obejmuje płat warstwy z normalnymi odstępami między
molekułami. Nie zastępujemy jego powierzchni sumą masek molekuł. Domeny ucięte
brzegiem uwzględniamy w widocznym zakresie i oznaczamy ucięcie; małe skupisko
bez wystarczających danych o porządku nie jest automatycznie domeną.

Pozostaje ustalić dokładne liczenie powierzchni odtworzonych obszarów,
mianowniki udziału powierzchni i liczebności, przypisywanie molekuł do domen
oraz agregację nakładania, niepewności i nieprzypisanych typów. Jak prezentujemy
liczby obserwowanych fragmentów bez wnioskowania o połączeniach poza kadrem?
Co pokazujemy w pikselach przy braku kalibracji i jak przechodzimy na jednostki
fizyczne po jej uzupełnieniu?

Jak przedstawiamy zmiany po numerach klatek przy niewiarygodnych czasach eksportu,
wybór zakresu klatek oraz rozróżnienie zera od braku pomiaru? Zmiana liczby obszarów
w klatkach nie jest dowodem narodzin lub zaniku konkretnej domeny.

Rozstrzygnięcie zawiera definicje wielkości, jednostki i przykłady obliczeń na
prostym układzie z domeną na brzegu, pustym dopełnieniem i niepewnymi wynikami.
Te statystyki powstają w etapie 2; ich definicja nie blokuje podstawowego podglądu.

## Dependencies

- [Jak zapis wejściowy odtwarza obrazy, oznaczenia i rejestrację?](01-import-and-geometry.md)
- [Jak definiujemy wyspę, typ uporządkowania i domenę sieci?](02-order-types-and-domains.md)

## Discussion — 2026-10-19

Na bezpośrednie polecenie użytkownika rozstrzygamy definicje statystyk
przed odbiorem szkieletu. To decyzja pojęciowa, nie implementacja ani walidacja
metod wykrywania. Kontrakty importu i definicje wysp/typów/domen są już
uzgodnione; pilotaż wskazał osobne pytania do dalszych prób metod.
