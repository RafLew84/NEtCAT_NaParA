# Rejestracja względem kilku klatek i kolejne algorytmy

Stan przeglądu: 2026-10-31. Dotyczy STM Viewer, gałęzi
`viewer/registration-difficult-movies`, kodu `5b7ab58`.
To rozpoznanie i propozycje kolejnych prób; nie zmienia zakresu ticketów ani aplikacji.
W tym zadaniu nie uruchamiano nowych matcherów ani optymalizacji grafu na pomiarach.

Późniejsze zlecenie z 2026-10-31 przeniosło rekomendacje do
[planu i ticketów](registration/README.md). Poniższa notatka zachowuje stan
badania z commita `903dfac`; aktualną kolejność i zakresy prowadzi plan.

## Rekomendacja

W eksperymencie wieloklatkowym najpierw warto sprawdzić **ten sam Deep Matcher,
ale z dopasowaniem do kilku
klatek i wspólnym wyznaczaniem przesunięć całej serii**. Pozwoli to ocenić zmianę
sposobu łączenia wyników niezależnie od zmiany algorytmu dopasowującego parę.
Pierwszy wariant: graf translacji z oknem 3–5 klatek, odporne dopasowanie do
pomiarów par oraz jawna informacja o niepewnych lub brakujących połączeniach.
Nie dokładamy założenia o gładkości, kierunku ani maksymalnej szybkości dryfu.

W obecnym planie najbliższym etapem pozostaje przestrzenna ocena poparcia
dopasowania z REG-05:
czy przesunięcie wynika z kilku części próbki, czy przede wszystkim z jednego
zakłóconego pasa. Ta informacja będzie też ważna przy interpretacji grafu.
Nowe modele dopasowujące pary można potem porównać przy
niezmienionym sposobie łączenia wyników. To priorytety wynikające z problemów
użytkownika i ograniczeń obecnej implementacji, a nie opublikowany ranking
metod dla MOVIE_4/MOVIE_8.

## Co wiemy lokalnie

- Według oględzin użytkownika Deep Matcher wyglądał najlepiej w pierwszych
  100 klatkach MOVIE_4, z wymienionymi wyjątkami. Numeracja dotyczy serii po
  usunięciu dwóch pierwszych, błędnie dołączonych klatek: bieżąca 29→30 to
  źródłowa 31→32. Ta obserwacja nie obejmuje całego filmu.
- REG-04 dodał Deep Matcher → ECC, nadal dla kolejnych par. Na syntetycznej
  scenie ze znanym ruchem ECC poprawiał błąd podpikselowy, ale na scenie
  z nieruchomymi pasami potrafił pogorszyć dobry wynik Deep o wiele pikseli.
  Sam wynik zakończonego przebiegu ECC nie świadczy o fizycznej poprawności.
- Oba warianty przeszły techniczną próbę pełnych MOVIE_4 i MOVIE_8. Rozmiar
  końcowego płótna i wykonanie eksportu nie rozstrzygają, który film jest
  lepiej dopasowany. Nie ma jeszcze manualnego odbioru REG-04.

Źródło tych wyników i ich warunków: [lokalny raport REG-04](registration/deep-ecc-results.md).

Obecny Deep nie uśrednia bezpośrednio wszystkich dopasowanych punktów.
Wybiera grupę zgodnych wektorów według ważonego poparcia, a potem używa
ważonej mediany. Dlatego „dodajmy RANSAC” nie opisuje wystarczająco nowej
funkcji. REG-05 powinien wnosić rozkład przestrzenny poparcia, ocenę konkurujących
grup i lokalne poszukiwanie odpowiedników, zgodnie z istniejącym ticketem.
Publiczny wynik backendu zawiera XY i zbiorczą ocenę; nie zachowuje pełnej mapy
punktów/inlierów. Graf może korzystać z XY, ale wizualna diagnostyka konsensusu
wymaga dodatkowych danych z adaptera.
Źródła: [Deep Matcher](../../nanotrack/registration/deep_matcher.py),
[REG-05](registration/issues/05-local-consensus.md).

## Jak użyć kilku klatek

Algorytm pary i sposób połączenia par to dwie różne decyzje. Deep, Optical Flow,
ECC lub korelacja mogą dostarczać pomiary do grafu, jeśli zwracają przesunięcie
w ustalonym układzie współrzędnych. Na pierwszą próbę proponujemy Deep, ponieważ
ma obecnie najlepsze częściowe obserwacje użytkownika. Nie oznacza to obowiązku
stosowania Deep w każdym późniejszym wariancie.

Zamiast mierzyć wyłącznie 2 względem 1, 3 względem 2, 4 względem 3 itd., mierzymy
np. klatkę 5 względem 4, 3 i 2. Każdy pomiar mówi, jakie ma być względne
położenie dwóch klatek. Program szuka takich globalnych XY, które możliwie
zgodnie spełniają wszystkie te relacje. Nie wolno po prostu uśrednić wektorów
5→4, 5→3 i 5→2: każdy ma inny punkt odniesienia.

Podczas analizy gotowego filmu można użyć także klatek późniejszych. Okno
`|i-j| ≤ k` oznacza jedną krawędź dla każdej nieuporządkowanej pary w tym
zasięgu, a nie liczenie dwukrotnie tego samego połączenia. Dodatkowy pomiar
w odwrotnym kierunku może być diagnostyką, lecz nie jest niezależnym pomiarem
nowej części próbki. Propozycja nie wymaga odtwarzania filmu w czasie rzeczywistym.

Bezpośrednią analogię mikroskopową daje Savitzky i współautorzy: rejestracja
wszystkich par niskosygnałowych obrazów cryo-STEM dostarcza nadmiarowych relacji,
które pomagają znaleźć błędne dopasowania i wyznaczyć wspólne przesunięcia.
Autorzy opisują również mylne dopasowania okresowej sieci o komórkę elementarną.
To **STEM, nie STM**. Przejmujemy pomysł nadmiarowych relacji, nie założenia
fizyczne eksperymentu ani końcowe uśrednianie klatek.
Źródła: [publikacja, Ultramicroscopy 2018](https://doi.org/10.1016/j.ultramic.2018.04.008),
[preprint autorów](https://arxiv.org/abs/1710.09281),
[kod autorów](https://github.com/bsavitzky/rigidRegistration).

Innym przykładem jest Zorro: ważona rejestracja względem wielu odniesień
w cryo-TEM, z osobną oceną wyników. Potwierdza sens takiej architektury,
lecz model szumu i procedurę walidacji trzeba dostosować do STM.
Źródło: [McLeod i współautorzy, 2017](https://www.sciencedirect.com/science/article/abs/pii/S1047847716302520).

## Proponowany model obliczeniowy

Poniższy zapis jest propozycją dla STM Viewer:

- `d_ij`: zmierzone przesunięcie, które nakłada oryginalną klatkę `j` na `i`;
- `p_i`: przesunięcie oryginalnej klatki `i` do wspólnego płótna;
- `r_ij = (p_j - p_i) - d_ij`: rozbieżność relacji, w pikselach oryginału;
- `p_0 = (0, 0)`: ustalenie początku wspólnego układu.

Przy poprawnym dopasowaniu `p_j - p_i = d_ij`. Pierwszy wariant rozwiązuje
ważone najmniejsze kwadraty: sumę `w_ij * ||r_ij||²`. Wariant odporny zastępuje
karę kwadratową funkcją Hubera od długości wektora, np.
`sum(w_ij * Huber_delta(||r_ij||))`. Próg `delta` ma jednostkę pikseli i należy
do zapisanej konfiguracji próby. Odporność ogranicza wpływ odstających relacji;
nie gwarantuje znalezienia prawdziwego ruchu przy dominującej błędnej zgodności.

To uproszczony graf pozycji: dwa parametry na klatkę, bez obrotu i deformacji.
Oficjalny przykład Ceres pokazuje analogiczne budowanie kosztu z relacji par
oraz unieruchomienie pierwszej pozycji, które usuwa dowolność wspólnego
przesunięcia. Nie trzeba jednak dodawać Ceres jako zależności do tego
niewielkiego problemu translacyjnego.
Źródło: [przykład grafu pozycji 2D w Ceres](https://github.com/ceres-solver/ceres-solver/blob/master/examples/slam/pose_graph_2d/pose_graph_2d.cc).

### Solvery i wagi

| Wariant | Rola w próbie | Ograniczenie |
| --- | --- | --- |
| Rzadki układ liniowy, zwykłe/ważone LS | Prosta baza do zmierzenia samego efektu kilku odniesień | Błędne krawędzie mogą przesunąć wiele klatek |
| IRLS + Huber dla całej krawędzi XY | Pierwszy proponowany wariant odporny; w kolejnych iteracjach zmniejsza wspólną wagę X/Y odstającej pary | Potrzebuje nadmiarowych poprawnych relacji oraz jawnego progu |
| Odporna funkcja `soft_l1` | Alternatywa do kontrolowanego porównania z Huberem | Inna funkcja kosztu sama nie usuwa niejednoznaczności obrazu |
| Odrzucanie krawędzi na podstawie cykli | Ewentualny dalszy eksperyment | Jeden niespójny cykl nie identyfikuje jednoznacznie winnej pary; można zerwać graf |

W IRLS każdy krok jest ważonym liniowym LS i może używać
`scipy.sparse.linalg.lsmr`. Solver obsługuje macierze rzadkie oraz raportuje
przyczynę zakończenia i oszacowanie uwarunkowania. `damp=0` nie dodaje
regularizacji. Nie wprowadzamy ukrytej kary przyciągającej XY do zera ani
wygładzania trajektorii.
Źródło: [SciPy — LSMR](https://docs.scipy.org/doc/scipy/reference/generated/scipy.sparse.linalg.lsmr.html).

Istotny detal implementacyjny: `scipy.optimize.least_squares(loss="huber")`
stosuje funkcję straty osobno do każdej składowej residual. Spłaszczenie XY
nie daje automatycznie jednej odpornej wagi dla pary. Jeśli chcemy karać
normę 2D, należy jawnie zastosować taki model, np. opisany blokowy IRLS.
Ceres opisuje funkcję straty dla normy całego bloku residual; SciPy udostępnia
m.in. Huber, `soft_l1` i rzadkie Jacobiany. To wybór modelu, nie tylko nazwy solvera.
Źródła: [SciPy — least_squares](https://docs.scipy.org/doc/scipy/reference/generated/scipy.optimize.least_squares.html),
[Ceres — residual blocks i loss functions](https://ceres-solver.readthedocs.io/latest/nnls_modeling.html).

Na początku warto porównać równe wagi zaakceptowanych pomiarów z jawnymi wagami
jakości. Liczba dopasowań, rozkład po obrazie, reszty lokalne i jednoznaczność
mogą być dowodami jakości, ale żadna z tych liczb nie jest automatycznie
prawdopodobieństwem poprawnego dryfu. Nie mieszamy surowego score LoFTR,
korelacji ECC i wyniku Optical Flow jako porównywalnych wag.

## Jak wybierać połączenia

| Strategia | Co daje | Proponowane użycie |
| --- | --- | --- |
| Tylko poprzednia klatka | Obecny prosty łańcuch | Baza porównania |
| Każda względem pierwszej | Brak sumowania błędów kolejnych kroków | Osobna próba, gdy pierwsza klatka pozostaje reprezentatywna i ma wspólny obszar |
| Okno 3–5 klatek | Kilka dróg połączenia przy umiarkowanym koszcie | Pierwsza propozycja grafu |
| Okno + klatki odniesienia w dalszych częściach filmu | Potencjalna kontrola dryfu na dłuższej odległości | Następny eksperyment; tylko tam, gdzie nadal istnieją wspólne struktury |
| Wszystkie pary | Najwięcej relacji i kosztów | Krótkie fragmenty badawcze; nie domyślnie cały MOVIE_4 |
| Dopasowanie do wzorca ze stosu obrazów | Może poprawić sygnał wzorca, wymaga iteracji | Późniejsza alternatywa dla stabilnej sceny |

Liczba pomiarów dla okna `k` przy `n > k` wynosi
`k*n - k*(k+1)/2`; dla wszystkich par `n*(n-1)/2`.
To liczba kandydatów, przed odrzuceniem niewykonalnych par:

| Seria | Sąsiednie pary | Okno 5 | Wszystkie pary |
| --- | ---: | ---: | ---: |
| MOVIE_4 po usunięciu dwóch pierwszych klatek: 362 | 361 | 1795 | 65341 |
| MOVIE_8: 84 | 83 | 405 | 3486 |

Są to obliczenia liczby połączeń, nie pomiary czasu. Wzrost liczby klatek nie
musi zawsze poprawiać estymacji: analiza Aguerrebere i współautorów wykazuje
zależność korzyści od SNR w modelu przesuniętych zaszumionych obserwacji tej
samej sceny. Tego wyniku nie można bezpośrednio przenieść na tearing i zmiany
molekuł, ale przestrzega przed utożsamianiem większej liczby par z lepszą jakością.
Źródło: [Fundamental Limits in Multi-image Alignment, 2016](https://arxiv.org/abs/1602.01541).

Własny wniosek dla tych filmów: szablon będący medianą lub średnią już
przesuniętych obrazów nie powinien być pierwszym krokiem. Zmieniające się
molekuły i błędna inicjalizacja mogą utworzyć rozmyte lub podwójne struktury.
Jeżeli go sprawdzimy, będzie tylko materiałem pomocniczym estymacji. Zapisany
film nadal zachowa osobne klatki pomiarowe.

## Co graf może przeoczyć

Poniższe ograniczenia wynikają z proponowanego modelu i potrzebują testów:

1. **Łańcuch lub drzewo bez nadmiarowych relacji.** Można spełnić dokładnie
   wszystkie przesunięcia, również błędne. Mała reszta optymalizacji niczego
   wtedy nie sprawdza.
2. **Most między fragmentami grafu.** Jedyne połączenie dwóch dużych części
   filmu może przenieść błędne XY na całą dalszą część bez wywołania konfliktu
   cyklu. Sama spójność grafu jest konieczna, ale nie wystarcza do dobrej oceny.
3. **Rozłączny graf.** Położenie dwóch komponentów względem siebie jest
   nieokreślone. Osobne ustawienie obu początków na zero nie tworzy jednego
   poprawnego układu filmu. Trzeba odmówić wspólnego wyniku lub jawnie
   udostępnić osobne dopasowania, zgodnie z ustalonym kontraktem.
4. **Spójny błąd.** Okresowy wzór może dać błędne, lecz zgodne cykle.
   Zakłócenie obecne w wielu klatkach też może zdominować wiele połączeń.
   Odporne LS nie wie samo, które struktury są próbką.
5. **Powiązane błędy.** Połączenia współdzielą klatki i artefakty. Nie należy
   traktować tysięcy krawędzi jak tysięcy niezależnych obserwacji ani przedstawiać
   formalnej kowariancji LS jako skalibrowanej pewności fizycznej.
6. **Rzeczywisty ruch i tearing.** Model wyznacza jedno XY na klatkę.
   Gdy różne obszary poruszają się inaczej, nie można idealnie nałożyć ich
   wszystkich translacją. Nie kasujemy ruchu molekuł przez lokalną deformację
   ani przez karę za zmianę kierunku trajektorii.

Nieudane dopasowanie pary oznacza **brak krawędzi**, nie przesunięcie `(0, 0)`.
Nowy wariant grafowy mógłby korzystać z innych połączeń, jeżeli pozostała
struktura nadal pozwala oszacować XY i ocenić poparcie. Musiałby jawnie
raportować pominięte pary, mosty i izolowane klatki. Nie interpolujemy XY
w czasie ani nie zmieniamy algorytmu pary po cichu. To byłaby osobna,
zaprojektowana polityka nowej metody; obecne zachowanie błędu rejestracji
serii nie zmienia się przez samą publikację tej notatki.

## Integracja z obecnym programem

**Aktualizacja planu — 2026-11-01:** użytkownik usunął osobny REG-08,
który miał wyłącznie diagnozować spójność trójek. Po odebranym zapisie sesji
REG-07 następuje [REG-08a — graf dopasowań](registration/issues/08a-window-graph.md).
Nie wymagamy wcześniejszego panelu trójek ani jego odbioru. Spójność relacji
pozostaje informacją pomocniczą rozwiązania grafu.

Poniższy podział opisuje pierwotną propozycję z przeglądu; aktualne numery,
zakresy i zależności określa [plan](registration/README.md). Każdy realizowany
etap kończy się próbą w aplikacji:

1. **Próba grafu na kopii wyniku:** wybór okna, obliczenie par, LS/Huber,
   lista braków i rozbieżności, podgląd względem bieżącego aligned. Odbiór:
   porównanie tych samych klatek i struktur z bazowym Deep; anulowanie
   zachowuje aktywny film.
2. **Użycie sprawdzonego wyniku w filmie:** świadome zastosowanie próby,
   zapis konfiguracji i źródłowych relacji, ponowny odczyt oraz eksport.
   Odbiór: zgodne XY w podglądzie i pliku, poprawna geometria i braki danych.
3. **Dalsze odniesienia lub nowy matcher:** dopiero po osobnym porównaniu,
   ze stałym zbiorem przypadków i manualnym odbiorem.

Zgodnie z aktualnym planem LS należy do REG-08a, Huber do REG-08b,
a zastosowanie do filmu do REG-08c. REG-05 zachowuje lokalne poparcie,
REG-06 pozostaje odłożony, a REG-07 dostarcza zapis i odczyt sesji. Wizualna
ocena filmów służy odbiorowi wpływu rejestracji wieloklatkowej.

Dwa szczegóły wymagają jawnego projektu przed implementacją:

- **Korekty manualne.** Obecna korekta pary przesuwa dalszą część łańcucha.
  Globalna optymalizacja może zmienić pozycje po obu stronach poprawianej pary.
  Trzeba zdecydować, czy ręczne XY jest twardym ograniczeniem, miękką wskazówką,
  czy wyklucza ponowną optymalizację danego wyniku. Nie wolno po cichu nadpisywać
  korekty użytkownika. Sprzeczne twarde ograniczenia wymagają wskazania konfliktu.
  Źródło obecnego kontraktu: [REG-02a](registration/issues/02a-manual-movie-corrections.md).
- **Próbkowanie obrazów.** Wszystkie estymatory pracują na ustalonych danych
  oryginalnych lub ich jawnych kopiach pomocniczych. Finalne XY stosujemy
  do oryginału raz, zachowując jedno globalne przesunięcie na klatkę i ważność
  próbek. Nie wykonujemy kolejnych interpolacji wcześniej wyrenderowanego aligned.

Graf można zaimplementować w STM Viewer. Rozszerzenia backendów wspólnych
należy zgłosić do sesji integracyjnej; nowe adaptery i diagnostykę utrzymujemy
najpierw w zakresie aplikacji, zgodnie z [zasadami współpracy](../PARALLEL_DEVELOPMENT.md).

## Dodatkowe algorytmy par — kandydaci do prób

Poniższa kolejność jest propozycją prób, nie twierdzeniem o jakości na STM.
W sprawdzonych źródłach nie znaleziono benchmarku tych modeli na naszych
filmach ani potwierdzenia, że rozwiążą problem tearingu.

| Priorytet | Kandydat i stan publikacji | Co faktycznie wnosi | Hipoteza do sprawdzenia na STM |
| --- | --- | --- | --- |
| 1 | EfficientLoFTR, CVPR 2024 | Rozwinięcie LoFTR z agregacją uwagi i doprecyzowaniem korespondencji | Czy dokładniejsze punkty poprawią translację bez kolejnego globalnego ECC? |
| 2 | RoMa v2, preprint 2025, ECCV 2026 | Gęste korespondencje, DINOv3 i osobny etap doprecyzowania | Czy poparcie z większej części obrazu jest przydatniejsze przy słabej teksturze? |
| 3 | MatchAnything, preprint 2025, TPAMI 2026 według repozytorium autorów | Trening między modalnościami; warianty oparte na ELoFTR/RoMa | Czy zmiana treningu pomaga na teksturze różnej od fotografii? |

**EfficientLoFTR** jest najbliższym porównaniem do istniejącego Deep.
Autorzy udostępniają kod, przykład pracy na skali szarości i wagi. Jednocześnie
wprost wskazują ograniczenie domeny treningowej MegaDepth i najlepsze działanie
na scenach outdoor; nawet indoor wymaga uwagi. Nowszy LoFTR nie oznacza zatem
modelu wytrenowanego do mikroskopii.
Źródła: [publikacja](https://arxiv.org/abs/2403.04765),
[implementacja autorów](https://github.com/zju3dv/EfficientLoFTR).

**RoMa v2** dostarcza gęste dopasowania oraz informacje o pokryciu i precyzji.
Preprint pojawił się 19.11.2025; sprawdzona wersja 3 z 06.07.2026 jest oznaczona
jako ECCV 2026 camera ready. Kod i ścieżka uruchamiania są publiczne. W naszym
wariancie z korespondencji nadal obliczalibyśmy tylko jedną translację XY.
Gęste pole byłoby materiałem estymatora, a nie pozwoleniem na deformację
obrazu pomiarowego. Nie potwierdzono lokalnie czasu ani zużycia 8 GB VRAM.
Źródła: [publikacja](https://arxiv.org/abs/2511.15706),
[kod i API autorów](https://github.com/Parskatt/RoMaV2).

**MatchAnything** jest szczególnie interesujący jako kontrola wpływu treningu:
porównujemy zwykły ELoFTR z wariantem MatchAnything-ELoFTR przy tym samym
konsensusie translacji i tym samym grafie. Autorzy udostępniają modele/inference
przez wskazane repozytoria Hugging Face. Sukces dopasowania między modalnościami
nie dowodzi odporności na zakłócenia skanowania STM.
Źródła: [publikacja](https://arxiv.org/abs/2501.07556),
[strona projektu](https://zju3dv.github.io/MatchAnything/),
[repozytorium autorów](https://github.com/zju3dv/MatchAnything).

Przy późniejszej integracji trzeba przypiąć wersję kodu i warunki wybranych
wag. Na dzień przeglądu główne gałęzie EfficientLoFTR i MatchAnything wskazują
PRL v1.0/2026, a RoMa v2 ma kod MIT z osobnymi warunkami DINOv3.
Nie są to jednakowe pakiety licencyjne.
Źródła: [EfficientLoFTR LICENSE](https://raw.githubusercontent.com/zju3dv/EfficientLoFTR/main/LICENSE),
[MatchAnything LICENSE](https://raw.githubusercontent.com/zju3dv/MatchAnything/main/LICENSE),
[RoMa v2 — warunki i zależności](https://github.com/Parskatt/RoMaV2).

Dalsza lista obserwacyjna może pozostać krótka: **LightGlue + ALIKED** pozwala
osobno wyznaczać cechy klatki i dopasowywać je w parach; przechowywanie raz
wyznaczonych cech dla wielu połączeń jest naszą propozycją oszczędności obliczeń,
nie argumentem za lepszą jakością STM. **TartanMatch**, preprint z 10.10.2026,
ma publiczny kod i wagi oraz trening na kilku modalnościach, ale w deklarowanym
zakresie nie ma STM. Sama świeżość pracy nie uzasadnia dodawania następnego
obowiązkowego wariantu przed oceną trzech głównych kandydatów.
Źródła: [LightGlue](https://github.com/cvg/LightGlue),
[TartanMatch — publikacja](https://arxiv.org/abs/2610.14513),
[kod](https://github.com/castacks/tartanmatch),
[wagi autorów](https://huggingface.co/theairlabcmu/TartanMatch).

## Powtarzalny eksperyment

Zmieniać po jednej rzeczy. Proponowana macierz:

| Próba | Matcher pary | Łączenie | Pytanie |
| --- | --- | --- | --- |
| A | Obecny Deep, te same wagi i parametry | Poprzednia klatka | Baza |
| B | Jak A | Okno 3/5, zwykłe LS | Czy same dodatkowe relacje pomagają? |
| C | Dokładnie pomiary z B | Odporny graf | Czy odporność ogranicza wpływ złych krawędzi? |
| D | Deep z nowym przestrzennym konsensusem | Ten sam wybrany wariant grafu | Czy problemem pozostaje lokalizacja poparcia? |
| E | Jeden nowy matcher naraz | Ten sam wariant łączenia | Czy zmiana modelu daje dodatkową poprawę? |

Deep→ECC z REG-04 pozostaje osobnym porównaniem, a nie obowiązkowym etapem
każdej próby grafu. Nie nadajemy mu większej wagi dlatego, że optymalizuje
wynik Deep. Konfiguracje, wersje bibliotek, sumy kontrolne wag, źródła klatek,
obsługę błędów i budżet zasobów zapisujemy razem z próbą.

Zestaw syntetyczny powinien obejmować znane XY ze zmianami kierunku,
pojedynczą błędną parę, klatkę bez wiarygodnego połączenia, most,
rozłączne komponenty, okresowy wzór z fałszywą zgodnością, nieruchome pasy
oraz różny ruch góry i dołu. Mierzymy błąd pozycji i relacji względem znanej
prawdy, a także jawne odmowy. Gładka trajektoria nie jest kryterium poprawności.

Na MOVIE_4 zawsze usuwamy źródłowe klatki 1 i 2. Oglądamy podane przez
użytkownika pary 29→30, 35→36, 44→45→46, 61→62, 94→95→96→97, potem pierwsze
150 oraz cały pozostały film. MOVIE_8 oceniamy oddzielnie, żeby nie stroić
wszystkiego do jednego filmu. Porównujemy te same struktury przy tym samym
zoomie i kontrastach, zapisując również obszary z rzeczywistymi zmianami próbki.

Ocena dopuszczająca krawędź do grafu i jej waga są częścią estymatora.
Fragmenty kontrolne z [REG-06](registration/issues/06-independent-validation.md)
pozostają poza estymacją danej próby i nie służą do poprawiania XY, wyboru
krawędzi ani strojenia progu Hubera. Przypadki wielokrotnie oglądane podczas
rozwoju są danymi rozwojowymi; końcowy odbiór wymaga także nowych przypadków.

Raport powinien rozdzielać: jakość obrazową, liczbę odmów/niepewnych klatek,
reszty grafu, czas estymacji par, czas solvera i renderowania, RAM oraz VRAM.
Docelowe 8 GB VRAM wymaga pomiaru na takim sprzęcie lub wiarygodnego testu
pamięci — działanie wcześniejszych prób na RTX 5090 z 32 GB nie jest tym testem.
