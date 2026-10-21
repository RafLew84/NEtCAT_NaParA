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

Zestaw przypadków wynika z
[uzgodnionych definicji i przykładów](02-order-types-and-domains.md#answer--2026-10-19):
obejmuje m.in. obrót bez zmiany typu, różny rozstaw, pas bez uporządkowania,
granicę niedopasowania przy tym samym typie i orientacji, małe skupiska oraz
ucięcie brzegiem. Płynny gradient orientacji nie jest wymaganym scenariuszem
pierwszych prób. Trzeba osobno oceniać odmowę pomiaru i brak wykrytego porządku.

Jakie błędy kątów, nadmierne podziały, błędne scalenia, niestabilność typów,
fałszywe domeny i odmowy pomiaru są istotne dla użytkownika? Jak raportować
wyniki dla małych typów, ubytków oznaczeń i domen uciętych krawędzią?

Rozstrzygnięcie określa wejścia, sposób oznaczania, pomiary jakości i progi lub
procedurę ich ustalenia. Jeśli brakuje danych, wskazuje konkretny brak do zdobycia,
zamiast uznawać metodę za skuteczną bez referencji.

To odbiór metod drugiego etapu; nie jest warunkiem odbioru szkieletu.

[Wykonany wcześniej na polecenie użytkownika pilotaż](../method-comparison-pilot.md)
wskazuje konkretne przypadki do referencji: skąpe oznaczenia w klatce 68,
rozbieżne maski pokrycia i kontrolną granicę przesunięcia. Nie dostarcza
niezależnej prawdy odniesienia TTMAPP ani progów jakości. To pytanie nadal
warunkuje pełny odbiór metod. Dalsze lokalne próby na dostarczonej referencji
są dopuszczone decyzją użytkownika opisaną poniżej.

Kontekst: [proponowane kryteria domen](../research-general-domain-detection.md),
[protokół dla wysp i orientacji sieci](../research-domain-detection-level-sets.md).

## Materiał do przygotowania referencji — 2026-10-21

[Wstępna próba pokrycia i skali](../coverage-and-scale-pilot.md) wykazała,
że same centra nie określają warstwy w lukach oznaczeń, a warianty obrazowe
potrafią przypisać około połowy pustego, zaszumionego podłoża do materiału.
Użytkownik zaakceptował dalszą próbę z referencjami. Następnie wskazał
częściowo oznaczone klatki; ich zakres opisano w uzupełnieniu poniżej.

Pokrycie ma obejmować materiał na dowolnym widocznym poziomie warstwy.
Ciemne miejsca mogą odsłaniać niższą warstwę, ale gdy molekuł nie widać
oraz brak innych wystarczających przesłanek, pozostają nierozstrzygnięte.
Potrzebne są osobne oznaczenia pewnego materiału, pewnego podłoża i niepewności,
a nie binarna interpretacja „jasne = materiał”. Nowe przypadki kontrolne
obejmują wielopoziomowość, sam szum, ubytki centrów, otwory i małe wyspy.

W `.scratch/coverage-and-scale/reference-candidates/` są podglądy ośmiu klatek
bez nakładek i manifest geometrii; **nie są to niezależne referencje**.
Należy uwzględnić, że użytkownik oglądał już propozycje masek, oraz ustalić
sposób ograniczenia ich wpływu na referencję i niezależny zbiór sprawdzający.
Ten materiał nie zamyka niniejszego pytania ani nie ustanawia progów jakości.

## Dostarczone częściowe referencje — 2026-10-21

[Audyt klatek 250–268](../partial-domain-reference-audit.md) obejmuje 18 par
czystych/ręcznie oznaczonych PNG z `data/ttmapp_frames_250_268_domain_review`.
Użytkownik potwierdził przybliżone granice wybranych całych widocznych domen;
nie oznaczył pozostałych obszarów. Poza ramkami mogą występować takie same
wzory. Nie traktować tego otoczenia jako negatywnych przykładów lub podłoża.

Zweryfikowano zgodność PNG z MPP i rejestracją, przygotowano robocze wnętrza
w obu układach. Nie są to pełne referencje pokrycia ani dokładne granice.
Kolory nie definiują samodzielnie typów sieci. Stare raporty obejmują też
klatkę 255, której nie ma w tym folderze; nie włączono jej z domysłu.
Wcześniej używany temporalny holdout nie jest nowym niezależnym testem.

Pozostają: pewne podłoże, obszary nierozstrzygnięte, tolerancja przybliżonych
granic, podział do strojenia/sprawdzenia oraz kryteria jakości. Status pytania
nadal `open`; przyjęcie częściowej referencji nie zamyka całego protokołu.

Użytkownik 2026-10-21 potwierdził użycie obecnego zbioru na najbliższe próby.
Nowe referencje przygotuje w razie wykazanej potrzeby. Powyższe braki nie są
listą anotacji wymaganych przed rozpoczęciem lokalnych porównań: najpierw
wykorzystujemy oznaczone fragmenty, a ewentualną prośbę o uzupełnienie wiążemy
z konkretnym nierozstrzygniętym przykładem i celem pomiaru.

## Konkretna potrzeba po próbie granic — 2026-10-21

[Próba kroku 12](../phase-boundaries-trial.md) zmierzyła błędy granicy na
kontrolach syntetycznych; nie przypisała dokładnej prawdy przybliżonym ramkom
TTMAPP. Kolory oznaczają głównie różne orientacje, zgodnie z wyjaśnieniem
użytkownika. Do późniejszej oceny granicy przesunięcia przy tym samym typie
i kącie potrzebny będzie wskazany rzeczywisty przykład z linią/tolerancją
i fragmentami po obu stronach. Nie jest to warunek zamknięcia wykonanej próby
ani rozpoczęcia kolejnych lokalnych sprawdzeń na obecnych wnętrzach.

## Rola w nowych próbach samodzielnego wykrywania — 2026-10-21

[Wspólne wejście i kontrole](14-unsupervised-input-and-controls.md) oraz
trzy próby metod wykorzystują obecne dane, bez oczekiwania na rozstrzygnięcie
całego niniejszego pytania. To rozdzielenie przygotowania porównania od
pełnego protokołu jakości, nie rezygnacja z walidacji.

Nowa analiza obejmuje pełne pola klatek. Dotychczasowe ramki ograniczają
wyłącznie późniejszą ocenę, nie wejście ani miejsca poszukiwania domen.
Nie służą do uczenia klas, doboru liczby grup lub zakresu sąsiedztwa.
Poza ramkami brak prawdy odniesienia; wyjście poza nie nie jest samo w sobie
błędem. Te referencje były już używane i nie są niezależnym testem.

W pełnym protokole uwzględnić fałszywe domeny na kontrolach bez porządku,
przypadek jednej domeny, rozdzielność odmów i błędów, zmianę zakresu oraz
wpływ braków oznaczeń. Potrzebę nowych referencji uzasadniają konkretne
wyniki prób. Pytanie pozostaje `open` i nadal blokuje pełny odbiór metod;
nie blokuje przygotowania zestawu ani trzech wstępnych porównań.

## Dependencies

- [Jak definiujemy wyspę, typ uporządkowania i domenę sieci?](02-order-types-and-domains.md)
