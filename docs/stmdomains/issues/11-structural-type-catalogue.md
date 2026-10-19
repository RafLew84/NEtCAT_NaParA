# Jak rozpoznawać typy przy obrocie, zmianie rozstawu i rzadkich wzorach?

ID: 11
Type: prototype
Labels: wayfinder:prototype
Mode: HITL
Status: open
Assignee:
Parent: [STM Domains — etap 2: metody i zapis wyników](../map-methods-and-save.md)
Blocked by: 04, 05

## Question

Jakie cechy i procedura wspólnego katalogu zachowują typ przy obrocie,
odróżniają istotny rozstaw i nie tworzą nowych typów z brzegu lub defektu?
Jak zachować rzadki wzór oraz odmówić przypisania wzoru niejednoznacznego?

Użytkownik wybrał katalog ustalany wspólnie dla całego zaznaczonego zakresu.
Nie wracamy domyślnie do katalogu zamrożonego na klatkach referencyjnych.
[Pilotaż](../method-comparison-pilot.md) zachował typ po obrocie, lecz scalił
rozstawy 16 i 20 px. Zmiana promienia o kolejną powłokę sąsiadów unieważniła
próg regularności, a FFT reagowało głównie na obwiednię sztucznego płata.

Sprawdźmy stabilny wybór sąsiedztwa, wagi cech struktury i rozstawu oraz okno
obrazu obejmujące wystarczającą liczbę okresów. Porównanie ma objąć kontrolowane
obroty, rozstawy, defekty, brzeg, ubytki oznaczeń i rzadkie wzory. Nie narzucamy
rodziny cech ani liczby typów tylko po to, by uzyskać oczekiwaną liczbę domen.

Ustalmy kryterium odrzucenia, niejednoznaczności i kandydata na nowy typ,
odrębne od brakujących danych. Oceńmy wpływ liczebności punktów/klatek na
katalog, powtórzenia oraz zmianę zakresu. Wersje katalogu wymagają jawnego
porównania znaczeń, nie tylko zgodnych numerów. Nie śledzimy konkretnych domen.

Wynik: obejrzane przypisania i pomiary na uzgodnionych referencjach, stabilność
typu wobec obrotu/rozstawu, ocena rzadkich typów i odmów oraz koszt/pamięć.
Wspólne dopasowanie katalogu i niezależna ocena poprawności to osobne czynności.

## Dependencies

- [Jakie referencje i kryteria potwierdzą wiarygodność analizy?](04-reference-and-quality.md)
- [Jak porównać metody wykrywania wysp i domen w serii?](05-stable-types-across-frames.md)
