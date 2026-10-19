# Jak porównać metody wykrywania wysp i domen w serii?

ID: 05
Type: prototype
Labels: wayfinder:prototype
Mode: HITL
Status: open
Assignee:
Parent: [STM Domains — etap 2: metody i zapis wyników](../map-methods-and-save.md)
Blocked by: 01, 02, 04

## Question

Jakie metody potrafią na uzgodnionych danych wykrywać pokrycie/wyspy oraz
spójne domeny orientacji i uporządkowania sieci, zachowując znaczenie typów
na kolejnych klatkach?

Na odebranym szkielecie porównajmy małą liczbę kandydatów z przeglądów:
prosty model regionów i level set dla pokrycia oraz cechy lokalnej tekstury
lub sąsiedztwa dla sieci. Wybór kandydatów wynika z referencji i jakości wejścia;
SBC/MatID, FFT/Gabor, analiza grafu i level set pozostają możliwościami,
a nie obowiązkową listą funkcji. Pomiar orientacji pojedynczej molekuły nie
jest warunkiem rozpoczęcia tych prób.

Prototyp ma umożliwić wybór klatki lub zakresu, parametrów i metody oraz
obejrzenie nakładek wyników na obraz. Oddzielmy maskę pokrycia, identyfikatory
wysp, typy i domeny sieci, orientacje sieci oraz brak wiarygodnego wyniku.
Użytkownik ocenia wyniki na przykładach; nie wystarczy samo uruchomienie kodu.

Punktem odniesienia są
[uzgodnione definicje i przypadki graniczne](02-order-types-and-domains.md#answer--2026-10-19).
Typ nie jest przedziałem orientacji. Próba musi też pokazać, czy metoda potrafi
rozróżnić domeny o tym samym typie i orientacji rozdzielone linią niedopasowania;
samo podobieństwo kąta i rozstawu nie potwierdza poprawnego scalenia.

Jak ustalamy typy w serii: wspólna analiza wybranego zestawu, referencja z części
klatek czy inna procedura? Co z nowym wzorem, rzadkim typem, ponownym obliczeniem
oraz zmianą parametrów? Numery niezależnych klastrów nie ustalają wspólnego
znaczenia. Nie dodajemy śledzenia konkretnych domen.

Oceńmy jakość, koszt, pamięć, anulowanie i powtarzalność na danych z ticketu
referencji. Rozstrzygnięcie określa metodę popartą wynikami albo konkretną lukę
wymagającą dalszej próby. Linkujemy materiały porównawcze, parametry i ograniczenia.
Prezentacja tych eksperymentów rozwija podstawowy podgląd z pierwszego etapu;
nie uzależnia jego odbioru od skuteczności detekcji.

Kontekst: [przegląd metod](../research-general-domain-detection.md),
[level set i analiza sieci](../research-domain-detection-level-sets.md).

## Dependencies

- [Jak zapis wejściowy odtwarza obrazy, oznaczenia i rejestrację?](01-import-and-geometry.md)
- [Jak definiujemy wyspę, typ uporządkowania i domenę sieci?](02-order-types-and-domains.md)
- [Jakie referencje i kryteria potwierdzą wiarygodność analizy?](04-reference-and-quality.md)
