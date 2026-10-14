# Jak przeglądać klatki, domeny i zmiany ilościowe?

ID: 07
Type: prototype
Labels: wayfinder:prototype
Mode: HITL
Status: open
Assignee:
Parent: [STM Domains — specyfikacja analizy typów uporządkowania w serii](../map.md)
Blocked by: 01, 02, 06

## Question

Jaki przebieg pracy i widoki pozwolą otworzyć zapis, sprawdzić jego zgodność,
przejrzeć klatki oraz zrozumieć wyniki domen i wykresy zmian?

Przygotujmy szkic do reakcji użytkownika: nawigacja serii, obraz z oznaczeniami,
przełączanie widoków przed/po wyrównaniu, granica oryginalnego pola klatki,
warstwy typów/domen/kątów i połączony widok wykresu lub tabeli.

Jak wybieramy klatkę lub zakres do analizy, zaznaczamy typ i oglądamy jego zmianę,
rozróżniamy niepewny wynik od braku domeny oraz naprawiamy ścieżkę do obrazu?
Jak pokazać stałe znaczenie typów i kolory, nie sugerując śledzenia konkretnego
obszaru w czasie? Czy potrzebna jest ręczna ocena lub korekta wyników analizy,
a jeśli tak, co wolno zmieniać i jak zaznaczyć tę ingerencję?

Interakcje ustalamy na szkicu, bez implementacji aplikacji. Rozstrzygnięcie
opisuje ekran i przejścia zaakceptowane przez użytkownika, z odnośnikiem do szkicu.
Gotowe oznaczenia wejściowe nie stają się przez to edytorem detekcji YOLO.

## Dependencies

- [Jak zapis wejściowy odtwarza obrazy, oznaczenia i rejestrację?](01-import-and-geometry.md)
- [Jak definiujemy typ uporządkowania i pojedynczą domenę?](02-order-types-and-domains.md)
- [Jak dokładnie liczymy ilości i udziały na każdej klatce?](06-frame-statistics.md)
