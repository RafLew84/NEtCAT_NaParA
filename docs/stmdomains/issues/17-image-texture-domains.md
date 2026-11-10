# Czy lokalna tekstura STM pozwala znaleźć domeny bez przykładów?

ID: 17
Type: prototype
Labels: wayfinder:prototype
Mode: HITL
Status: resolved
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

## Punkt odniesienia dla porównania ML

Na polecenie użytkownika z 2026-10-21 wcześniejszą propozycję ML wydzielono
do [przygotowania gotowych cech](18-frozen-feature-preparation.md) i
[porównania domen z tych cech](19-frozen-feature-domains.md). Ten ticket
zachowuje autokorelację/EWT jako klasyczny punkt odniesienia; jego wykonanie
nie czeka na modele ani ich wagi. Wynik przygotować do ponownego porównania:
zapisane cechy i pozycje, konfiguracja grupowania, reguła przestrzennej
łączności oraz ocena porządku. Wynik negatywny też jest użytecznym punktem
odniesienia. [Próba otoczenia molekuł](15-local-neighborhood-domains.md)
zachowuje niezależne porównanie geometrii.

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


## Answer — 2026-10-23

Wykonano [porównanie tekstury](../image-texture-domains-trial.md): lokalne
widmo/autokorelacja i EWT, siatka/centra, 32 konfiguracje na 228 próbkach.
Przygotowano [audyt publikacji i API](../research-image-texture-adaptation-audit.md),
pełne cechy, banki, katalogi, przypisania, odmowy i samodzielny podgląd:
`/home/rlew/projekty/NEtCAT-domains/.scratch/image-texture-domains/index.html`.
Źródła: `prototype/stmdomains-texture`, commit `3bb4d36`, baza `e6d3fbc`.
Kod eksperymentu nie trafia do aplikacji.

Wybrane na syntezie warianty przypisują na częściowej referencji TTMAPP
0.3–5.8% centrów, bez RED/YELLOW. Bramkę porządku przechodzi tylko
9.2–12.6% ocenianych miejsc; EWT wcześniej tworzy jedną grupę całego
zakresu. Na kontrolach EWT scala 8° i część granic przesunięcia, a widmo
na siatce dzieli jedną sieć na trzy. Odmowa na losowych kontrolach jest
poprawna, ale nie równoważy odmowy na rzeczywistym uporządkowaniu.
Zamrożony filtr doboru pomijał podziały pojedynczej sieci; opisano tę lukę
bez poprawiania rankingu po referencji.

Potwierdzono identyczność cech i wyników obrazowych na 228 próbkach po
usunięciu wszystkich oznaczeń i referencji. Oceniono braki, kontrast,
inwersję, skalę i ponowne dopasowanie banku/katalogu dla 5 → 24 klatek.
Walidacja 1824 wyników, 42 kontrole HTML bez błędów JS. Szczegóły, koszt
CPU/pamięci i ograniczenia są w raporcie; nie wykonano testów aplikacji.

Użytkownik zatwierdził: **„Tak — zachowaj porównanie i zamknij 17”**.
Ticket jest `resolved` jako eksperyment, bez przyjęcia metody produkcyjnej.
Cechy i wyniki pozostają punktem odniesienia dla 19/21/22. Następnym krokiem
może być przygotowanie 18, potem porównanie 19; niezależnie pozostaje 20.
Żadnego z tych zadań nie uruchomiono w ramach 17. Odbiór 13 i jakość 04
pozostają otwarte. Level set nie rozwiązuje wykazanych braków rozpoznania.
