# Czy otoczenie zaznaczonych molekuł pozwala samodzielnie znaleźć domeny?

ID: 15
Type: prototype
Labels: wayfinder:prototype
Mode: HITL
Status: resolved
Assignee: Codex — domains/orientation-trial
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
tę próbę”**. Status pozostawał wtedy `claimed`; nie przyjęto zakończenia pytania
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

Status pozostał `claimed`; użytkownik następnie polecił wykonać badanie
orientacji i łączenia opisane poniżej. Katalog rozstawów nadal jest osobną luką.

## Kontynuacja — orientacja i łączenie, 2026-10-23

[Raport badania](../orientation-and-joining-trial.md): 31 wariantów na
24 pełnych klatkach i 204 kontrolach. Porównano dawny wybór symetrii,
pełny rozkład kierunków i lokalną komórkę sieci. Powtarzalność, minimum
8 elementów i dawny katalog pozostają stałe; główny wynik ocenia obszary
bez warunku typu, a katalog jest osobnym porównaniem.

Wybór na kontrolach rozwojowych wskazał komórkę ze zgodnością wobec startu
obszaru. Przy 30% braków daje jedną domenę i 81.9% przypisań zamiast
2–3 fragmentów i 46.7%. Na TTMAPP: 70.7% zamiast 62.5%, scalenia 0/3801
ocenianych par różnych regionów zamiast 708/2329. Poprawa nie jest
równomierna: RED spada z 28/101 do 14/101 przypisań. Granica przesunięcia
z błędem centrów ma 98.1% scaleń przypisanych par; wygięta sieć jest
nadmiernie dzielona. Sama kontrola fazy na krawędziach nie naprawia granicy.

Podgląd: `/home/rlew/projekty/NEtCAT-domains/.scratch/orientation-and-joining/index.html`.
Źródła: `prototype/stmdomains-orientation`, commit `2b70d0d`, baza `bc3763e`.
Sprawdzono odtworzenie 204 wcześniejszych wyników, 1368 wyników zgodnych
z kontraktem, obrót 37° na czterech kontrolach, kontrast i skalę oraz
14 kontroli HTML bez błędów JS. Pełne powtórzenie bez referencji i ze
zmianą kolejności opisano w raporcie.

Po tej próbie issue 15 pozostawało `claimed` do omówienia. Komórka jest
użytecznym punktem odniesienia, nie gotową metodą produkcyjną. Proponowano
porównanie 16 z zachowaniem nowych trudnych kontroli i osobną oceną
RED/YELLOW. Decyzja użytkownika o przejściu do 16 jest poniżej;
odbiór 13 nadal pozostaje otwarty.

## Dependencies

- [Jak przygotować wspólne wejście i kontrole bez narzucania domen?](14-unsupervised-input-and-controls.md)

## Kontekst

- [Przegląd samodzielnego wyszukiwania domen w STM/AFM](../research-stm-afm-unsupervised-domain-discovery.md)
- [Przegląd domen i grupowania obiektów](../research-domain-discovery-and-object-clustering.md)

## Answer — 2026-10-23: przejście do porównania SBC

Po trzech eksperymentach użytkownik polecił przejść do issue 16. Zakończono
15 jako porównanie i punkt odniesienia; nie przyjęto metody do aplikacji.
Ograniczenia granic przesunięcia, RED/YELLOW i deformacji pozostają w
[raporcie orientacji i łączenia](../orientation-and-joining-trial.md).
