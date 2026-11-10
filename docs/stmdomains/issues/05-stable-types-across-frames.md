# Jak porównać metody wykrywania wysp i domen w serii?

ID: 05
Type: prototype
Labels: wayfinder:prototype
Mode: HITL
Status: resolved
Assignee: Codex — domains/method-comparison
Parent: [STM Domains — etap 2: metody i zapis wyników](../map-methods-and-save.md)
Blocked by: 01, 02

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

## Discussion — 2026-10-19

Na bezpośrednie polecenie użytkownika podejmujemy prototyp przed odbiorem
szkieletu i rozstrzygnięciem referencji jakości. Zależność od referencji
pozostaje jawna; sama próba działania nie jest walidacją naukową. Prototyp
powstaje na osobnej gałęzi, bez zmian produkcyjnego kodu aplikacji.

## Answer — 2026-10-19

**Wynik: zakończony pilotaż wskazujący konkretne braki, bez wyboru metody.**
Po otrzymaniu prototypu i opisu braków użytkownik polecił dopisać tickety
do dalszej analizy. Nie jest to akceptacja skuteczności segmentacji.

W odpowiedzi na pytanie o procedurę użytkownik wybrał: **katalog ustalamy
wspólnie dla całego wybranego zakresu**. Nie zamrażamy go na podzbiorze
klatek referencyjnych. W prototypie katalog jest osobny dla każdej metody;
zmiana zakresu lub parametrów wymaga nowej próby. Numery klastrów z różnych
prób nie oznaczają automatycznie tych samych typów.

[Raport pilotażu](../method-comparison-pilot.md) identyfikuje dane, parametry,
wyniki, koszt i ograniczenia. Lokalny plik do otwarcia w przeglądarce:
`/home/rlew/projekty/NEtCAT-domains/.scratch/method-comparison/pilot.html`.
Źródło: commit `f9ea1d602a8c2bcd1bc5eb410765706d2ae43fca` na osobnej gałęzi
`prototype/stmdomains-method-comparison`, katalog `stmdomains/prototypes/`.
Kod prototypu nie jest scalany do aplikacji; dane i wygenerowany HTML są poza Git.

Porównano gęstość centrów i Chan–Vese dla pokrycia, a dla struktur lokalne
cechy sąsiedztwa i FFT. Kontrole ujawniły mieszanie różnego rozstawu w jednym
typie, podziały na brzegach i niepoprawny wynik dla granicy niedopasowania.
Zmiana skali silnie zmienia wyniki. Powtarzanie daje identyczne przypisania,
a anulowanie nie przyjmuje częściowego katalogu. Nie zwalidowano skuteczności
na TTMAPP, rzadkich typów ani kosztu/anulowania pełnej serii.

Braki przechodzą do nowych pytań:

- [Jak wyznaczać pokrycie bez mylenia luk oznaczeń z podłożem?](10-coverage-and-scale.md)
- [Jak rozpoznawać typy przy obrocie, zmianie rozstawu i rzadkich wzorach?](11-structural-type-catalogue.md)
- [Jak rozdzielać domeny o tym samym typie i orientacji?](12-phase-boundaries.md)
- [Które metody i warunki odmowy wyniku przyjmujemy po próbach?](13-method-acceptance.md)

[Referencje i kryteria jakości](04-reference-and-quality.md) pozostają otwarte.
Pierwotną zależność od nich przeniesiono z zakończonego pilotażu do dalszych
prób i odbioru metod. To jawne ograniczenie rozstrzygnięcia do wskazania luk,
nie uznanie brakującej walidacji za wykonaną. Zapis wyników będzie zależał
od odbioru metod, więc samo zamknięcie tego pilotażu nie otwiera drogi do
utrwalenia obecnych klastrów jako zatwierdzonych typów materiału.
