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
warunkuje dalsze próby i odbiór metod, pomimo zakończenia samego pilotażu.

Kontekst: [proponowane kryteria domen](../research-general-domain-detection.md),
[protokół dla wysp i orientacji sieci](../research-domain-detection-level-sets.md).

## Materiał do przygotowania referencji — 2026-10-21

[Wstępna próba pokrycia i skali](../coverage-and-scale-pilot.md) wykazała,
że same centra nie określają warstwy w lukach oznaczeń, a warianty obrazowe
potrafią przypisać około połowy pustego, zaszumionego podłoża do materiału.
Użytkownik zaakceptował dalszą próbę z referencjami i może posiadać klatki
referencyjne; ich lokalizacja i status oznaczeń pozostają do ustalenia.

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

## Dependencies

- [Jak definiujemy wyspę, typ uporządkowania i domenę sieci?](02-order-types-and-domains.md)
