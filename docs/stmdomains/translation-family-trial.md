# Ocena rodziny zgodnych przesunięć — wynik próby w issue 19

Data: **2026-10-28**. Na polecenie użytkownika **„zbadaj ocenę wielu
zgodnych przesunięć”**, po [audycie odmów](vector-refusal-audit.md).
Źródła: **`prototype/stmdomains-translation-family`, `d6ae09a`**, baza
`9c78d8c`. Dokumentacja: `domains/translation-family`, baza `e5e6100`.
Prototyp pozostaje poza aplikacją.

**Ocena rodziny usuwa zależność wyniku liczbowego od równoważnej bazy,
ale nie rozwiązuje ogólnego wykrywania domen.** Agregacje zgodności obrazu
nadal nie odzyskują znanych wnętrz TTMAPP. Zgodność położeń centrów przy
większym oknie odzyskuje do **296/1678 oznaczeń (17.6%)**, wyłącznie BLACK,
lecz na kontrolach scala granicę przesunięcia i przyjmuje część niezależnych
rzędów. Warianty łagodniejszej agregacji obrazu tworzą też pozorny fragment
w pustej przerwie. Nie wybrano metody do programu.

[Podgląd HTML](../../.scratch/translation-family/index.html) ·
[wykres PNG](../../.scratch/translation-family/family-comparison.png) ·
[PDF](../../.scratch/translation-family/family-comparison.pdf) ·
[tabele CSV](../../.scratch/translation-family/controls.csv) ·
[manifest](translation-family-manifest.json).

## Zakres i rozdzielenie danych

**165 obrazów**: 78 obrazów poprzedniego audytu oraz 45 wcześniejszych
negatywnych obrazów kalibracji, a następnie **42 nowe syntetyki**.
Zachowano 24 pełne klatki TTMAPP, regularną siatkę i dostarczone centra.
Referencje obejmują 18 klatek, 1916 miejsc siatki i 1678 kolejnych oznaczeń
molekuł. Nieoznaczone części obrazów nie są uznawane za negatywne.

Nowe syntetyki: 14 przypadków × ziarna 6101–6103. Jedna sieć, losowe
amplitudy molekuł, zmienne kształty, większy szum, zaburzenia pozycji .6
i 1.2 px, niezależne fazy rzędów, losowe punkty, pasy, przerwa, granica
przesunięcia, dwie orientacje oraz obrót sieci i zmiennych amplitud o 27°.
Obrazy mają 192×192 px i podstawowy rozstaw 12 px. Algorytm nie otrzymuje
parametrów generatora ani masek prawdy. „Ta sama sieć” w kontrolach
zmiennego wyglądu oznacza ten sam układ położeń; nie modeluje wszystkich
fizycznych przyczyn kontrastu w STM.

Protokół zapisano przed obliczeniami. Progi wyznaczono wyłącznie na
45 znanych negatywach. Nowe obrazy wygenerowano **po zamrożeniu progów**.
Referencje TTMAPP odczytano dopiero po zapisaniu predykcji i ich hashy.
Bez treningu, wzorców domen, zadanej liczby grup, nowej symetrii sieci
i dopasowywania parametrów do ramek. To własny eksperyment na bazie
poprzedniego kryterium, nie deklaracja implementacji zwalidowanej metody
z publikacji. Nowe syntetyki nie zastępują niezależnych pomiarów STM.

## Jak powstaje rodzina

Zachowano dwa źródła propozycji: parę ACF obrazu oraz histogram różnic
centrów z audytu. Dla pary `B` wyliczono wszystkie pierwotne wektory
`i·B₁ + j·B₂` o długości 6–24 px. Współczynniki są względnie pierwsze;
pomijamy wielokrotności tego samego przesunięcia. Granice enumeracji
wynikają z odwrotności bazy i obejmują cały dysk długości 24 px, także
gdy ta sama sieć została opisana dłuższymi wektorami.

Znaki i kolejność są ujednolicone w układzie obrazu. Z wektorów wybieramy
wszystkie pary o tej samej bezwzględnej wartości wyznacznika co `B`
oraz sinusie kąta ≥.35. To bazy tej samej proponowanej sieci, bez
rozszerzania jej na nową podsieć. Potrzeba przynajmniej trzech wektorów
i dwóch baz. **Nie wybieramy rodziny według najwyższej korelacji.**

Rozwiązanie jest niezależne od dokładnie równoważnej bazy. Nie gwarantuje
zgodności dwóch różnych estymat sieci, propozycji z błędem pozycji,
niecałkowitych przesunięć ani błędnie znalezionej komórki. Nadal obowiązuje
ograniczony zakres długości i kwantyzacja propozycji do pikseli.
Badamy rodzinę jednej oszacowanej sieci okresowej. Brak trzech wektorów
w zadanym zakresie może wynikać z jej skali, więc nie oznacza braku porządku.

## Kryteria i uczciwe porównanie

Dla każdej pary liczymy niezmienione osiem korelacji różnic obrazu:
dwa kierunki × cztery części okna. Rodzina jest dostępna, gdy przynajmniej
dwie bazy i co najmniej połowa wszystkich baz mają obliczalne korelacje.
Porównano:

| Kryterium | Znaczenie |
| --- | --- |
| Jedna para | Dotychczasowe minimum ośmiu korelacji; ponowna kalibracja osobno dla obu źródeł |
| Najlepsza para | Maksimum z minimów wszystkich obliczalnych baz; wariant liberalny do porównania |
| Mediana minimów | Typowy najsłabszy wynik wśród baz |
| Mediana średnich | Typowa średnia ośmiu korelacji; mniejszy wpływ jednej słabszej części okna |
| Zgodność centrów | Mediana udziału centrów zgodnych z każdym przesunięciem rodziny, tolerancja 2 px |

Ostatnie kryterium wymaga co najmniej czterech źródłowych centrów dla
wektora, obu końców przesunięcia wewnątrz koła oraz co najmniej trzech
i połowy obliczalnych wektorów. Korzysta z oznaczeń **także przy siatce**.
Zgodność z centrami, które wyznaczyły propozycję, nie jest niezależnym
sprawdzianem jej poprawności. Braki i błędy oznaczeń pozostają ograniczeniem.

Każde kryterium, źródło propozycji i promień mają osobny próg: kwantyl
.99 dostępnych wyników na siatce 45 negatywów. Wymagamy wyniku **ściśle
większego** od progu. Brak obliczalnych wartości daje próg 1. Kalibracja
jest wspólna dla siatki i centrów. Kwantyl próbek nie jest
prawdopodobieństwem fałszywej domeny.

| Promień / propozycja | Jedna para | Najlepsza para | Mediana minimów | Mediana średnich | Zgodność centrów |
| --- | ---: | ---: | ---: | ---: | ---: |
| r24 / obraz | .7286 | .8791 | .6976 | .8500 | 1.0000 |
| r24 / centra | .7296 | .9040 | .7378 | .8827 | 1.0000 |
| r48 / obraz | .9364 | .9494 | .4692 | .7738 | .7516 |
| r48 / centra | .4124 | .9372 | .4241 | .7670 | .7612 |

**Maksymalizacja podnosi również wyniki negatywów**, dlatego nie można
uczciwie zachować starego progu i uznać wzrostu przypisań za poprawę.
Próg jednej pary obrazu odtworzył poprzednie wartości. Źródła mają osobną
kalibrację: identyczny wynik rodziny nie musi dawać tej samej decyzji,
gdy porównujemy różne źródła. Niezmienniczość decyzji dotyczy zmiany
równoważnej bazy przy stałym kryterium i kalibracji.

Przy r24 zgodność centrów osiąga 1 na negatywach z niezależnymi rzędami:
108/5440 dostępnych próbek dla propozycji obrazu i 201/5355 dla geometrii.
Stąd próg 1 i brak akceptacji także poprawnych sieci. To konkretna luka
rozdzielczości wskaźnika przy małym oknie, nie sukces eliminacji błędów.

Zachowano podziały FCN/DINO HDBSCAN/FH4 oraz reguły łączenia i przypisania
molekuł. Minimum fragmentu nadal wynosi cztery miejsca siatki lub osiem
centrów. Dwadzieścia skalibrowanych kryteriów oraz sześć dokładnych
wariantów bazowych daje **260 konfiguracji** z dziesięcioma podziałami
(w tym dwa warianty samego porządku/łączności). Rzędy i nowe obrazy
sprawdzają tylko **52 konfiguracje porządku/łączności**. Łącznie 24804
wyniki; ocena obejmuje 23244 wyniki na 159 obrazach z dostępną prawdą.

## Wynik 1: zależność od bazy została usunięta

W miejscu 113 klatki 250, r24, poprzednie pary dawały .5285 oraz .7878.
Teraz obie prowadzą do **tych samych pięciu wektorów i siedmiu baz**:

| Ocena rodziny | Obie propozycje |
| --- | ---: |
| Najlepsze minimum | .7878 |
| Mediana minimów | .5285 |
| Mediana średnich | .7155 |
| Zgodność centrów | 1.0000 |

Wyniki są identyczne, ale żaden nie przekracza właściwego nowego progu.
Sprawdzono również 56818 otoczeń całego zestawu, w których oba źródła
proponują tę samą rodzinę: wszystkie cztery oceny rodziny są identyczne.
To sprawdzenie mechaniki kryterium, nie 56818 niezależnych dowodów domen.

## Wynik 2: brak przełomu na TTMAPP

**Wszystkie trzy agregacje obrazu po rodzinie dają 0/1678 przypisań**,
na siatce i przy centrach, przy obu promieniach i obu źródłach wektorów.
Geometryczna mediana minimów przy r48 przepuszcza jedno znane miejsce
siatki, z którego nie powstaje fragment.

Nie wynika to głównie z braku rodziny: przy r24 na siatce ocena jest
dostępna w 1874/1916 otoczeń dla obrazu i 1840/1916 dla geometrii.
Najlepszy wynik obrazu to .8241 przy progu .8791; mediana minimów
osiąga maksymalnie .6574 przy .6976, a mediana średnich .8054 przy .8500.
Dokładne rozkłady, dostępność i etapy odmów są w wynikach maszynowych.

Zgodność centrów przy r48 daje częściowy wynik:

| Miejsca / propozycja | Przypisane oznaczenia | Udział wszystkich 1678 |
| --- | ---: | ---: |
| Siatka / obraz | 292 | 17.4% |
| Siatka / centra | 279 | 16.6% |
| Centra / obraz | 296 | 17.6% |
| Centra / centra | 275 | 16.4% |

Wszystkie należą do BLACK: 1303 oznaczenia odniesienia. RED (101) i YELLOW
(274) nadal nie mają przypisań. Brak ocenianych par między różnymi
regionami oznacza brak podstaw do oceny scaleń, a nie udowodnione zero błędów.
Zachowany DINO/centra/HDBSCAN nadal odrzuca wszystkie grupy wyglądu;
pozostałe podziały sieci nie dają tu przewagi nad samym porządkiem/łącznością.

Nowo skalibrowana **pojedyncza para geometrii** przy r48 daje jeszcze
21 przypisań na siatce. To efekt zmiany kalibracji .9364 → .4124,
nie korzyść oceny wielu przesunięć. Wszystkie poprzednie warianty pozostają
dokładnie odtworzone jako oddzielne konfiguracje porównawcze.

## Wynik 3: zmienny wygląd i błędy pozycji nadal są trudne

Nowe kontrole, trzy ziarna, siatka r24, propozycje obrazu, sam porządek
i łączność; procent przypisanych oznaczeń:

| Kontrola | Jedna para | Najlepsza para | Mediana minimów | Mediana średnich |
| --- | ---: | ---: | ---: | ---: |
| Jedna regularna sieć | 79.7% | 76.7% | 79.7% | 79.7% |
| Losowe amplitudy poszczególnych molekuł | 24.6% | 1.4% | 27.1% | 24.7% |
| Zmienne kształty molekuł | 76.6% | 14.7% | 78.0% | 74.5% |
| Większy szum | 0% | 0% | 0% | 0% |
| Zaburzenia pozycji sigma .6 px | 1.7% | 0% | 1.5% | .5% |
| Losowe amplitudy, obrót 27° | 17.6% | 0% | 23.1% | 4.4% |

Zmienne amplitudy rozbijają jedną sieć na kilka fragmentów. Mediana
minimów pomaga w części przypadków, lecz nie usuwa problemu. Losowa
jasność każdej molekuły nie jest globalną zmianą kontrastu, względem
której Pearson byłby niezmienniczy. Sama enumeracja baz nie daje też
tolerancji na błędy położeń ani dopasowania podpikselowego.

Przy r48 zgodność centrów z propozycji obrazu zachowuje 87.6% oznaczeń
przy zmiennych amplitudach i 88.3% przy zmiennym kształcie/szumie.
Przy sigma .6 px daje 82.8%, a przy 1.2 px już 0%. Na tych kontrolach
centra są dostarczone z generatora nawet przy silniejszym szumie obrazu;
nie należy tego przedstawiać jako odporności detekcji molekuł na szum.

## Wynik 4: więcej akceptacji ma koszt

- Nowe niezależne rzędy, r24: pojedyncza para daje **26/768** błędnych
  miejsc, najlepsza para 4/768, mediana minimów 25/768, średnich 28/768.
  Mniejsza liczba błędów najlepszej pary idzie wraz z dużą utratą poprawnych
  sieci o zmiennych amplitudach i kształtach.
- Pusta przerwa, r48: mediany obrazu przypisują **84/96** i **78/96** miejsc
  w pustym pasie, tworząc trzeci, pozorny fragment. Udział scaleń poprawnych
  płatów jest przy tym zerowy — samo mierzenie scaleń przeoczyłoby błąd.
- Granica przesunięcia, r48: obie mediany obrazu i zgodność centrów scalają
  dwa płaty we wszystkich trzech realizacjach. **100% ocenianych par
  z różnych domen trafia do wspólnego fragmentu.**
- Zgodność centrów przy r48 poprawnie pozostawia pustą przerwę, lecz
  przypisuje **33/768** miejsc niezależnych rzędów. Przy r24 z progiem 1
  nie przypisuje niczego, również poprawnych sieci.

To wciąż brak ogólnej metody. Kierunek/rozstaw, lokalna powtarzalność,
obecność materiału w środku okna i zgodność fazy przy granicy wymagają
oddzielnego sprawdzenia; jedna mediana nie rozstrzyga wszystkich tych kwestii.

## Weryfikacja, koszt i odtworzenie

- 24 kontrole równoważnych rodzin i 96 ocen przy zmianie znaków/kolejności
  oraz baz unimodularnych; przykład klatki 250 i brak prawidłowej bazy.
- 864 porównania korelacji z poprzednim bezpośrednim rachunkiem,
  błąd ≤1.39e-16. **804 odtworzone tablice** pojedynczych par,
  błąd ≤1.12e-15. **3816 dokładnych wyników bazowych**.
- **165 pomiarów i 165 predykcji / 24804 wyników** odtworzono identycznie
  przy zablokowanych odczytach referencji. 132 pary tablic obrazu nie
  zmieniły się po usunięciu samych oznaczeń. Wskaźnik zgodności centrów
  jest z tego sprawdzenia świadomie wyłączony.
- 56818 zgodnych rodzin rzeczywistych wejść daje **227272 identyczne
  oceny**. 42 deterministyczne odtworzenia nowych obrazów i masek.
- **343 kontrole QtWebEngine**, brak błędów JS; obejrzano podgląd i wykres.
  Sprawdzono składnię Python/Bash. Nie testowano natywnego GUI aplikacji.

Przed oceną referencji poprawiono dwie usterki zapisu wyników i manifestu.
Ponowiono wszystkie pomiary; potwierdzono niezmienione oceny we wszystkich
165 obrazach oraz niezmienione progi. Poprawki nie zmieniły kryteriów
ani budżetu prób. Weryfikacja programu nie oznacza przyjęcia metody.

CPU: cztery procesy, po jednym wątku BLAS/OpenMP. Pomiary starego zestawu
153.98 s, nowych obrazów 64.41 s, predykcje 4.17 s, ocena 7.05 s,
pełne ponowienie i weryfikacja 232.03 s. Są to czasy końcowych etapów,
nie całkowity czas sesji wraz z poprawkami i budową podglądu.
Maksymalny RSS procesu pomiarowego 138200 KiB (~135 MiB); łącznego szczytu
nie mierzono. Bez GPU, nowych wag i instalowania zależności.
Kopia lokalna: **444 pliki / 158992656 B**, wszystkie SHA-256 zgodne;
potem dopisano potwierdzenie kopii. Dane i duże wyniki pozostają poza Git.

Odtworzenie: `bash stmdomains/prototypes/run-translation-family.sh` ze
wskazanej gałęzi prototypu, przy zachowaniu poprzednich lokalnych artefaktów.
Etapy uruchomiono osobno; wrapper sprawdzono składniowo. HTML jest
samowystarczalny: 24 klatki TTMAPP, 18 starszych przypadków i 14 nowych
przypadków, po jednym ziarnie do podglądu. Pełne tabele obejmują trzy ziarna.

## Co dalej w 19

**19 pozostaje `claimed`, do omówienia; 20 nadal odłożone.** Zachowujemy
kanoniczną rodzinę jako poprawkę niezależności od bazy, bez uznawania jej
za gotowe kryterium domeny. Kolejna propozycja powinna zbadać **lokalne
dopasowanie struktury z tolerancją pozycji oraz osobną kontrolą zgodności
fazy między sąsiadującymi otoczeniami**. Samo łagodzenie agregacji
przesunięć lub zwiększanie okna nie rozwiązuje pokazanych błędów.

Taki eksperyment powinien oddzielić zmienny wygląd molekuł od ich układu,
porównać wynik ze strukturami o niezależnych fazach rzędów oraz zachować
kontrole pustej przerwy i granicy przesunięcia. Braki centrów nadal muszą
być jawne. Użyte tu syntetyki stają się materiałem rozwojowym; kolejne
nieużyte realizacje trzeba odłożyć przed doborem parametrów. Nie uruchomiono
tej kolejnej próby, treningu, pełnych 268 klatek ani wdrożenia do aplikacji.
