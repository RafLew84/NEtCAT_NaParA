# Czy SBC/MatID odtwarza domeny z niepełnych centrów molekuł?

ID: 16
Type: prototype
Labels: wayfinder:prototype
Mode: HITL
Status: resolved
Assignee: Codex
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

## Wykonana próba — 2026-10-23

[Raport SBC/MatID](../sbc-matid-domains-trial.md) i
[audyt API](../research-sbc-adaptation-audit.md). Sprawdzono 24 pełne klatki
TTMAPP i 204 kontrole: 6 ustawień, wynik surowy oraz dwie jawne adaptacje.
Bez treningu, K lub ramek na wejściu. Żaden wariant nie spełnia kompletu
warunków; konfigurację podglądu wybrano diagnostycznie na syntezie.

SBC poprawia braki 30% (99.8% przypisań), gładkie odkształcenie i trudną
granicę przesunięcia (0.2% scaleń przy 52.2% przypisań). Jednak scala
różnicę orientacji 8° i przypisuje 355/3195 losowych punktów do pozornych
obszarów. TTMAPP: 63.5% przypisań, 5.9% podziałów i 5.5% scaleń
warunkowych par, wobec 70.7% / 2.8% / 0% poprzedniej komórki.
Wynik zależy też od ziarna wyszukiwania. Nie przyjęto metody do aplikacji.

Podgląd: `/home/rlew/projekty/NEtCAT-domains/.scratch/sbc-matid-domains/index.html`.
Źródła: `prototype/stmdomains-sbc`, commit `e6d3fbc`, baza `2b70d0d`.
W tym checkoutcie: `stmdomains/prototypes/README-sbc.md` i jedno polecenie
odtworzenia. Duże wyniki pozostają lokalne, kod prototypu na osobnej gałęzi.

Pełne powtórzenie bez referencji, ze zmianą kolejności, daje 228 identycznych
wyników. Zapisano 684 wyniki zgodne z kontraktem, komórki i ślady etapów;
sprawdzono kontrast, skalę, obrót, ziarna oraz zależność od kategorii atomowej.
35 kontroli HTML bez błędów JS. Raport podaje zakres, koszty i ograniczenia.

Po obliczeniach status pozostawał `claimed` do omówienia. Zaproponowano:
zachować SBC jako punkt odniesienia i przejść do
[17 — tekstury](17-image-texture-domains.md). Nie uruchomiono kolejnego
issue ani treningu; odbiór 13 pozostaje osobną decyzją.

## Dependencies

- [Jak przygotować wspólne wejście i kontrole bez narzucania domen?](14-unsupervised-input-and-controls.md)

## Kontekst

- [Przegląd samodzielnego wyszukiwania domen w STM/AFM](../research-stm-afm-unsupervised-domain-discovery.md)
- [Przegląd domen i grupowania obiektów](../research-domain-discovery-and-object-clustering.md)

## Answer — 2026-10-23

Po obejrzeniu wyniku użytkownik wybrał: **„Tak — zachowaj porównanie,
następnie issue 17”**. Próba jest zakończona. SBC pozostaje punktem
odniesienia, bez przyjęcia do programu. Dalszy krok to tekstura obrazu
w 17; błędy pozornego porządku, orientacji i niestabilności pozostają
w raporcie oraz porównaniu do odbioru 13.
