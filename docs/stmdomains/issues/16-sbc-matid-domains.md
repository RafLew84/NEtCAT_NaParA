# Czy SBC/MatID odtwarza domeny z niepełnych centrów molekuł?

ID: 16
Type: prototype
Labels: wayfinder:prototype
Mode: HITL
Status: open
Assignee:
Parent: [STM Domains — etap 2: metody i zapis wyników](../map-methods-and-save.md)
Blocked by: 14

## Question

Czy lokalne powtórzenia centrów pozwalają odtworzyć komórki różnych
sieci, a następnie rozdzielić domeny? To transfer metody atomistycznej,
nie potwierdzona metoda dla TTMAPP.

Użyć centrów jako punktów 2D jednej kategorii. Jawnie dostosować skalę,
promienie połączeń, tolerancję pozycji i maksymalny rozmiar komórki; nie
interpretować molekuł jako atomów o domyślnych promieniach w Å. Rejestrować
znalezioną komórkę i wsparcie dla każdego obszaru, także niepowodzenie.

Najpierw sprawdzić zero/jedną/wiele sieci, dwa rozłączne identyczne płaty,
zmianę kolejności punktów, ubytki i szum. Wcześniejszy audyt kodu wskazał
zachowywanie największego komponentu podczas końcowego czyszczenia;
sprawdzić utratę pozostałych fragmentów przed próbą pełnej serii.
Nie przejmować losowego rozstrzygania niepewnych nakładających się regionów
jako pewnej decyzji domenowej: takie miejsca mają pozostać niejednoznaczne.
[Źródło SBC](https://www.nature.com/articles/s41524-024-01498-x),
[audyt kandydata](../research-domain-discovery-and-object-clustering.md).

Oddzielić surowy wynik biblioteki od naszej adaptacji do punktów 2D.
Zestawić odzyskane komórki, orientacje, pozostawione punkty oraz błędy
połączeń/podziałów. Wykazać, czy odtworzenie komórki przekłada się na
poprawne domeny, także przy wspólnym typie i różnej orientacji.

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

- [Przegląd samodzielnego wyszukiwania domen w STM/AFM](../research-stm-afm-unsupervised-domain-discovery.md)
- [Przegląd domen i grupowania obiektów](../research-domain-discovery-and-object-clustering.md)
