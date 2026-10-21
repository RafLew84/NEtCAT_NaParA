# Czy lokalna tekstura STM pozwala znaleźć domeny bez przykładów?

ID: 17
Type: prototype
Labels: wayfinder:prototype
Mode: HITL
Status: open
Assignee:
Parent: [STM Domains — etap 2: metody i zapis wyników](../map-methods-and-save.md)
Blocked by: 14

## Question

Czy obraz uzupełnia brakujące centra i ujawnia orientacje oraz
rozstaw bez etykiet domen? Porównać lokalną autokorelację/widmo z EWT,
inspirowanym bezpośrednią publikacją STM z przeglądu.

Cechy pobierać na regularnej siatce całego pola, w kilku skalach. Dodatkowy
wariant pomiaru przy centrach pozwoli ocenić znaczenie oznaczeń. Nie wybierać
okien według poprzednich domen MolTrack. Energię, rozstaw i orientację
traktować osobno; sama jasność nie jest rozpoznaniem struktury.

Oryginalny wariant EWT z zadanym `K` może być porównaniem, lecz nie spełnia
warunku docelowego. Próba samodzielnego znajdowania grup musi dopuścić
jedną grupę i brak wiarygodnego porządku. Zamiana końcowego grupowania jest
naszą adaptacją wymagającą sprawdzenia. Przetestować pasy skanowania,
odwrócenie kontrastu i obszary z ubytkami oznaczeń. Użycie level set do
poprawy konturu rozważyć dopiero po uzyskaniu wiarygodnej informacji
o strukturze; nie rozwiązuje on sam wyboru i istnienia domen.

Pokazać osobno wyniki pomiaru na siatce i przy centrach. Usunięcie samych
oznaczeń nie może zmieniać wariantu korzystającego wyłącznie z obrazu.
Zestawić wpływ okna, kontrastu, skali, rzadkiego wzoru i rozszerzenia zakresu
na katalog. Porównać z wynikami innych kandydatów, gdy będą dostępne,
bez uzależniania wykonania tej próby od ich powodzenia.

## Propozycja porównania ML bez własnego treningu

[Przegląd z 2026-10-21](../research-training-free-ml-domain-discovery.md)
uzasadnia dodatkowe porównanie cech wczesnych warstw gotowej FCN–ResNet101
(bezpośredni precedens STM) i zamrożonego DINOv2 ViT-S z autokorelacją/EWT.
DINOv3 ViT-S pozostaje opcjonalnym rozszerzeniem, zależnym od dostępu do
wag. To propozycja próby; nie potwierdzono jakości tych cech na TTMAPP.

Sieci tylko wyliczają lokalne opisy obrazu: bez treningu wag, głowicy
klasyfikacyjnej ani przykładów domen. Grupowanie nadal dopasowuje się
do nieoznaczonych danych. Cechy pobierać na siatce i, osobno, przy
dostarczonych centrach. Oba warianty pozostają w tym tickecie;
[krok 15](15-local-neighborhood-domains.md) zachowuje bazę geometryczną.

Przy porównaniu reprezentacji stosować wspólny sposób grupowania,
łączenia przestrzennego i oceny uporządkowania, z jawnym doborem skali
parametrów. Sprawdzić wpływ rozdzielczości cech oraz skalowania wejścia
na rozstaw, orientację i granice przesunięcia. Model i wagi, przygotowanie
obrazu, czas oraz pamięć wymagają zapisu. SAM i autoenkodery wymagające
własnego treningu nie są warunkiem tej próby.

## Dane i kryteria porównania

Obowiązuje [wspólne wejście, kontrole i format oceny](14-unsupervised-input-and-controls.md).
Analiza obejmuje całe pola klatek, bez ramek domen na wejściu; częściową
referencję odsłaniamy po zapisaniu predykcji. Powtórzenie ze zmienioną lub
usuniętą referencją ma zachować identyczny wynik analizy. Parametry i źródła
ich doboru są jawne, bez dopasowywania liczby grup do BLACK/RED/YELLOW.

Ocenić zero/jedną/wiele domen, fałszywy porządek, scalenia/podziały, odmowy,
braki detekcji i stabilność zakresu. Nie wymuszać domeny na szumie ani nie
zaliczać odrzucenia wszystkich danych jako sukcesu. Spójność klastra,
rozpoznanie struktury i powierzchnia materiału pozostają odrębne.

## Wynik do omówienia

Odtwarzalny prototyp, pełne nakładki klatek, tabela wspólnych kontroli,
przypisania i odmowy oraz raport z parametrami, wersjami, kosztem i pamięcią.
Wynik syntetyczny rozdzielić od ograniczonej oceny częściowych referencji
TTMAPP. Nie deklarować dokładności nieoznaczonych fragmentów ani granic,
których referencja nie określa.

Omówić z użytkownikiem, czy kierunek zasługuje na dalsze rozwijanie i jakie
ograniczenia zostają. Udokumentowany wynik negatywny także odpowiada na to
pytanie. Zakończenie próby nie zatwierdza metody produkcyjnej; ten wybór
pozostaje w [odbiorze metod](13-method-acceptance.md). Kod prototypu oraz
lokalne duże wyniki nie stają się automatycznie częścią aplikacji.

## Dependencies

- [Jak przygotować wspólne wejście i kontrole bez narzucania domen?](14-unsupervised-input-and-controls.md)

## Kontekst

- [ML i deep learning bez własnego treningu](../research-training-free-ml-domain-discovery.md)
- [Przegląd samodzielnego wyszukiwania domen w STM/AFM](../research-stm-afm-unsupervised-domain-discovery.md)
- [Przegląd domen i grupowania obiektów](../research-domain-discovery-and-object-clustering.md)
