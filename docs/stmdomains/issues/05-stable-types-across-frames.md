# Jak odkrywać domeny i zachować stałe typy w całej serii?

ID: 05
Type: prototype
Labels: wayfinder:prototype
Mode: HITL
Status: open
Assignee:
Parent: [STM Domains — specyfikacja analizy typów uporządkowania w serii](../map.md)
Blocked by: 01, 02, 03, 04

## Question

Jakie połączenie opisu sąsiedztwa, orientacji molekuł i podziału przestrzennego
pozwala odkrywać typy uporządkowania bez zamkniętego katalogu oraz nadać im stałe
znaczenie na kolejnych klatkach?

Porównajmy kandydatów z istniejącego przeglądu na uzgodnionych referencjach.
SBC/MatID, wieloskalowe cechy sąsiedztwa i kontrola obrazowa pozostają kandydatami.
Wynik ma rozdzielać klasę podobnych środowisk od spójnego obszaru domeny.

Jak ustalamy typy dla serii: wspólna analiza wybranego zestawu, referencja z części
klatek czy inna procedura? Co dzieje się z typem nieobecnym na pierwszej klatce,
nowym wzorem, bardzo rzadkim typem oraz po ponownym przeliczeniu? Numery lub kolory
z niezależnego grupowania każdej klatki nie gwarantują zgodności znaczenia.

Jaki jest wpływ brakujących orientacji, zmiany parametrów, zakresu analizowanych
klatek i inicjalizacji? Rozstrzygnięcie zawiera wybór metody oraz regułę spójności
typów w serii popartą wynikami. Nie dodaje śledzenia konkretnych domen.

Kontekst: [kandydaci i ograniczenia](../research-general-domain-detection.md),
[istniejące agregaty typów MolTrack](../../../moltrack/analysis/m6_domain_type_aggregates.py).

## Dependencies

- [Jak zapis wejściowy odtwarza obrazy, oznaczenia i rejestrację?](01-import-and-geometry.md)
- [Jak definiujemy typ uporządkowania i pojedynczą domenę?](02-order-types-and-domains.md)
- [Jak mierzyć orientację molekuły i oznaczać wynik niepewny?](03-molecular-orientation.md)
- [Jakie referencje i kryteria potwierdzą wiarygodność analizy?](04-reference-and-quality.md)
