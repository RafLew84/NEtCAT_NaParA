# Jakie referencje i kryteria potwierdzą wiarygodność analizy?

ID: 04
Type: grilling
Labels: wayfinder:grilling
Mode: HITL
Status: open
Assignee:
Parent: [STM Domains — specyfikacja analizy typów uporządkowania w serii](../map.md)
Blocked by: 02

## Question

Na jakich danych i niezależnych oznaczeniach ocenimy orientacje, typy oraz
obszary domen, aby odróżnić poprawne uruchomienie programu od skutecznej analizy?

Ustalmy przygotowanie referencji i ich niepewność, dobór klatek/akwizycji,
podział danych używanych do strojenia i sprawdzania oraz syntetyczne przypadki
kontrolne. Posiadany zapis TTMAPP jest pierwszym przykładem, nie automatyczną
prawdą odniesienia dla domen lub kątów.

Jakie błędy kątów, nadmierne podziały, błędne scalenia, niestabilność typów,
fałszywe domeny i odmowy pomiaru są istotne dla użytkownika? Jak raportować
wyniki dla małych typów, ubytków oznaczeń i domen uciętych krawędzią?

Rozstrzygnięcie określa wejścia, sposób oznaczania, pomiary jakości i progi lub
procedurę ich ustalenia. Jeśli brakuje danych, wskazuje konkretny brak do zdobycia,
zamiast uznawać metodę za skuteczną bez referencji.

Kontekst: [proponowane kryteria domen](../research-general-domain-detection.md),
[walidacja orientacji](../research-molecular-orientation.md).

## Dependencies

- [Jak definiujemy typ uporządkowania i pojedynczą domenę?](02-order-types-and-domains.md)
