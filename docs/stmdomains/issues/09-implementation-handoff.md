# Jak przekazać uzgodnioną specyfikację do implementacji?

ID: 09
Type: grilling
Labels: wayfinder:grilling
Mode: HITL
Status: open
Assignee:
Parent: [STM Domains — specyfikacja analizy typów uporządkowania w serii](../map.md)
Blocked by: 04, 05, 07, 08

## Question

Czy po rozstrzygnięciu pytań można opisać spójną drogę od wejścia do wyników,
z jawnymi granicami modułów, zależnościami i sposobem odbioru?

Ustalmy zakres ponownego użycia czytników, geometrii, rejestracji, analizy i GUI
z istniejących aplikacji. Oddzielmy zmiany lokalne STM Domains od zmian wspólnych,
które trzeba przekazać sesji integracyjnej. Gotowy kod MolTrack jest materiałem
do oceny, nie domyślnym wyborem metody.

Jakie wymagania dotyczą czasu obliczeń, pamięci, anulowania i ponownego użycia
wyników wynikają z prób oraz z rozmiarów serii? Jak odbieramy import, statystyki,
interakcje i zapis, a osobno jakość naukową analizy? Czy istnieje nierozstrzygnięta
kwestia, bez której nie można przygotować zadań implementacyjnych?

Rozstrzygnięcie wskazuje uzgodnioną specyfikację, kolejność etapów i wymagania
wobec integracji. Nowe problemy wracają jako pytania mapy. Nie implementujemy
aplikacji ani nie uznajemy mapy za ukończoną tylko dlatego, że istnieje szkielet GUI.

Kontekst: [instrukcje współpracy](../../PARALLEL_DEVELOPMENT.md).

## Dependencies

- [Jakie referencje i kryteria potwierdzą wiarygodność analizy?](04-reference-and-quality.md)
- [Jak odkrywać domeny i zachować stałe typy w całej serii?](05-stable-types-across-frames.md)
- [Jak przeglądać klatki, domeny i zmiany ilościowe?](07-browsing-and-comparison.md)
- [Co zapisujemy i eksportujemy, aby odtworzyć analizę?](08-save-and-export.md)
