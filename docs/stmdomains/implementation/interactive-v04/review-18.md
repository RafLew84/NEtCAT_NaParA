# SD-V4-18 — przegląd implementacji

2026-11-04, skill `code-review`, dwie niezależne osie w równoległych agentach.
Baza: `e4fb4aa`; implementacja `85a90e0`, poprawki `d7ea7b2`.
Diff: `git diff e4fb4aa...HEAD`.
Spec: [ticket 18](18-compare-freud-environments.md), wybrany
[Panel A](prototype-18-layouts.md), [protokół](experiment-18.md).
Standardy: root i app AGENTS.md, PARALLEL_DEVELOPMENT.md, GLOSSARY.md,
wspólne kryteria planu oraz heurystyki skilla. Brak osobnego
CODING_STANDARDS.md/CONTRIBUTING.md.

## Standards

Pierwszy przegląd: **0 naruszeń udokumentowanych zasad, 1 sugestia P3**.
Możliwe Duplicated Code: `freud_domains.py` i `geometry_domains.py`
powtarzały budowanie parametrów, kalibracji i pochodzenia wyniku. Ryzyko:
przyszła zmiana formatu pomiaru trafi tylko do jednej metody. Sugestia
wydzielenia małego wspólnego konstruktora, bez ogólnego frameworka.
To ocena utrzymaniowa, nie błąd działania ani twarde naruszenie.

**Zamknięte w `d7ea7b2`:** `measured_domain_provenance` jest używane
przez obie metody, freud dodaje własne parametry. Agent potwierdził,
że refaktor zachowuje dotychczasowe znaczenie danych.
Zakres aplikacji, podział modułów, rozróżnienie eksperymentu od odbioru
i dokumentowanie zależności oceniono bez innych materialnych uwag.

## Spec

Pierwszy przegląd: **1 potwierdzona uwaga P2**. Wymaganie: „Jawnie
wybrano i zapisano sposób traktowania obrotu”. `registration=True`
uruchamia dopasowanie 3D freud, także dla `Box.is2D=True`. W UI i protokole
mówiono wyłącznie o obrocie, chociaż rejestracja łączy też odbicia lustrzane
płaskich otoczeń. Odtworzono na asymetrycznych wektorach `(1,0), (0.3,1.3),
(-1,0.2), (-0.2,-0.9)` i ich odbiciu względem Y przy tolerancji 0,01:
bez rejestracji różne klasy, z rejestracją jedna klasa.

**Zamknięte w `d7ea7b2`:** opcja „Dopasuj obrót lub odbicie otoczeń”,
opis szczegółów i `registration_transform` w metadanych ujawniają tę
symetrię. Dodano regresję prawdziwej biblioteki oraz uściślenie protokołu.
Agent ponownie sprawdził diff i test (PASS). Nie zmieniono zamrożonego
sposobu obliczeń ani wyników domyślnych bez rejestracji.
Brak innych materialnych braków lub niezamówionego zakresu.

## Sprawdzenia po uwagach

Pełna regresja przed poprawkami: **557 PASS / 256,20 s**. Po poprawkach:
**28 testów obu metod PASS / 27,84 s**, w tym nowa regresja symetrii oraz
wzmocniona regresja zachowania sąsiadów po zmianie raw/aligned (RED→GREEN).
Mypy: **105 modułów PASS**. Natywne GUI X11/netcat ponownie PASS na 259;
wcześniejszy pełny przebieg obejmował 9 kontroli i TTMAPP259–266.
23 zmienione pliki kodu/testów <1000 linii, maksimum 862; linki i graf
27 ticketów sprawdzone. [Raport i odbiór ręczny](acceptance-18.md).

Standards: **0 otwartych** (P3 zamknięta). Spec: **0 otwartych** (P2 zamknięta).
