# Jak rozdzielać domeny o tym samym typie i orientacji?

ID: 12
Type: prototype
Labels: wayfinder:prototype
Mode: HITL
Status: resolved
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


## Answer — 2026-10-21

Zakończono [próbę granic przesunięcia](../phase-boundaries-trial.md): 7 wariantów,
19 kontroli syntetycznych oraz 18 klatek / 54 wnętrza TTMAPP. Status `resolved`
oznacza wykonany eksperyment, **bez zatwierdzenia metody produkcyjnej**.
Prototyp i nakładki przygotowano do oceny użytkownika; nie deklarujemy, że
zaakceptował już wynik lub parametry.

Niedopasowanie wektorów między centrami do oszacowanej sieci rozdziela
kontrolne domeny o tym samym typie i orientacji przy przesunięciu 4/8 px,
również na granicy skośnej. Zachowuje jeden obszar po globalnym przesunięciu,
pojedynczych defektach i ucięciu brzegiem. Sam kąt nie wykrywa tych granic.
To wynik na prostych kontrolach z dokładnymi centrami, nie walidacja na STM.

Metoda nie wykrywa przesunięcia 1 px i myli przerwę detekcji z rozłączeniem
domen. Wymaganą estymatę dwóch wektorów sieci uzyskano tylko w 7/54 wnętrz
TTMAPP. Prosta faza obrazu tworzy wielokrotne cięcia, zależy od kontrastu
i okna; filtrowanie krótkich wskazań usuwa również część rzeczywistych granic.
Zmiana orientacji unieważnia założenie wspólnej sieci użyte w tych wariantach.

Raport zawiera błędy scaleń/podziałów i położenia wskazań na kontrolach,
liczby przed/po cięciu, dostępność, parametry oraz koszt. Komponenty grafu
nie są maskami powierzchni domen. Brak wiarygodnego pomiaru pozostaje brakiem
danych, a nie automatycznym pasem nieporządku. Nie liczono dokładności granic
TTMAPP: obecne ramki opisują głównie orientacje i mają przybliżone kontury.

Dalszy kierunek: porównanie wektorów pomiędzy centrami w obszarach z wiarygodną
siecią i orientacją, po rozwiązaniu luk z kroku 11. Nie przyjęto fazy obrazu
jako samodzielnego detektora. Konkretne ograniczenia przekazano do
[odbioru 13](13-method-acceptance.md). Obecne referencje wystarczają do dalszych
lokalnych prób; późniejszy pomiar błędu rzeczywistej granicy będzie wymagał
wskazanego przykładu niedopasowania przy tym samym kącie i tolerancji oznaczenia.
Brak takiej referencji nie pozostawia wykonanego eksperymentu otwartym.

## Prototype and inspection

Źródła: **`prototype/stmdomains-boundaries`, `c33cc5b`** — nie scalać do aplikacji.
Lokalny podgląd:
`/home/rlew/projekty/NEtCAT-domains/.scratch/phase-boundaries-trial/index.html`.
Obok JSON, CSV i inspekcje. Polecenie odtworzenia jest w raporcie oraz
`stmdomains/prototypes/phase_boundaries_README.md` na gałęzi prototypu.

W HTML porównaj „Granica 4 px”, „Jeden defekt”, „Pas bez detekcji”,
„Odwrócenie kontrastu” i „Klatka 258”. Liczby grafów przed cięciem pokazują,
kiedy rozłączenie istniało już z powodu braku danych. Gamma i nakładki
zmieniają tylko podgląd; wyniki są zapisane w prototypie.

Sprawdzono geometrię wejścia i wsparcia pomiarów, metryki par niezależnym
wyliczeniem oraz niezmienność przy zmianie obrazu poza referencją i usunięciu
samych centrów. QtWebEngine: 37 przypadków, 24 kroki scenariuszy; brak błędów JS.
Koszt generatora 3,91 s przed końcowym zapisem JSON/CSV, 588,59 MiB RSS.
Nie zmieniano aplikacji ani nie uruchamiano jej testów.
