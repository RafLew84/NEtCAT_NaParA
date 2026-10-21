# Granice przesunięcia sieci — wynik próby

Data: 2026-10-21. [Zadanie 12](issues/12-phase-boundaries.md).
Źródła: **`prototype/stmdomains-boundaries`, `c33cc5b`** — nie scalać do aplikacji.
Dokumentacja: `domains/phase-boundaries`.

## Wniosek

Wykonano 7 wariantów na 19 kontrolach syntetycznych i na 54 wnętrzach z 18 klatek
TTMAPP. **Próba jest zakończona; nie wybrano metody produkcyjnej.**
Niedopasowanie wektorów między centrami do oszacowanej sieci rozdziela dwie
kontrolne domeny przy przesunięciu 4/8 px i jednakowej orientacji. Zachowuje
jedną domenę po przesunięciu całego wzoru, pojedynczych defektach i ucięciu
brzegiem. Samo porównanie kąta nie wykrywa tych granic przesunięcia.

Ten wynik dotyczy prostych obrazów z dokładnymi centrami. Wariant nie wykrywa
przesunięcia 1 px, jest zależny od kompletności centrów oraz wymaga wiarygodnej
lokalnej sieci. Dwa wymagane piki widma udało się przyjąć tylko w **7/54**
wnętrz TTMAPP. Nie jest to odsetek wnętrz z prawdziwym uporządkowaniem.

Prosta analiza lokalnej fazy obrazu daje zarówno wielokrotne cięcia jednej
linii, jak i brak wskazania prawdziwej granicy. Odwrócenie kontrastu potrafi
utworzyć fałszywy podział bez przemieszczenia centrów. Filtrowanie krótkich
wskazań usuwa też część rzeczywistych granic; większe okno nie rozwiązuje
problemu. Nie ma podstaw do budowania z tych wyników powierzchni domen.

## Referencja i tożsamość wejścia

Użyto tych samych [częściowych referencji](partial-domain-reference-audit.md)
co w krokach 10 i 11: klatki 250–254, 256–268, 54 wnętrza, po 18 przykładów
BLACK/RED/YELLOW. Klatki 255 nie ma w zbiorze. Użytkownik wyjaśnił, że kolory
oznaczają głównie różne orientacje tej samej sieci. Ręczne ramki są przybliżone;
nie stanowią dokładnej referencji granicy przesunięcia przy tym samym kącie.
Dlatego **błędy granic liczymy tylko na kontrolach syntetycznych**. Na TTMAPP
pokazujemy dostępność i lokalne wskazania, bez deklaracji błędu konturu.

Analiza realna jest ograniczona do osobnych konserwatywnych wnętrz. Kreska,
pas domknięcia i margines 3 px raw pozostają wyłączone. Rozłączenie pomiędzy
samymi wnętrzami jest narzucone zakresem referencji, a nie wykryciem granicy.
Obszary poza ramkami nie stają się podłożem ani negatywnymi przykładami.
Nie zmieniono masek po obejrzeniu wyniku.

| Źródło | SHA-256 |
| --- | --- |
| `data/TTMAPP/MOVIE_23raw_TTMAPP_I_AU111.MPP` | `8fbbfa5d515a90552c13cee2dbd289ff5cc16f000315547185c2a57bfe9f7c66` |
| `data/TTMAPP/detection_full.moltrack.json` | `d0c4cb999bede28edb5dfd18ddbe146054711382f1c78363055be2330b3cdd2e` |
| Manifest `.scratch/partial-domain-reference` | `30eeda806622d428900d60f6391e749a66a154f53aeb40c8d8f48097c48ef637` |

Sprawdzono hashe MPP, sesji i 36 PNG, kolejność klatek, przesunięcia, padding
oraz mapowanie masek raw/PNG z wyłączeniem kresek i paddingu. Hashe 18 NPZ są
w pochodzeniu wyniku. Obrazy do obliczeń pochodzą z MPP, centra z MolTrack;
nie z PNG z ręcznymi kolorami. Raw 256×256 px, płótno wyrównania 480×408 px,
PNG 960×816 px; padding LTRB 224,139,0,13. Skala fizyczna nie jest ustalona.

Standaryzacja obrazu do obliczeń używa tylko pikseli danego wnętrza. Estymata
sieci wykorzystuje całe to wnętrze; lokalny filtr fazowy dodatkowo wymaga,
aby jego skończone wsparcie w całości się w nim mieściło. Normalizacja całej
klatki i gamma są tylko podglądem. Nie korzystamy z nieoznaczonego otoczenia.

## Kontrole

Bazowa sieć kwadratowa ma rozstaw 16 px, plamki Gaussa σ=2,2 px i szum σ=0,015.
Centra są dokładne. Wspólny obszar badany ma 208×208 px, mały wycinek 64×64 px;
przypadek brzegowy dochodzi do fizycznej krawędzi x=0. Przesunięcie po jednej
stronie pionowej granicy x=128 wynosi 1, 4 lub 8 px w kierunku y. Przykład
skośny ma linię x=128+0,5(y−128), z przesunięciem (0,4) px.

Pozostałe kontrole: globalne przesunięcie (5,3), jeden/trzy oddzielne defekty,
pas losowych pozycji, przerwa materiału szerokości 32 px, obrót jednej strony
o 17°, pozostawienie 25% centrów, pas brakujących detekcji przy niezmienionym
obrazie, kontrast prawej strony ×0,4, odwrócenie jego znaku, sam szum i płaski
obraz. Odwrócenie kontrastu jest kontrolą niejednoznaczności informacji fazowej,
nie modelem konkretnego procesu STM. Wszystkie 19 przypadków jest w HTML.

Referencyjne domeny i linie są używane tylko do oceny. Algorytmy nie otrzymują
ich identyfikatorów ani położenia. Progi są robocze, nie ustalone przez użytkownika;
ten zbiór nie jest niezależnym testem generalizacji na STM.

## Metody i parametry

**Estymata sieci:** usunięcie płaszczyzny we wnętrzu, waga rosnąca przez 12 px
od brzegu, FFT 256². Pasmo okresów 10–28 px; dwa najsilniejsze lokalne maksima
w sąsiedztwie 5×5, oddzielone kątowo: |sin(kąt)|≥0,5. Moc każdego ≥10 median
pasma, drugiego ≥0,15 pierwszego. Promień wpisany we wnętrze musi mieścić
jeden oszacowany okres. To estymata dwóch wektorów odwrotnych K, bez gwarancji,
że są właściwą bazą prymitywną. Nie wprowadzamy znanego rozstawu 16 px do estymatora.

| Wariant | Reguła |
| --- | --- |
| `connect` | Graf Delaunaya centrów, odcinki w całości we wnętrzu, długość ≤1,8 mediany najbliższych odległości. Węzeł wymaga pełnego sąsiedztwa promienia 1,35 najbliższej odległości +1 px i przynajmniej 3 sąsiadów. |
| `angle` | Graf jak wyżej; q4 lub q6 według większego średniego modułu we wnętrzu. Cięcie przy różnicy kąta >12°, jeśli oba moduły ≥0,45. Niepewne kąty pozostawiają połączenie nierozstrzygnięte, a nie automatyczny pas nieporządku. |
| `residual18` / `residual28` | Dla przemieszczenia centrów Δp: max|K·Δp−round(K·Δp)|. Cięcie powyżej 0,18 / 0,28 okresu. K pochodzi z obrazu, więc metoda korzysta z obu źródeł. Bez dwóch pików odmawia wyniku. |
| `phase_raw` | Demodulacja obrazu dwoma wektorami K; filtr Gaussa σ=0,35 mediany okresów, promień ceil(3σ). Siatka co 4 px. Cięcie, gdy zawinięta różnica fazy między sąsiednimi węzłami przekracza 0,045 okresu w którejkolwiek składowej. |
| `phase_long` | Jak wyżej, ale pozostają tylko połączone wskazania o zasięgu ≥3 okresy. Środki przeciętych połączeń łączymy w klaster przy odległości ≤6 px. |
| `phase_wide` | Jak `phase_long`, lecz σ=0,5 okresu. |

Dla fazy wymagamy energii lokalnej >10⁻¹⁰ po standaryzacji i amplitudy każdej
składowej / sqrt(energii) ≥0,16. Brak dwóch pików, pełnego okna lub dostatecznej
amplitudy oznacza brak pomiaru. Są to nieskalibrowane kryteria dostępności.

Informacja fazowa jako źródło przemieszczeń ma podstawę w pracy
[Hÿtcha, Snoecka i Kilaasa](https://doi.org/10.1016/S0304-3991(98)00035-7).
Tutaj wykonano prostą demodulację i próbę wykrycia nieciągłości, nie pełny
pomiar odkształceń GPA. [Peters i in.](https://arxiv.org/abs/1504.06089)
opisują dodatkową fazę zależną od struktury w obrazach TEM; to uzasadnia
sprawdzanie alternatywnych przyczyn sygnału, nie zatwierdza metody dla STM.
Skończone wsparcie filtra określa `radius` w
[SciPy 1.15.2](https://docs.scipy.org/doc/scipy-1.15.2/reference/generated/scipy.ndimage.gaussian_filter.html).

## Jak liczymy błędy

Fragmenty grafu liczymy przed i po cięciu; komponenty <5 punktów pokazujemy
osobno, bez automatycznego usuwania. Dwa fragmenty mogą istnieć już przed
analizą granicy wskutek braku danych. To nie dwie potwierdzone domeny.

- Błędne scalenia: pary dostępnych węzłów z różnych dodatnich domen referencji
  pozostające w jednym komponencie / wszystkie pary z różnych domen.
- Błędne podziały: pary dostępnych węzłów z jednej domeny rozdzielone między
  komponentami / wszystkie pary z tej samej domeny.
- Dostępność: węzły z pomiarem / centra lub pozycje siatki we wnętrzu,
  osobno dla każdej rodziny. Różne miejsca próbkowania nie są wspólnym rankingiem.
- Trafność wskazań: środki przeciętych krawędzi w odległości ≤8 px od znanej
  linii / wszystkie wskazania. Pokrycie: punkty znanej linii co 4 px w odległości
  ≤8 px od wskazania / cała linia we wnętrzu, także jej niedostępne odcinki.
  Raportujemy również średnią odległość wskazania od tej próbkowanej linii.

Tolerancja 8 px to około pół okresu kontroli, nie ustalony dopuszczalny błąd
fizyczny. Środki krawędzi dają rzadkie wskazania, nie dokładny kontur; nie
interpolujemy między nimi przed oceną. Brak wskazań oznacza pokrycie 0 oraz
brak pomiaru błędu położenia. Brak odpowiednich par daje pustą miarę.

Obszar nieuporządkowany i podłoże nie należą do dodatnich domen referencji,
więc są wyłączone z mianowników błędów par. Niskie błędy nie gwarantują poprawnej
klasyfikacji takiego pasa ani kompletnego wyniku. Na TTMAPP wszystkie miary
błędów względem prawdy domen są puste; liczby komponentów są diagnostyką.

## Wyniki kontroli

| Przypadek | Niedopasowanie 0,18 okresu | Faza z filtrem długości |
| --- | --- | --- |
| Jedna sieć / globalne przesunięcie | 1 komponent, bez cięć w obu przypadkach | 1 komponent, bez cięć |
| Przesunięcie 4 px | 115/169 centrów; 2 komponenty; 0% błędów par; 20 wskazań | 1936/2704 miejsc; 4 komponenty; scalenia 4,55%, podziały 12,41% |
| Przesunięcie 8 px | 2 komponenty, 0% błędów par | 1 komponent po odrzuceniu krótkich wskazań; 100% błędnych scaleń |
| Przesunięcie 1 px | Brak cięcia; 100% błędnych scaleń | Brak cięcia; 100% błędnych scaleń |
| Granica skośna | 2 komponenty; 0% błędów par | Usunięte wszystkie wskazania; 100% błędnych scaleń |
| Jeden / trzy oddzielne defekty | 1 komponent, bez cięć | 1 komponent, bez cięć |
| Pas bez uporządkowania | 6 komponentów; obie uporządkowane strony rozdzielone | 47 komponentów; liczne cięcia w pasie |
| Rzeczywista przerwa materiału | 2 komponenty już przed cięciem; brak wskazań linii | 2 komponenty już przed cięciem; brak wskazań linii |
| Ten sam obraz, pas brakujących detekcji | 2 komponenty; 49,89% błędnych podziałów | Nadal 1 komponent, wynik identyczny z pełnymi detekcjami |
| Ten sam obraz, 25% centrów | Tylko 3 dostępne centra, 3 komponenty | Nadal 1 komponent, wynik identyczny z pełnymi detekcjami |
| Zmniejszenie kontrastu ×0,4 | 1 komponent | 1 komponent |
| Odwrócenie kontrastu | 1 komponent, bez cięć | 3 komponenty; 52,38% błędnych podziałów |
| Mały wycinek | Tylko 1 centrum, brak podstaw do oceny dwóch domen | 64 dostępne miejsca, brak cięcia po filtrze długości |
| Ucięcie fizycznym brzegiem | 1 komponent | 1 komponent |
| Sam szum / płaski obraz | Brak pomiaru | Brak pomiaru |

Dla granicy 4 px wariant `residual18` ma 100% wskazań w tolerancji, ale pokrywa
jedynie 38,46% próbkowanej linii; średnia odległość wynosi 7,52 px. Dla 8 px:
pokrycie 76,92%, odległość 7,65 px. Dla granicy skośnej: 80,77%, 2,37 px.
Różnice pokrycia wynikają także z rzadkich położeń środków krawędzi i wymaganej
tolerancji — doskonały podział dostępnych centrów nie daje dokładnego konturu.
Zwiększenie progu do 0,28 zachowuje wykrycie przesunięcia 8 px, lecz scala
przypadki 4 px i skośny. Nie ma tu uniwersalnej tolerancji niedopasowania.

Przy zmianie orientacji o 17° narzucenie jednej estymaty K całemu regionowi
jest niewłaściwe: `residual18` daje 53 komponenty, `phase_long` 421. Nie należy
uruchamiać takiego detektora granic fazy bez sprawdzenia zgodności orientacji.
Wariant `angle` również nie rozcina tutaj grafu na dwie domeny, mimo 10 cięć;
pojedyncze lokalne wskazania nie gwarantują kompletnej granicy.

Większe okno fazowe dla przesunięcia 8 px daje dwa komponenty **bez żadnych
cięć**, poprzez utratę pomiarów w pobliżu granicy. Nie zaliczamy tego jako
wyznaczenia linii. Taki sam mechanizm rozłącza graf na przerwie materiału.
Pas bez uporządkowania, brak detekcji i odsłonięte podłoże wymagają odrębnych
informacji; sama topologia grafu nie odróżnia tych sytuacji.

## Wyniki w częściowej referencji TTMAPP

Dwa piki przyjęto w 6 wnętrzach BLACK (klatki 253, 257–260, 262) i jednym
YELLOW (264), bez RED. Wyznaczone okresy mieszczą się w przybliżeniu 11,61–12,40 px;
nie są zwalidowanym pomiarem fizycznego rozstawu molekuł. Pozostałe 47 wnętrz
nie przechodzi obecnego kryterium dwóch pików. Nie dostrajano go tak, aby
wymusić dostępność w każdej ręcznej ramce.

Poniższe sumy opisują lokalne pomiary i grafy z wielu klatek; **nie są liczbą
unikalnych molekuł ani domen**. Grafy różnych wnętrz są rozłączne z definicji próby.

| Wariant | Dostępne węzły / miejsca | Klatki z pomiarem | Komponenty przed → po cięciu | Wskazania |
| --- | ---: | ---: | ---: | ---: |
| connect | 547 / 1678 | 18 | 36 → 36 | 0 |
| angle | 547 / 1678 | 18 | 36 → 36 | 0 |
| residual18 | 179 / 1678 | 7 | 8 → 10 | 7 |
| residual28 | 179 / 1678 | 7 | 8 → 9 | 4 |
| phase_raw | 1507 / 17718 | 7 | 34 → 239 | 880 |
| phase_long | 1507 / 17718 | 7 | 34 → 159 | 628 |
| phase_wide | 1041 / 17718 | 6 | 9 → 9 | 0 |

Dla mniejszego filtra fazowego pełne okno istnieje w 1859 miejscach wnętrz
z przyjętymi pikami; 352 dodatkowo odpada przez słaby sygnał. Większy filtr
ma 1228 takich miejsc, z których odpada 187. Zniknięcie cięć po zwiększeniu
okna może być utratą czułości, nie poprawą trafności. Żaden z tych wyników
nie mierzy dokładności przybliżonych ręcznych granic.

## Podgląd, odtworzenie i sprawdzenia

Otwórz:
`/home/rlew/projekty/NEtCAT-domains/.scratch/phase-boundaries-trial/index.html`.
Zacznij od „Granica 4 px”, porównaj `residual18` z `phase_long`, potem zobacz
„Jeden defekt”, „Pas bez detekcji”, „Odwrócenie kontrastu” i „Klatka 258”.
Można wyłączyć punkty grafu, pozostawiając same wskazania. Dostępne są dwa
podglądy, wybór metod, gamma, tabele i pięć scenariuszy z 24 krokami.

Na gałęzi prototypu, z katalogu głównego worktree, w środowisku `netcat`:

```bash
python stmdomains/prototypes/phase_boundaries.py \
  --session /home/rlew/projekty/NEtCAT-domains/data/TTMAPP/detection_full.moltrack.json \
  --mpp /home/rlew/projekty/NEtCAT-domains/data/TTMAPP/MOVIE_23raw_TTMAPP_I_AU111.MPP \
  --reference /home/rlew/projekty/NEtCAT-domains/.scratch/partial-domain-reference \
  --review /home/rlew/projekty/NEtCAT-domains/data/ttmapp_frames_250_268_domain_review \
  --out /tmp/netcat-phase-boundaries-reproduction
```

Python 3.12.12, NumPy 2.2.5, SciPy 1.15.2. Interpreter:
`/home/rlew/projekty/conda-migration-ubuntu-20261008/envs/netcat/bin/python`.
Generator SHA-256 `2fffe9c4af535847cd2d32a5eb849c65b5326796093aa359656943ed75454329`;
HTML `4d7671e8441d992b529c8a91e66c01a5ffab3c889145035fafd8fb1cbf50a884`.
Pozostałe hashe i parametry zapisano w `results.json`. Obok HTML są CSV,
raporty inspekcji oraz zrzuty. Dane i duże wyniki pozostają poza Git.

Czas generatora 3,91 s przed końcowym zapisem JSON/CSV, szczyt RSS 588,59 MiB;
HTML 4 500 199 B. Generator wczytuje MPP w całości. To koszt tej lokalnej próby,
nie test czasu, pamięci, anulowania ani otwierania docelowej aplikacji.

Wykonana inspekcja: 95 389 sprawdzeń węzłów we właściwych wnętrzach,
6854 środków cięć, 87 365 pełnych okien fazy; 76 niezależnych sprawdzeń miar
par przez jawne wyliczenie. Potwierdzono 6 identycznych wyników fazowych po
usunięciu samych centrów. Zastąpienie wszystkich pikseli poza referencją
losowymi dużymi wartościami nie zmienia wyników kontroli 4 px ani TTMAPP 258.
Sprawdzono zgodność hashy źródeł i liczebności tabel.

QtWebEngine: 37 przypadków, 7 metod, 24 kroki scenariuszy, wybory, gamma,
nakładki, nawigacja, tabela, reset i brak wyniku — bez błędów JavaScript.
Obejrzano zrzuty kontroli granicy oraz TTMAPP. Sprawdzenia dotyczą eksperymentu;
nie uruchamiano testów aplikacji. Wynik jest gotowy do oceny użytkownika;
nie deklarujemy jego akceptacji metody ani parametrów.

## Dalszy krok

Do [odbioru metod 13](issues/13-method-acceptance.md) przekazujemy wynik:
**warto dalej sprawdzać niedopasowanie wektorów między centrami w obszarach
z wiarygodnie ustaloną siecią i orientacją**. Najpierw trzeba rozwiązać
ograniczenia lokalnej sieci z kroku 11 i rozróżnić przerwę detekcji od materiału.
Faza obrazu może być dodatkowym sygnałem, ale ten prototyp nie uzasadnia
samodzielnego wyznaczania nią domen ani zastępowania odmów sztuczną granicą.

Do późniejszej oceny rzeczywistego błędu potrzebny będzie wskazany przykład
linii niedopasowania przy tej samej orientacji, z tolerancją oznaczenia i
fragmentem po obu stronach. Obecne ramki nadal służą lokalnym próbom;
nie uzależniamy zamknięcia eksperymentu od przygotowania nowych anotacji.
Krok 12 ma status `resolved` jako wykonana próba. Pytania 04 i 13 pozostają
otwarte; nie zaimplementowano segmentacji ani powierzchni domen w aplikacji.
