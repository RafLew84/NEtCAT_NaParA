# Jak wyznaczać pokrycie bez mylenia luk oznaczeń z podłożem?

ID: 10
Type: prototype
Labels: wayfinder:prototype
Mode: HITL
Status: open
Assignee:
Parent: [STM Domains — etap 2: metody i zapis wyników](../map-methods-and-save.md)
Blocked by: 04, 05

## Question

Jak wyznaczać cały płat warstwy, zachowując zwykłe odstępy między molekułami,
ale wykluczając większe obszary podłoża, przy niepełnych oznaczeniach i zmiennym
kontraście obrazu? Kiedy należy odmówić wyznaczenia maski?

[Pilotaż](../method-comparison-pilot.md) pokazał m.in. pokrycie 45,5–78,8%
klatki 68 wyznaczone z zaledwie trzech centrów oraz silną zależność Chan–Vese
od wygładzania. Sprawdźmy dobór skali przy rzadkich oznaczeniach, osobno wpływ
poszczególnych parametrów oraz założenie jaśniejszej warstwy. Brak detekcji
nie jest referencją pustego podłoża.

Porównanie ma korzystać z niezależnie oznaczonych granic płata i niepewności
z pytania o referencje. Obejmuje luki oznaczeń, małe wyspy, odsłonięte podłoże,
zwykłe odstępy oraz brzeg obrazu; padding nie jest pomiarem. Dobór kolejnego
wariantu regionowego lub level set wynika z obserwowanych błędów. Jeśli
porównujemy Gibou–Fedkiwa, potrzebna jest jego rzeczywista implementacja;
obecny Chan–Vese nie rozstrzyga jego przydatności.

Wynik: obejrzane przez użytkownika maski, parametry, błędy granic/pokrycia,
błędne scalenia i podziały wysp oraz warunki braku wyniku. Zapisujemy również
koszt, pamięć i ograniczenia. Nie wybieramy wariantu wyłącznie po liczbie wysp.

## Dependencies

- [Jakie referencje i kryteria potwierdzą wiarygodność analizy?](04-reference-and-quality.md)
- [Jak porównać metody wykrywania wysp i domen w serii?](05-stable-types-across-frames.md)
