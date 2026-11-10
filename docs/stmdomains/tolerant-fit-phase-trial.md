# Dopasowanie sieci z tolerancją pozycji i zgodność przesunięcia między otoczeniami

Data: **2026-10-28**. Kontynuacja issue **19**, wykonana na polecenie użytkownika.
**19 pozostaje `claimed`, do omówienia; 20 nadal odłożone.** Nie wybrano metody
ani nie zmieniono aplikacji. [Manifest](tolerant-fit-phase-manifest.json).

**Wynik:** miękka ocena dopasowania pomaga przy niewielkich błędach pozycji
oraz brakach oznaczeń. Korekta wektorów pomaga przy lekkim odkształceniu,
ale może też wchłonąć granicę przesunięcia. Osobny test fazy wykrywa część
niezgodnych połączeń, lecz obecne łączenie w spójne fragmenty nadal scala
niektóre domeny. Na TTMAPP nie uzyskano poprawy: najwyżej **125/1678 (7.4%)**
przypisanych znanych molekuł, wobec **279/1678 (16.6%)** poprzedniej zgodności
centrów z geometrycznymi wektorami na tej samej siatce. Nadal tylko BLACK.
To wynik tej procedury, nie dowód braku domen lub niemożliwości ich wykrycia.

Podgląd: [tolerant-fit-phase/index.html](../../.scratch/tolerant-fit-phase/index.html).
Samodzielny HTML ma 53 obrazy, wszystkie 84 ustawienia, pięć przykładów krokowych,
wybór miejsca i podgląd połączeń. Kółka oznaczają molekuły, kwadraty — regularne
miejsca próbkowania. Referencje można włączyć do oceny. Pełne dane:
[CSV](../../.scratch/tolerant-fit-phase/controls.csv),
[wykres PNG](../../.scratch/tolerant-fit-phase/comparison.png),
[wykres PDF](../../.scratch/tolerant-fit-phase/comparison.pdf).

## Pytania i zakres

Sprawdzono osobno:

1. Czy dopasowanie położeń do jednej lokalnej sieci działa przy błędach pozycji,
   gdy zamiast ostrego trafienia w promieniu 2 px stosujemy miękką ocenę?
2. Czy niewielka ciągła korekta wektorów usuwa problem ich całkowitopikselowej
   propozycji oraz toleruje lekkie odkształcenie?
3. Czy sąsiednie zaakceptowane otoczenia mają zgodny układ i zgodne przesunięcie
   wzoru, a po odrzuceniu niezgodnych połączeń powstają poprawne fragmenty?

To próba geometrii dostarczonych oznaczeń. Nie uruchamiano ponownie FCN/DINO,
treningu ani odkrywania katalogu typów. Propozycje pochodzą z histogramu różnic
położeń centrów, tak jak w [poprzedniej próbie](translation-family-trial.md).
Pozostało wcześniejsze podparcie oraz dodatnia propozycja ACF obrazu.
Nie jest to metoda działająca bez centrów. Nie podano liczby domen, wzorców
ich klas, ręcznych granic ani kolorów referencji do detektora.

## Dane i rozdzielenie oceny

- **210 pełnych obrazów:** wszystkie 165 obrazów poprzedniego badania oraz
  45 nowych syntetyków. Wśród nich 24 TTMAPP; 18 ma częściowe referencje,
  a 6 pozostaje tylko do oglądania. Nie wykonywano pełnych 268 klatek.
- Kalibracja na tych samych **45 wcześniejszych negatywach**, przed wygenerowaniem
  nowych kontroli. Osobny kwantyl .99 dla każdej oceny/promienia, decyzja `>`.
  To kontrola empiryczna tego zbioru, nie gwarancja 1% fałszywych domen.
- Nowe syntetyki: 15 przypadków × ziarna 7101–7103: czysta sieć, jitter .6/1.2 px,
  małe odkształcenie, przesunięcie całego obrazu, granica 1/3/6 px, granica 6 px
  z jitterem .6/1.2, brak 30% oznaczeń, pusty pas, niezależne rzędy, losowe punkty,
  odwrócenie kontrastu połowy obrazu. Okres bazowy 12 px, obraz 192×192.
  W kontrolach o stałej geometrii ziarna zmieniają szum obrazu; nie są trzema
  niezależnymi strukturami. Jitter jest odchyleniem standardowym każdej osi.
- Pełne prognozy zamrożono przed oceną referencji. Powstało **17640 wyników**
  (210×84); oceniono **17136**, bo 6 TTMAPP nie ma masek referencyjnych.
  Poza znanymi wnętrzami TTMAPP niczego nie traktujemy jako negatywu.
  Mianowniki: 1916 miejsc siatki / 1678 molekuł; BLACK 1303, RED 101, YELLOW 274.

## Procedura

Dla każdego miejsca siatki co 12 px i każdego rzeczywistego centrum badamy
promień 24 lub 48 px. Z integerowej propozycji wybieramy kanoniczną najkrótszą
równoważną bazę. Dopasowanie wymaga co najmniej 12 centrów w otoczeniu.

Współrzędne po przeliczeniu na bazę dają fazę modulo okres. Średnia kołowa
inicjuje przesunięcie sieci. Pięć iteracji z wagami Hubera, skala 2 px,
aktualizuje samo przesunięcie (`fixed`) albo przesunięcie i wektory (`refined`).
Zmiana afiniczna względem propozycji ma normę spektralną odchylenia od
identyczności najwyżej .15. Nie oznacza to dowolnego obrotu lub wyboru nowego typu.

Centra sortujemy po y/x i dzielimy naprzemiennie na dwie części. Dopasowanie
na jednej części oceniamy na drugiej i zamieniamy role. Ocena jest średnią
`exp(-d²/(2τ²))` odległości do najbliższego węzła; τ=1 lub 2 px. To nie jest
promień twardej akceptacji każdej molekuły. **Propozycja początkowej bazy
korzysta już ze wszystkich lokalnych centrów.** Podział sprawdza zatem
estymację parametrów warunkowo względem tej propozycji, a nie stanowi w pełni
niezależnej walidacji. Kalibracja negatywów obejmuje tę samą procedurę.

| Promień | Stała, τ=1 | Stała, τ=2 | Korekta, τ=1 | Korekta, τ=2 |
| --- | ---: | ---: | ---: | ---: |
| 24 px | .844717 | .957362 | .839428 | .955465 |
| 48 px | .648580 | .846472 | .713942 | .887665 |

Pełne lokalne dopasowanie służy następnie do oceny krawędzi. Sąsiedztwo
pozostało wcześniejsze: siatka do 12√2 px; centra do minimum z 24 px i 1.65
mediany odległości do najbliższego sąsiada. Fragment wymaga 4 miejsc siatki
lub 8 centrów. Porównano pięć sposobów dopuszczania połączeń:

- tylko sąsiedztwo;
- dodatkowo zgodność baz po całkowitoliczbowej transformacji unimodularnej,
  z różnicą afiniczną ≤.15;
- dodatkowo faza pełnego otoczenia z różnicą ≤2 px;
- faza z mniejszego promienia 18 px, różnica ≤2 px;
- faza z promienia 18 px, różnica ≤1 px.

Fazę porównujemy w środku krawędzi, przez przewidywane węzły obu sieci,
modulo ich uzgodnioną średnią bazę. Nie porównujemy surowych faz z różnie
zapisanych baz. Małe otoczenie wymaga minimum 4 centrów oraz koncentracji
kołowej ≥.65 w obu współrzędnych. Brak dostępnej fazy blokuje połączenie.
W audycie rozdzielono taki brak od rzeczywistej różnicy fazy.

Łącznie: 2 sposoby próbkowania × 2 promienie × 4 oceny × 5 sposobów łączenia
=80 wariantów oraz 4 wcześniejsze wyniki geometryczne. Te ostatnie odtworzono
dokładnie. Nie stosowano poprawiania konturów, ręcznej eliminacji mostków
ani doboru najlepszego progu na TTMAPP.

## Tolerancja położeń: częściowa korzyść

Nowe kontrole, siatka, r48; odsetek dostępnych molekuł przypisanych do fragmentu.
Kolumny nowych dopasowań mają τ=2. Progi każdej kolumny są osobno kalibrowane.

| Kontrola | Poprzednia metoda | Stała sieć | Korekta wektorów | Korekta + mała faza ≤1 px |
| --- | ---: | ---: | ---: | ---: |
| Czysta sieć | 88.3% | 91.0% | 91.0% | 88.3% |
| Jitter .6 px | 84.2% | 90.9% | 77.5% | 69.3% |
| Jitter 1.2 px | 0% | 0% | 0% | 0% |
| Lekkie odkształcenie | 87.1% | 48.8% | 91.3% | 91.3% |
| Brak 30% oznaczeń | 13.1% | 75.8% | 75.8% | 21.8% |

Przy jitterze .6 stała sieć pozostaje jednym fragmentem w każdym obrazie;
korekta daje 1, 1 i 3 fragmenty. **Większa elastyczność nie zapewnia lepszej
odporności na losowe odchylenia.** Przy jitterze 1.2 żaden z 84 wariantów
nie daje przypisań. Nie dobierano po wyniku łagodniejszych progów.

Korekta jest przydatna przy niewielkim spójnym odkształceniu: stała baza
całkowitopikselowa gorzej reprezentuje ten układ. Efekt zależy od miejsc
próbkowania: dla rzeczywistych centrów w tej kontroli stała i korygowana
sieć osiągają obie 92.5%. Nie jest to jednolita przewaga korekty.

Przesunięcie całej sieci i odwrócenie kontrastu nie tworzą dodatkowej domeny
w r48/τ2. Pozostają wcześniejsze ograniczenia pola podparcia i wejściowej ACF.

## Faza: sygnał granicy nie gwarantuje rozdzielenia domen

Dla czystej granicy 3 px, r48/τ2:

- poprzednia metoda scala obie strony;
- stała sieć daje dwa fragmenty już **przez odmowę dopasowania w pasie styku**;
  test fazy nie jest przyczyną tego rozdzielenia;
- korekta wektorów znów scala strony: lokalne odkształcenie pochłania część
  skoku. Faza pełnego okna także nie rozdziela wyników;
- faza promienia 18 px/limit 1 px, przy rzeczywistych centrach, usuwa
  **132/138 bezpośrednich połączeń przez znaną granicę**, lecz zostawia
  **6** — po dwa na obraz. Wynik nadal jest jednym fragmentem, czyli
  100% ocenianych par różnych domen pozostaje scalonych.

Pozostałe połączenia leżą między [84,0]–[99,0] i [84,180]–[99,180].
Ich oszacowana różnica fazy wynosi około **.862 px**, więc przechodzą limit 1 px.
Na siatce mała faza pozostaje jeszcze bardziej wygładzona: zwykle około .86 px,
więc większość połączeń przez ten sam skok 3 px zostaje. To efekt nakładających
się otoczeń, dopasowania i próbkowania; same prawidłowe rachunki fazy nie
zapewniają rozdzielenia. Szczegóły zapisano w `evaluation/mechanism-audit.json`.

Skok 1 px pozostaje scalony w omawianych r48/τ2. Przy skoku 6 px nowe
kryterium dopasowania rozdziela strony już bez fazy, kosztem nieprzypisanego
pasa; po dodaniu jitteru .6 zachowuje rozdzielenie, ale spada liczba przypisań.
Nie interpretujemy odmowy na szerokim pasie jako dokładnego znalezienia konturu.

## Materiał, braki danych i fałszywy porządek

**Pusty pas:** na siatce r48 nowe dopasowanie przyjmuje **96/96 miejsc**
kontrolnej przerwy. Odtwarza wspólną sieć z molekuł po obu stronach i scala
płaty. Zgodna faza dużego okna tego nie naprawia — po obu stronach faktycznie
jest ta sama faza. Mały promień usuwa fałszywe miejsca i przywraca dwa fragmenty,
ale wskutek **braku lokalnych centrów**, nie wykrycia różnicy fazy.
Na próbkowaniu w centrach pustego pasa nie ma w grafie, więc płaty już są rozdzielone.

**Brak oznaczeń:** ta sama reguła dostępności małego otoczenia odcina
1648/1851 krawędzi zaakceptowanych miejsc siatki przy braku 30% centrów.
Wszystkie te odmowy wynikają z niedostępnej fazy, a nie z jej różnicy >1 px.
Powstaje 3, 1 i 7 fragmentów zamiast jednej sieci. Przy próbkowaniu w centrach
odmów dostępności jest tylko 10; ta różnica wyjaśnia dużą zależność od siatki.
Nie możemy utożsamiać braku oznaczenia z brakiem materiału.

**Niezależne rzędy:** fałszywie przypisane miejsca siatki r48: poprzednio
66/768, stała sieć τ2 **91/768**, korekta **136/768**, korekta + mała faza
**123/768**. Tolerancja nadal dopuszcza lokalnie podobne przypadkowe układy.
Dla nowych losowych punktów omawiane warianty dają 0/768, co nie usuwa problemu
niezależnych rzędów. Wyniki negatywów trzeba oceniać oddzielnie, a nie uśredniać.

## TTMAPP i ograniczenia modelu

Na r48 wszystkie znane miejsca mają dostępną ocenę: 1916/1916 na siatce
i 1678/1678 centrów. Odmowy nie wynikają więc głównie z braku liczby punktów.
Stała baza daje zero przypisań, korekta τ1 daje 125/1678 na siatce oraz
107/1678 w centrach; τ2 odpowiednio 102 i 89. Dodatkowa faza nie zmienia
tych przypisań. Wszystkie należą do BLACK; RED/YELLOW pozostają nieprzypisane.
Przy r24 minimum 12 centrów jest istotnym ograniczeniem: dostępność tylko
455/1916 miejsc siatki i 341/1678 centrów.

Model zakłada, że oznaczone molekuły pasują do węzłów **jednej lokalnej sieci
Bravaisa**, z niewielkim odkształceniem i wspólną fazą. Nie modeluje wielu
molekuł w komórce, dowolnych motywów ani mieszaniny sieci w jednym oknie.
Nie narzucamy konkretnej orientacji czy rozstawu, lecz nadal narzucamy tę
rodzinę geometryczną. Wyniki nie uzasadniają ogólności dla różnych materiałów STM.
Centrów również nie traktujemy jako bezbłędnej prawdy.

Wcześniejszy [eksperyment 12](phase-boundaries-trial.md) liczył fazę w wybranych
wnętrzach referencji. Tutaj każde dopasowanie i połączenie powstaje na całej
klatce bez tych wnętrz. Obserwacja wygładzania granicy powraca także w tej
niezależnej od referencji procedurze.

## Wniosek i następny krok

Zachowujemy osobne wyniki dopasowania, dostępności materiału i zgodności fazy.
Nie wybieramy wariantu według największej liczby przypisań; większa liczba
może obejmować pusty pas lub przypadkowe rzędy.

**Następna konkretna hipoteza w 19:** porównać jeden wspólny model z dwoma
modelami dopasowanymi do rozłącznych, jednostronnych otoczeń po obu stronach
potencjalnej granicy. Ocenić przewidywanie na oddzielnych blokach punktów,
aby granica nie była wygładzana wspólnymi punktami. Sprawdzać całą ciągłość
rozcięcia, również przy brzegu obrazu, oraz odróżniać brak dowodu fazy od
potwierdzonej niezgodności. Niezależnie sprawdzać lokalne podparcie materiału;
liczba centrów sama nie rozstrzyga pustego podłoża i brakujących oznaczeń.

Przed rozszerzaniem modelu na TTMAPP warto odczytać rozkład reszt w odrzuconych
otoczeniach: jedna niedokładna sieć, kilka motywów czy nakładające się struktury
wymagają różnych rozwiązań. To propozycja następnego badania, jeszcze niewykonana.
Nie jest poleceniem przejścia do 20 ani wyborem algorytmu produkcyjnego.

## Sprawdzenia i odtworzenie

Źródła: **`prototype/stmdomains-tolerant-fit-phase`, `c7ed021`**, baza `d6ae09a`.
Prototyp nie jest przeznaczony do scalenia do aplikacji. Jedno polecenie:
`bash stmdomains/prototypes/run-tolerant-fit-phase.sh /tmp/nowa-proba` w tym
checkoutcie. Wymaga poprzednich lokalnych artefaktów i środowiska netcat.

- **1225 sprawdzeń liczbowych:** równoważne bazy, kolejność centrów, przesunięcie
  całego układu; 1200 porównań najbliższego węzła z szerszym przeszukaniem
  (maksymalny błąd 0); znane różnice fazy 0/1/3/6/12 px.
- **660 dokładnych odtworzeń wcześniejszych wyników** po 3 tablice: decyzje,
  fragmenty, przypisania molekuł. 45 deterministycznych odtworzeń nowych obrazów.
- **210 pomiarów i 210 plików predykcji / 17640 wyników** odtworzono identycznie
  przy zablokowanym odczycie ścieżek referencji/evaluation. To sprawdzenie
  niezależności obliczeń, nie dowód trafności metody.
- **217 kontroli QtWebEngine**, bez błędów JS; sprawdzono wszystkie ustawienia,
  53 obrazy w obu trybach, scenariusze, wybór miejsca i poprawną prezentację
  procentów. Obejrzano zrzut i wykres. Naprawy dotyczyły serializacji bool oraz
  wskaźników w HTML; nie zmieniały progów, pomiarów ani prognoz.
- Python/Bash sprawdzone składniowo; wrapper wykonany etapami. Nie testowano
  aplikacyjnego GUI ani produkcji. Nie dokładano zależności, wag lub testów aplikacji.

CPU, 4 procesy po 1 wątku: pomiary **42.13 + 29.80 s**, predykcje **18.28 s**,
ocena **4.18 s**, niezależne odtworzenie **91.85 s**. Maksymalny RSS procesu
**118712 KiB**; łącznego szczytu nie mierzono. Czasy końcowych etapów, bez UI.
Bez GPU. Kopia lokalna: **537 plików / 109045271 B**, wszystkie SHA-256 zgodne;
następnie dodano potwierdzenie kopii. Względny link `previous` prowadzi do
`../translation-family`. HTML/CSV/wykresy są samodzielne; powtórzenie obliczeń
wymaga poprzednich artefaktów. Dokumentacja i manifest pozostają w Git,
dane i duże wyniki w `.scratch/`. Brak potrzeb zmian wspólnych modułów.
