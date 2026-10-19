# Które metody i warunki odmowy wyniku przyjmujemy po próbach?

ID: 13
Type: grilling
Labels: wayfinder:grilling
Mode: HITL
Status: open
Assignee:
Parent: [STM Domains — etap 2: metody i zapis wyników](../map-methods-and-save.md)
Blocked by: 04, 06, 10, 11, 12

## Question

Czy po porównaniach mamy zestaw metod, parametrów i ograniczeń, który można
włączyć do STM Domains oraz oprzeć na nim zapis wyników? Zakończenie pilotażu
wskazującego braki nie jest jeszcze takim odbiorem.

Przejrzyjmy razem wyniki pokrycia, katalogu typów i granic domen na referencjach,
w tym odmowy, niejednoznaczności, rzadkie typy i błędy scaleń/podziałów.
Czy metody są ze sobą zgodne geometrycznie i znaczeniowo? Czy wnioskowanie
o porządku jest oddzielone od jakości danych i przynależności do katalogu?

Sprawdźmy zgodność z [definicjami statystyk](06-frame-statistics.md#answer--2026-10-19):
geometrię powierzchni płatów, oba mianowniki udziału powierzchni, przypisanie
molekuł według środka bboxa, brak podwójnego liczenia oraz częściowe wyniki.
Ręczny wybór domeny w konkretnym konflikcie ma przeliczać wynik i pozostawiać
informację o korekcie; nie jest dowodem trafności automatycznej segmentacji.

Potrzebne są też mierzalne koszty na docelowych seriach, pamięć, najdłuższy
nieprzerywalny etap i zachowanie anulowania, odtwarzalność parametrów oraz
warunki unieważnienia katalogu po zmianie zakresu. Pilotaż ośmiu klatek nie
rozstrzyga tych własności dla całego wejścia. Dobór zakresu sprawdzeń wynika
z uzgodnionego niewielkiego, wewnętrznego zastosowania.

Wynik: zaakceptowany przez użytkownika zestaw z jasno określonymi warunkami
użycia/odmowy albo konkretna dalsza luka. Nie przyjmujemy metody na podstawie
samego uruchomienia programu ani dostrojenia do tych samych przykładów.
Ten odbiór jest warunkiem kontraktu zapisu analizy, nie odbioru szkieletu.

## Dependencies

- [Jakie referencje i kryteria potwierdzą wiarygodność analizy?](04-reference-and-quality.md)
- [Jak dokładnie liczymy ilości i udziały na każdej klatce?](06-frame-statistics.md)
- [Jak wyznaczać pokrycie bez mylenia luk oznaczeń z podłożem?](10-coverage-and-scale.md)
- [Jak rozpoznawać typy przy obrocie, zmianie rozstawu i rzadkich wzorach?](11-structural-type-catalogue.md)
- [Jak rozdzielać domeny o tym samym typie i orientacji?](12-phase-boundaries.md)
