# Jakie referencje i kryteria potwierdzą wiarygodność analizy?

ID: 04
Type: grilling
Labels: wayfinder:grilling
Mode: HITL
Status: open
Assignee:
Parent: [STM Domains — etap 2: metody i zapis wyników](../map-methods-and-save.md)
Blocked by: 02

## Question

Na jakich danych i niezależnych oznaczeniach ocenimy pokrycie, wyspy, orientacje
sieci, typy oraz domeny, aby odróżnić poprawne uruchomienie od skutecznej analizy?

Ustalmy przygotowanie referencji i ich niepewność, dobór klatek/akwizycji,
podział danych używanych do strojenia i sprawdzania oraz syntetyczne przypadki
kontrolne. Posiadany zapis TTMAPP jest pierwszym przykładem, nie automatyczną
prawdą odniesienia dla pokrycia, domen lub kątów sieci. Maski pokrycia i granice
domen sieci wymagają odrębnej referencji; padding wykluczamy z obu ocen.

Jakie błędy kątów, nadmierne podziały, błędne scalenia, niestabilność typów,
fałszywe domeny i odmowy pomiaru są istotne dla użytkownika? Jak raportować
wyniki dla małych typów, ubytków oznaczeń i domen uciętych krawędzią?

Rozstrzygnięcie określa wejścia, sposób oznaczania, pomiary jakości i progi lub
procedurę ich ustalenia. Jeśli brakuje danych, wskazuje konkretny brak do zdobycia,
zamiast uznawać metodę za skuteczną bez referencji.

To odbiór metod drugiego etapu; nie jest warunkiem odbioru szkieletu.

Kontekst: [proponowane kryteria domen](../research-general-domain-detection.md),
[protokół dla wysp i orientacji sieci](../research-domain-detection-level-sets.md).

## Dependencies

- [Jak definiujemy wyspę, typ uporządkowania i domenę sieci?](02-order-types-and-domains.md)
