# Kryterium powtarzalności — kontynuacja issue 15

Data: 2026-10-23. Status: wykonana próba rozwojowa, **issue 15 nadal `claimed`**.
Polecenie użytkownika: „zbadaj kryterium powtarzalności”, po decyzji
„Najpierw omówmy lub rozwińmy tę próbę”. Punktem odniesienia jest
[pierwsza próba otoczeń molekuł](local-neighborhood-domains-trial.md).

Sztywny próg 0.6 był istotną przyczyną pomijania RED/YELLOW. Kalibracja
na kontrolach i większa tolerancja położeń zwiększają odsetek oznaczeń
przechodzących warunek z **34.0% do 90.9%**, a przypisanych do domen
z **31.0% do 62.5%** we wnętrzach referencji TTMAPP. Nie jest to dokładność
detekcji: pojawiają się scalenia różnych obszarów, a większość YELLOW
nadal nie tworzy rozpoznanej domeny. Sama lokalna powtarzalność nie
wystarcza do rozstrzygnięcia istnienia spójnej domeny 2D.

Podgląd: `/home/rlew/projekty/NEtCAT-domains/.scratch/recurrence-criterion/index.html`.
Zacząć od „TTMAPP”, „Błąd centrów” i „Rzędy bez wspólnej fazy”; przełączać
warunek porządku, składowe bez typu oraz domeny. Nakładkę referencji
włącza się osobno. Wykres: `recurrence-comparison.png` w tym samym katalogu.

## Co sprawdza ten warunek

Dla każdego centrum wybieramy otoczenie o promieniu R. Wektory do
bliskich sąsiadów traktujemy jako propozycje przesunięć sieci. Przesuwamy
otoczenie o taki wektor i liczymy, jaka część przesuniętych punktów trafia
w pobliże istniejących centrów. Szukamy dwóch nieprawie równoległych
wektorów; wynik jest najlepszym minimum ich dwóch odsetków trafień.
To miara powtarzalności geometrii, **nie prawdopodobieństwo domeny**.

W starym wyniku środek otoczenia zawsze trafia na sąsiada, który
wyznaczył wektor. Usunięto to gwarantowane trafienie. W poprawionej
wersji nadal wymagamy co najmniej 8 pozostałych prób na wektor oraz
8 sąsiadów. Nie zakładamy statystycznej niezależności tych prób.

Rozstaw s jest lokalną medianą odległości do najbliższego sąsiada.
Kandydaci mają długość od 0.65s do min(0.8R, 1.8s), a sinus kąta między
dwoma wektorami musi mieć moduł co najmniej 0.3. Tolerancję dopasowania
wyrażamy jako część s. Nie zadano jednej symetrii ani liczby domen.
Nie zmieniono tych reguł kandydatów w tej próbie. Trafienia opierają się
na najbliższym punkcie, bez dopasowania jeden do jednego i bez wymogu
jednej wspólnej komórki sieci dla całego obszaru — to nadal ograniczenia.

## Zakres i dobór parametrów

Zamrożono katalog SOAP/36, przypisania surowych grup, miary orientacji
i reguły przestrzennego łączenia z poprzedniej próby. Zmienialiśmy warunek
powtarzalności i liczbę sąsiadów liczoną w badanym promieniu. Dzięki temu
nie przypisujemy poprawy ponownemu dopasowaniu katalogu. Nie badano tutaj
nowego rozwiązania rozstawów, segmentacji obrazu ani treningu.

Wejście: 24 pełne klatki TTMAPP, dotychczasowe 132 kontrole oraz
48 nowych kontroli, razem **204 próbki**. Nowe przypadki, każdy z trzema
ziarnami rozwojowymi i trzema do oceny:

- błędy centrów σ = 3%, 6%, 10% rozstawu, czyli 0.36/0.72/1.2 px w każdej osi;
- błąd 6% razem z brakiem 30% centrów;
- sieć ścinana i łagodnie odkształcona;
- losowe punkty skupione w trzech gęstszych obszarach;
- regularne rzędy o niezależnych przesunięciach wzdłuż rzędu.

Przy błędzie centrów obraz nie zmienia się; odrzucamy centra przesunięte
poza obraz, więc porównanie dotyczy zachowanych oznaczeń. Rzędy są
przypadkiem diagnostycznym bez kompletnej prawdy domen 2D. Wyłączono je
z kalibracji i oceny trafności. Nie uznajemy automatycznie każdej znalezionej
w nich składowej za fałszywą domenę.

Nowym kontrolom nie dopasowano katalogu typów. Oceniają warunek oraz
przestrzenne składowe **bez warunku zgodności typu**. W podglądzie brak
etapu typowania oznacza „—”, CSV zawiera `typed_available`. Zera
`typed_domains` w surowych tablicach oraz zerowe przypisanie `typed`
w surowej ocenie tych nowych kontroli oznaczają niewykonany etap,
nie wynik negatywny wykrywania. Wyniki zgodne z kontraktem mają stan
`ordered_untyped` i pusty typ. Dla TTMAPP i wcześniejszych kontroli
zachowano istniejący katalog.

Porównano **38 konfiguracji**:

- R = 24/36/48 px oraz tolerancja 8/12/18/24% rozstawu;
- dla poprawionego wyniku: próg 0.6, próg z trzech rodzin losowych lub
  próg z czterech rodzin, włącznie z losowymi skupiskami — 36 wariantów;
- dokładny poprzedni wariant oraz samą zmianę jego progu — dwa odniesienia.

Próg empiryczny to maksimum kwantyli 99.5% z poszczególnych rodzin
kontroli rozwojowych; akceptacja wymaga wyniku **ściśle większego** od
progu. Rodziny: punkty losowe, z minimalnym odstępem, z gradientem
gęstości, dodatkowo skupiska. Ziarna rozwojowe: 1701–1703; ocena: 2701–2703.
To kalibracja na ograniczonej próbie, bez gwarancji błędu 0.5% na nowych
rodzajach danych.

Reguła wyboru była zapisana przed oceną: spośród wariantów kalibrowanych
na czterech rodzinach wymagamy ≥90% akceptacji pojedynczej regularnej
sieci, ≤0.5% akceptacji w każdej rodzinie losowej i braku składowych
przestrzennych na tych kontrolach. Następnie maksymalizujemy najgorszą,
a potem średnią akceptację dziesięciu dodatnich przypadków rozwojowych;
remisy rozstrzyga mniejsza tolerancja, potem promień bliższy 36.

Wybrano **R = 36 px, tolerancję 24% s, poprawiony wynik >0.25**
(`r36-t24-expanded_null`). Dla kontrolnego rozstawu 12 px tolerancja to
2.88 px, ale na TTMAPP jest wyliczana lokalnie. Warunki spełnił również
wariant 18%; przegrał średnią akceptacją. Wariant 12% nie spełnił ścisłego
limitu fałszywych akceptacji na rozwoju: 4/768 ≈0.52%.

Kalibracja korzystała tylko z kontroli rozwojowych. Zapisano predykcje
wszystkich konfiguracji przed oceną referencji. Obecne ramki były już
używane do wykrycia problemu, zatem wynik TTMAPP jest **rozwojowy**, a nie
nowym niezależnym testem. Dobór nie wymuszał przejścia BLACK/RED/YELLOW.

## Co zmieniło się na TTMAPP

Ocena dotyczy 1678 oznaczeń we wnętrzach 18 częściowych referencji.
Są to obserwacje z kolejnych klatek, nie 1678 niezależnych molekuł.
Nieoznaczone miejsca nie są tłem ani negatywnymi przykładami.

| Wariant | Przechodzi warunek | Otrzymuje domenę |
| --- | --- | --- |
| Poprzedni: 12%, stary wynik >0.6 | 571/1678 = 34.0% | 521/1678 = 31.0% |
| Tylko niższy próg starego wyniku: >0.15385 | 1509/1678 = 89.9% | 1033/1678 = 61.6% |
| 12%, poprawiony wynik i kalibracja | 1470/1678 = 87.6% | 1007/1678 = 60.0% |
| 24%, poprawiony wynik, nadal >0.6 | 1051/1678 = 62.6% | 919/1678 = 54.8% |
| Wybrany na kontrolach: 24%, poprawiony wynik >0.25 | **1526/1678 = 90.9%** | **1048/1678 = 62.5%** |

Największą poprawę na tej serii daje zniesienie sztywnego progu 0.6.
Wybrany wariant nie był optymalizowany pod te ramki; nie dowiedziono,
że jest najlepszą konfiguracją dla rzeczywistych STM. Większa tolerancja
ma wyraźną zaletę w kontrolach błędu centrów, opisaną niżej.

| Obszar referencji | Stary warunek | Nowy warunek | Domeny przed → po zmianie |
| --- | --- | --- | --- |
| BLACK, 1303 oznaczenia | 571 = 43.8% | 1247 = 95.7% | 521 → 1007, czyli 40.0% → 77.3% |
| RED, 101 | 0 | 81 = 80.2% | 0 → 28, czyli 27.7% |
| YELLOW, 274 | 0 | 198 = 72.3% | 0 → 13, czyli 4.7% |

Wśród par przypisanych oznaczeń z różnych referencyjnych regionów
**708/2329 = 30.4% połączono w tę samą domenę**. To błąd scalenia
warunkowy względem przypisania obu elementów, nie procent wszystkich
domen ani obrazu. Stary wariant nie przypisywał par z różnych regionów,
więc jego scalenie jest nieocenialne, a nie równe zeru. Przy samej zmianie
progu błąd ten wynosi 23.5%; nie wolno więc utożsamiać większej akceptacji
z lepszym rozdzieleniem domen.

W jednym regionie rozdzielono 203/28585 = 0.71% przypisanych par,
wobec 640/7964 = 8.04% poprzednio. Mianowniki są różne, a spadek podziałów
występuje razem ze scalaniem. Kolory oznaczają głównie orientacje tej
samej sieci; nie są prawdą różnych typów strukturalnych. Nie mierzono
dokładności granic, pokrycia warstwy ani wszystkich domen całego kadru.

## Gdzie teraz znikają RED i YELLOW

Po przejściu warunku większość tych centrów odpada przy tworzeniu
dostatecznie dużych składowych zgodnych orientacyjnie:

| Przyczyna / wynik po zmianie | BLACK | RED | YELLOW |
| --- | --- | --- | --- |
| Rozpoznana domena | 1007 | 28 | 13 |
| Zgodna składowa ma mniej niż 8 centrów | 236 | 53 | 174 |
| Wynik powtarzalności za niski | 43 | 9 | 36 |
| Za mało sąsiadów lub prób przesunięcia | 13 | 11 | 40 |
| Brak dostatecznego wsparcia orientacji | 3 | 0 | 11 |
| Brak przypisania z zamrożonego katalogu | 1 | 0 | 0 |

To diagnoza reguł programu, nie dowód fizycznego rozdrobnienia domen.
Samo grupowanie SOAP nie wyjaśnia większości pozostałych odmów.
Potrzebna jest analiza estymacji orientacji, zgodności sąsiadów i sposobu
łączenia przestrzennego. Obniżenie minimalnej wielkości składowej bez
takiej analizy grozi uznaniem małych przypadkowych grup za domeny.

## Wyniki kontroli odłożonych do oceny

Na czterech rodzinach czysto losowych nowy wariant akceptuje **2/3195
centrów**, oba w kontroli z minimalnym odstępem. Nie powstaje żadna
składowa przestrzenna. Dla samej zmiany starego progu to 18/3195 centrów,
również bez składowych. To wynik trzech ziaren danego generatora,
nie potwierdzenie skuteczności na dowolnym nieuporządkowanym materiale.
W kontroli pasa nieuporządkowanego przechodzi 5/119 negatywnych centrów,
lecz żaden nie trafia do składowej; dwie regularne części pozostają osobne.

| Kontrola | Przechodzi stary → nowy warunek | Nowe składowe w trzech powtórzeniach |
| --- | --- | --- |
| Jedna regularna sieć | 98.4% → 98.4% | 1/1/1 |
| Błąd centrów σ = 0.36 px | 96.4% → 94.8% | 1/1/1, bez katalogu typów |
| Błąd σ = 0.72 px | **13.3% → 95.5%** | 1/1/1, bez katalogu typów |
| Błąd σ = 1.2 px | 0.14% → 89.2% | 3/2/2, bez katalogu typów |
| Błąd 0.72 px + brak 30% centrów | 1.0% → 75.0% | 2/2/3, bez katalogu typów |
| Sam brak 30% centrów | 76.2% → 81.9% | 2/2/3; domeny tylko 46.7% oznaczeń |
| Sam brak 50% centrów | 26.0% → 57.6% | 1/0/0; domeny tylko 2.9% oznaczeń |
| Sieć ścinana | 97.7% → 97.7% | 1/1/1, bez katalogu typów |
| Sieć łagodnie odkształcona | 97.5% → 95.5% | 3/3/3, bez katalogu typów |
| Dwie orientacje | 93.9% → 97.6% | 2/2/2, bez scaleń/podziałów przypisanych par |
| Granica przesunięcia | 98.3% → 98.3% | nadal 3/3/3 zamiast dwóch |

Próba potwierdza wrażliwość starej miary na niedokładne oznaczenia,
ale nie dowodzi, że taki błąd odpowiada za wszystkie odmowy na TTMAPP.
Przy większych brakach i odkształceniu lepszy warunek nadal nie zapewnia
poprawnych domen. W kontrolnej granicy przesunięcia pozostaje 11.3%
nadmiernie rozdzielonych par; jej rozpoznanie nie zostało naprawione.

Regularne rzędy z niezależnymi przesunięciami przepuszczają po zmianie
743/768 = **96.7%** punktów (wcześniej 28.9%); powstaje 9/11/5 składowych.
Mogą występować lokalne zgodności, dlatego nie nazywamy tych liczb
błędem względem nieistniejącej kompletnej referencji. Pokazują jednak,
że wysoki wynik nie oznacza wspólnej sieci w całym obszarze. Kontrole
losowych punktów należy uzupełniać strukturami skorelowanymi, a nie tylko
obniżać próg na podstawie ich kwantyla.

## Sprawdzenia, koszt i odtworzenie

- Stary wariant odtworzony dokładnie: warunek i domeny identyczne na
  wszystkich 156 wcześniejszych próbkach.
- Monotoniczność surowego wyniku względem tolerancji: 204 próbki;
  walidacja 1020 wyników dla pięciu wariantów podglądu.
- Obrót 37° tej samej nieprzyciętej chmury: zerowa zmiana wyniku i taka
  sama dostępność wektorów. Zmiana kolejności punktów: zerowa zmiana wyniku.
- Po sześć par kontrastu, odwróconego kontrastu i technicznej skali ×2:
  identyczne tablice wynikowe. Skala uwzględnia znany resampling w px,
  nie nieznaną kalibrację fizyczną STM.
- Dwa pełne powtórzenia ekstrakcji/predykcji: bez katalogu referencji
  oraz dodatkowo ze zmienioną kolejnością próbek i oznaczeń. W każdym
  wszystkie 204 pliki NPZ z 38 konfiguracjami identyczne bajtowo.
- Ponowne przygotowanie wejścia z końcowego źródła: 205 plików analizy
  i 199 oceny identycznych bajtowo. Pierwszy zapis przygotowania zachowuje
  hash wcześniejszej wersji skryptu; to sprawdzenie potwierdza zgodność danych.
- QtWebEngine offscreen: 13 sprawdzeń scenariuszy, widoków i referencji,
  bez błędów JavaScript i poziomego przepełnienia; obejrzano zrzut oraz wykres.
  Nie jest to test natywnego GUI STM Domains ani pełny odbiór każdej
  kombinacji kontrolek. Brak zmian aplikacji; nie uruchamiano jej testów.

CPU, jeden wątek BLAS/OpenMP. Ekstrakcja wyników powtarzalności: **29.61 s**;
kalibracja/wybór: 3.71 s; predykcja wszystkich 38 konfiguracji: **24.98 s**;
ocena: 3.10 s. Maksimum RSS tych procesów 217 780 KiB, około **213 MiB**, w
procesie oceny. Linux `ru_maxrss`, osobno dla procesu; bez GPU i treningu.
Nie mierzono VRAM ani pełnego kosztu 268 klatek. Nie obliczano ponownie SOAP.

`netcat`: NumPy 2.2.5, SciPy 1.15.2, scikit-learn 1.6.1. Podgląd:
PyQt6 6.9.1 / WebEngine 6.9.0. Import starego modułu korzysta z istniejących
DScribe 2.1.2/sparse 0.19.2 w `/tmp/stmdomains-issue15-deps`; bez instalacji
lub zmian środowiska i konfiguracji głównej repozytorium.

Źródła: **`prototype/stmdomains-recurrence`, commit `bc3763e`**, baza `1f25b45`.
Worktree `/tmp/netcat-stmdomains-recurrence-prototype`; README:
`stmdomains/prototypes/README-recurrence.md`. Nie scalać kodu prototypu
do aplikacji. Jedno polecenie z katalogu głównego tego worktree:

```bash
bash stmdomains/prototypes/run_recurrence_trial.sh \
  /home/rlew/projekty/NEtCAT-domains/.scratch/unsupervised-input \
  /home/rlew/projekty/NEtCAT-domains/.scratch/local-neighborhood-domains \
  /tmp/stmdomains-recurrence-new
```

Ostatni katalog musi być nowy. README podaje także oba powtórzenia bez
referencji. Główny skrypt użyty do ekstrakcji, kalibracji, predykcji i oceny:
SHA-256 `48e7c9393dcb439e7106899e4a0c857618c6a63b4dcb03256af6c9f70431622f`.

Pakiet lokalny `.scratch/recurrence-criterion/` (~230 MB) zawiera plan,
204 wejścia, cechy, 38 konfiguracji/predykcji, ocenę JSON/CSV, 1020
wyników z jawnymi odmowami, diagnozę odmów, HTML, wykres i sprawdzenia
odtwarzalności. `provenance.json` zapisuje źródła, wersje i hashe wejścia;
manifesty zapisują hashe wyników. Duże dane i obrazy pozostają poza Git.

## Wniosek i następny eksperyment

Kryterium warto zachować jako **pomocniczy dowód lokalnej regularności**.
Sztywne 0.6 nie jest uzasadnionym uniwersalnym progiem, a tolerancja
położeń ma istotny wpływ. Sam wynik powtarzalności nie wyznacza domeny,
jej typu, granicy ani powierzchni materiału.

Następna próba w ramach 15 powinna odseparować dwa pytania:

1. Czy estymujemy zgodną orientację i lokalne wektory sieci dla sąsiadów,
   mimo błędów centrów oraz braków? Porównać dotychczasowy estymator
   z odpornym dopasowaniem lokalnych przesunięć/komórki i jawną niepewnością.
2. Czy łączenie sąsiadów zachowuje wspólną geometrię bez mostków między
   różnymi orientacjami i bez nadmiernego rozdrabniania? Sprawdzić także
   zgodność przesunięć/fazy oraz przypadki skorelowanych rzędów, zaburzeń
   i braków. Nie rozwiązywać tego samym obniżeniem minimum 8 elementów.

Najpierw parametry i kontrola zero/jedna/wiele na syntezie, później
zamrożony wariant na pełnych klatkach i odsłonięcie częściowej referencji.
Katalog rozstawów SOAP pozostaje odrębną luką. Nie narzucamy trzech domen,
nie trenujemy na kolorowych ramkach. Nie wybrano metody produkcyjnej,
nie rozpoczęto issue 16; issue 15 i odbiór 13 pozostają otwarte.

## Aktualizacja po kolejnym poleceniu użytkownika

2026-10-23 wykonano proponowane [badanie orientacji i łączenia](orientation-and-joining-trial.md).
Komórka sieci i zgodność ze startem obszaru poprawiają kontrolę braków
oraz część TTMAPP, ale nie rozwiązują granicy przesunięcia przy błędach
centrów ani słabego RED/YELLOW. Wynik i nowe ograniczenia są w osobnym
raporcie. Issue 15 pozostaje `claimed`; po omówieniu proponowane jest
porównanie 16 z zachowaniem rozszerzonych kontroli.
