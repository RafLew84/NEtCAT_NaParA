# Jak rozdzielać domeny o tym samym typie i orientacji?

ID: 12
Type: prototype
Labels: wayfinder:prototype
Mode: HITL
Status: claimed
Assignee: Codex — domains/phase-boundaries
Parent: [STM Domains — etap 2: metody i zapis wyników](../map-methods-and-save.md)
Blocked by: 04, 05

## Question

Jaka informacja pozwoli wykryć wyraźną linię niedopasowania między obszarami
tego samego typu i orientacji, bez dzielenia jednej domeny przez pojedyncze
defekty? Sam kąt i rozstaw nie ustalają ciągłości wzoru.

[Pilotaż](../method-comparison-pilot.md) wyznaczył 3 lub 5 komponentów sąsiedztwa
zamiast zadanych dwóch i tworzył komponenty przy brzegu. Potrzebna jest próba
cech wrażliwych na przesunięcie/fazę wzoru albo lokalne niedopasowanie sieci,
z referencją przebiegu granicy. Wybór konkretnej metody pozostaje otwarty.

Kontrole obejmują jednorodne przesunięcie całego obrazu (bez nowej domeny),
granicę niedopasowania, izolowane defekty, pas bez uporządkowania i realną
przerwę materiału. Oddzielmy wykrycie granicy od określenia typu i orientacji.
Nie traktujemy automatycznie punktów poniżej progu jako pasa nieporządku.
Gradient orientacji nadal nie jest wymaganym scenariuszem pierwszych prób.

Wynik: nakładki granic/obszarów do oceny przez użytkownika, pomiary błędnych
scaleń i podziałów oraz błędu granicy na referencjach. Małe i ucięte obszary
zachowują informację o ograniczeniach. Jeśli materiał nie pozwala rozstrzygnąć
granicy, wynik ma to ujawnić. Komponenty punktów nie wystarczają do zatwierdzenia
powierzchni domen. Zapisujemy parametry, koszt i ograniczenia.

## Dependencies

- [Jakie referencje i kryteria potwierdzą wiarygodność analizy?](04-reference-and-quality.md)
- [Jak porównać metody wykrywania wysp i domen w serii?](05-stable-types-across-frames.md)


## Work started — 2026-10-21

Na bezpośrednie polecenie użytkownika wykonujemy lokalną próbę przed pełnym
odbiorem 04. Korzystamy z zaakceptowanych 18 klatek / 54 wnętrz oraz kontroli
syntetycznych z dokładnie znaną granicą. Kolory referencji oznaczają głównie
różne orientacje tej samej sieci; nie są referencją granicy przesunięcia przy
identycznej orientacji. Pomiar błędu takiej granicy oprzemy na kontrolach,
a we wnętrzach TTMAPP pokażemy lokalne wskazania i zakres braku danych.

Porównujemy kąt sąsiedztwa, niedopasowanie wektorów sieci i lokalną fazę obrazu.
Typ, orientacja, granica oraz brak wiarygodnego pomiaru pozostają rozdzielone.
Prototyp: `prototype/stmdomains-boundaries`; nie scalać do aplikacji.
