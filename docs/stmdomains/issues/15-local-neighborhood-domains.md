# Czy otoczenie zaznaczonych molekuł pozwala samodzielnie znaleźć domeny?

ID: 15
Type: prototype
Labels: wayfinder:prototype
Mode: HITL
Status: claimed
Assignee: Codex — domains/recurrence-trial
Parent: [STM Domains — etap 2: metody i zapis wyników](../map-methods-and-save.md)
Blocked by: 14

## Question

Czy geometria dostępnych centrów wystarcza do znalezienia spójnych
obszarów podobnego uporządkowania bez przykładów domen?

1. Zbudować lokalne opisy kilku rozmiarów sąsiedztwa: rozkłady odległości
   i kątów oraz powtarzalność otoczenia. Zachować rozstaw w px; normalizacja
   nie może ukryć różnicy rozstawu. Porównać prosty opis z SOAP, jeśli prosty
   opis nie rozdziela kontrolnych struktur. Nie narzucać liczby sąsiadów
   odpowiadającej jednej symetrii.
2. Grupować opisy we wspólnym katalogu całego wybranego zakresu, bez zadania
   `K`. Kandydatem jest HDBSCAN z dopuszczonym jednym klastrem. Typ ma być
   odporny na obrót; kąt analizować osobno, z symetrią oszacowanej struktury.
3. Łączyć przestrzennie sąsiednie, zgodne obiekty. Oddzielić rozłączne
   fragmenty. Zgodność opisu nie wystarcza: wymagać dowodów powtarzalności
   wykraczających poza kontrole losowe. Nie traktować etykiety „noise”
   algorytmu jako fizycznego nieuporządkowania.

Zapisać osobno wynik grupowania i wynik po ocenie porządku. Mierzyć
nadmierne podziały, scalanie, pozostawione bez przypisania molekuły i wpływ
braków centrów. Warunek zatrzymania: brak ustawień odróżniających kontrole
losowe od regularnej pojedynczej domeny. Nie naprawiać tego ręcznym `K=3`.
Uzasadnienie i biblioteki: [przegląd grupowania](../research-domain-discovery-and-object-clustering.md).

Sprawdzić także rzadki układ, zmianę kolejności i rozszerzenie zakresu
katalogu. Zachować znaczenie typów przy obrocie, a różne rozłączne domeny
tego samego typu liczyć oddzielnie. Wykazać ograniczenia przy granicy
przesunięcia; sama zgodność lokalnego opisu nie potwierdza jej rozpoznania.

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

## Próba wykonana — 2026-10-23, dyskusja trwa

[Raport](../local-neighborhood-domains-trial.md): porównano rozkłady
odległości/kątów i SOAP, promienie 24/36 px, HDBSCAN bez K, osobną ocenę
powtarzalności i przestrzenne składowe. Pełne wejście: 24 klatki TTMAPP
i 132 kontrole; 624 wyniki z jawnymi odmowami. Podgląd:
`/home/rlew/projekty/NEtCAT-domains/.scratch/local-neighborhood-domains/index.html`.

Prosty opis nadmiernie dzieli część kontrolnych struktur; SOAP scala
różne rozstawy. Większe otoczenia odróżniają losowe punkty od jednej
regularnej sieci, ale ubytki centrów pogarszają przypisania i podziały.
Na TTMAPP najwięcej przypisań daje SOAP/36: 31.0% wewnątrz częściowych
referencji, wyłącznie BLACK. RED/YELLOW nie przechodzą kryterium
powtarzalności mimo zwykle wystarczającej liczby sąsiadów. Nie jest to
rozpoznanie fizycznego nieporządku ani dowód nieskuteczności całej rodziny.

Zbadano rzadki układ, zakres 5 → 24, obrót, braki i skalowanie. Powtórzenie
bez referencji dało 624 identyczne pliki; zmiana kolejności — identyczne
przypisania. Raport podaje szczegóły jakości, koszty, wersje i ograniczenia.
Źródła: `prototype/stmdomains-neighborhoods`, commit `1f25b45` (baza
`76dd4a3`), bez scalania prototypu do aplikacji.

Użytkownik po przedstawieniu wyniku wybrał **„Najpierw omówmy lub rozwińmy
tę próbę”**. Status pozostaje `claimed`; nie przyjęto zakończenia pytania
ani przejścia do 16. Następnie polecił zbadać kryterium powtarzalności.

## Kontynuacja — kryterium powtarzalności, 2026-10-23

[Raport kontynuacji](../recurrence-criterion-trial.md): 38 konfiguracji,
24 pełne klatki i 180 kontroli, w tym nowe błędy centrów, odkształcenia
oraz losowe skupiska. Katalog SOAP/36 i reguły przestrzenne zamrożone.
Wybór tylko na kontrolach rozwojowych: promień 36 px, tolerancja 24%
rozstawu, wynik bez gwarantowanego trafienia środka >0.25.

Na częściowych referencjach warunek przechodzi 90.9% oznaczeń zamiast
34.0%, domenę otrzymuje 62.5% zamiast 31.0%. To nie dokładność: 30.4%
przypisanych par z różnych regionów jest błędnie scalonych. RED/YELLOW
nadal odpadają głównie na zbyt małych składowych zgodnych orientacyjnie.
Kontrole losowe: 2/3195 akceptacji, zero składowych; regularne rzędy
z niezależną fazą pokazują ograniczenie samej lokalnej powtarzalności.

Podgląd: `/home/rlew/projekty/NEtCAT-domains/.scratch/recurrence-criterion/index.html`.
Źródła: `prototype/stmdomains-recurrence`, commit `bc3763e`, baza `1f25b45`.
Sprawdzono odtworzenie poprzednich 156 wyników i walidację 1020 nowych
wyników dla pięciu podglądowych wariantów. Dwa powtórzenia bez referencji,
jedno ze zmianą kolejności, dały po 204 identyczne pliki z 38 konfiguracjami.
13 kontroli lokalnego HTML w QtWebEngine, bez błędów JS.

Status nadal `claimed`, bez wyboru metody produkcyjnej i bez przejścia
do 16. Kolejny proponowany eksperyment dotyczy estymacji orientacji,
zgodności lokalnej sieci oraz łączenia sąsiadów, z kontrolą skorelowanych
rzędów, braków, scaleń i podziałów. Samo dalsze obniżanie progu nie
rozwiązuje pozostałych błędów. Katalog rozstawów pozostaje osobną luką.

## Dependencies

- [Jak przygotować wspólne wejście i kontrole bez narzucania domen?](14-unsupervised-input-and-controls.md)

## Kontekst

- [Przegląd samodzielnego wyszukiwania domen w STM/AFM](../research-stm-afm-unsupervised-domain-discovery.md)
- [Przegląd domen i grupowania obiektów](../research-domain-discovery-and-object-clustering.md)
