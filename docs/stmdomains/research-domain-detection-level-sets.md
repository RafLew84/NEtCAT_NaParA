# Wykrywanie domen STM: tekstura, uporządkowanie i level sets

Data przeglądu: 2026-10-16. Zakres potwierdzony przez użytkownika: **orientacja
i uporządkowanie sieci molekuł oraz obszary pokrycia materiałem / wyspy**.
To rozpoznanie metod przed wyborem algorytmu, bez implementacji ani pomiaru
skuteczności na danych projektu. Zalecenia i proponowane eksperymenty poniżej są
wnioskami dla STM Domains, a nie wynikami opublikowanych badań.

## Wniosek dla projektu

**Level sets są sensownym kandydatem dla obrysów wysp i regularizacji granic.
Dla domen orientacji sieci zacząłbym od lokalnych cech tekstury lub geometrii
sąsiadów, a level set sprawdził jako kolejny etap.** Najpierw trzeba ustalić,
co w danych rozróżnia regiony; sam sposób przesuwania konturu tego nie definiuje.

Proponuję dwa powiązane wyniki:

| Warstwa | Pytanie | Wynik |
| --- | --- | --- |
| Pokrycie / wyspy | Gdzie znajduje się analizowana warstwa? | Maska pokrycia, identyfikatory wysp, powierzchnie i obrysy |
| Sieć wewnątrz pokrycia | Gdzie zmieniają się orientacja i uporządkowanie ułożenia molekuł? | Mapa orientacji, miara uporządkowania, domeny i obszary niepewne |

Jedna wyspa może zawierać kilka domen orientacyjnych; dwie osobne wyspy mogą
mieć tę samą orientację. To proponowany model opisu wyników. Orientacja sieci,
wyznaczana z rozmieszczenia środków molekuł lub periodyczności obrazu, nie jest
tożsama z kątem obrotu pojedynczej molekuły. Nie proponuję przyjmować obecnych
klas A/B/C z MolTrack jako definicji wszystkich domen.

## Co może oznaczać „level set Fedkiw”

**Level set** opisuje granicę jako poziomicę zerową funkcji `φ(x,y)` i pozwala
prowadzić jej ewolucję, także z łączeniem i rozdzielaniem obszarów. Klasyczna
praca Oshera–Sethiana z 1988 r. dostarcza tego aparatu numerycznego, nie
specyficznego kryterium rozpoznawania domen STM.
[Osher–Sethian, publikacja autorów](https://math.berkeley.edu/~sethian/Papers/sethian.osher.88.pdf).

Książka **Osher–Fedkiw, *Level Set Methods and Dynamic Implicit Surfaces***
(2003) obejmuje reprezentację powierzchni, ewolucję, obliczenia numeryczne
i zastosowania, w tym segmentację. Jest podstawą do zrozumienia narzędzia;
jej tytuł nie wskazuje jednej metody wykrywania domen.
[Wydawca i spis treści](https://link.springer.com/book/10.1007/b98879).

Istnieje też konkretna metoda **Gibou–Fedkiw, *A Fast Hybrid k-Means Level Set
Algorithm for Segmentation***: raport Stanford z listopada 2002 r., publikacja
konferencyjna w 2005 r. Autorzy wyprowadzają związek modelu Chan–Vese z k-means
i nieliniowym wygładzaniem, a następnie proponują szybszą hybrydę. Dopuszczają
również prędkość zależną od tekstury. **Wniosek dla projektu:** warto ją ocenić,
jeżeli model regionów już działa, a koszt obliczeń jest problemem; sama hybryda
nie definiuje, czym różnią się fizyczne domeny.
[Pełna praca autorów](https://physbam.stanford.edu/papers/stanford2002-08.pdf),
[datowanie w wykazie Fedkiwa](https://physbam.stanford.edu/).

Należy więc osobno wybrać **cechy obrazu**, **kryterium segmentacji** i **solver**.
Możemy porównywać różne solvery tego samego kryterium albo różne cechy przy
tym samym solverze — to odpowiada na inne pytania.

## Dlaczego sam kontur jasności może nie wystarczyć

W podstawowej wersji **Chan–Vese** dopasowuje dwie średnie wartości do wnętrza
i zewnętrza regionu, z karą za długość konturu; model nie wymaga silnej krawędzi
gradientowej. **Geodesic active contours** korzystają z geometrii obrazu
i informacji o jego krawędziach.
[Chan–Vese, 2001](https://doi.org/10.1109/83.902291),
[Caselles–Kimmel–Sapiro, 1997](https://link.springer.com/article/10.1023/A:1007979827043).

**Wniosek dla STM:** jeśli wyspa odróżnia się od podłoża średnim sygnałem,
model regionowy jest dobrym eksperymentem. Jeśli sąsiadujące domeny mają podobną
średnią jasność, ale inny kierunek rzędów, to średnia nie koduje poszukiwanej
różnicy. Z kolei wyraźne gradienty mogą obiegać każdą molekułę zamiast granicy
domeny. Wygładzenie ogranicza tę trudność, lecz może też usunąć informację
potrzebną do rozpoznania sieci. Należy sprawdzić to na konkretnych obrazach.

Model **wektorowy** może dopasowywać regiony w wielu kanałach cech, a model
**wielofazowy** rozdzielać więcej niż dwie klasy i reprezentować ich styki.
To dwa różne rozszerzenia; wielokanałowość nie oznacza automatycznie wielu
regionów. Dla projektu kanałami mogą być odpowiedzi filtrów kierunkowych,
a nie wyłącznie jasność.
[Chan–Sandberg–Vese, 2000](https://www.math.ucla.edu/~lvese/PAPERS/JVCIR2000.pdf),
[Vese–Chan, 2002](https://link.springer.com/article/10.1023/A:1020874308076).

## Najbliższe dowody z rzeczywistych obrazów STM

**Bui i współautorzy (2018)** proponują właśnie dwa tory analizy: rozkład obrazu
na część gładką i teksturę; pierwszą segmentują lokalnym wielofazowym Chan–Vese,
a drugą przez lokalne energie empirycznych filtrów curvelet i grupowanie.
Pokazują obrazy monowarstw cyjankowych na Au{111}. Opisują również błędy blisko
granic i problemy z teksturami występującymi w różnych skalach. To bezpośredni
precedens STM dla rozdzielenia informacji o pozornej wysokości i teksturze,
ale nie walidacja na naszych molekułach. Sam kontrast STM nie stanowi tu
automatycznego rozpoznania składu chemicznego.
[Pełna praca, szczególnie sekcje 3–5](https://arxiv.org/html/1804.08890v1).

**Jany–Janas–Krok (Micron, 2020)** wykorzystują przesuwane okno FFT,
PCA do oceny liczby składników i NMF do uzyskania map przestrzennych. Wśród
przykładów znajduje się STM rekonstrukcji Au/Ge(001). Autorzy pokazują,
że wielkość okna wpływa na wykrywane struktury: zbyt małe nie obejmuje
periodyczności, zbyt duże traci lokalność. To uzasadnia próbę lokalnych widm,
bez przenoszenia ich parametrów i wyników wprost do STM Domains.
[Publikacja autorów, wersja z 16.12.2019](https://arxiv.org/pdf/1907.10929).

## Metody do porównania

Poniższa kolejność jest rekomendacją eksperymentalną dla projektu.

| Podejście | Co dostarcza | Najważniejsza rzecz do sprawdzenia |
| --- | --- | --- |
| Lokalna FFT lub bank filtrów Gabor | Lokalna periodyczność, kierunki i skale tekstury | Rozmiar okna, artefakty skanowania, mieszanie dwóch domen przy granicy |
| Tensor struktury | Dominujący kierunek i koherencja lokalnych gradientów | Czy tekstura ma jeden dominujący kierunek; w symetrycznej sieci kilka kierunków może się równoważyć |
| Środki molekuł + graf sąsiadów | Kierunki wiązań sąsiedztwa, odległości i lokalny porządek | Brakujące/fałszywe detekcje, dobór sąsiedztwa, symetria sieci |

Tensor struktury i koherencja są dostępne np. w narzędziu autorów OrientationJ.
Koherencja opisuje kierunkowość gradientów; **nie należy traktować jej jako
uniwersalnej miary krystaliczności**. Dla projektu to szybka metoda porównawcza,
szczególnie przy obrazach rzędów lub pasm.
[OrientationJ: opis metody](https://bigwww.epfl.ch/demo/orientation/).

Dla grafu sąsiadów można liczyć
`ψₘ(i) = (1/Nᵢ) Σⱼ exp(i m θᵢⱼ)`: moduł opisuje lokalną zgodność kątów
z wybraną symetrią, a faza podzielona przez `m` — orientację modulo `360°/m`.
Przykładem jest `m=6` dla odpowiedniej sieci sześciokrotnej. Taką definicję
stosuje m.in. LAMMPS. **Rekomendacja:** dobrać `m` do struktury, nie zakładać
automatycznie sześciokrotności; sama wysoka wartość lokalna nie dowodzi
dalekozasięgowego porządku całej wyspy.
[Dokumentacja autorów LAMMPS](https://docs.lammps.org/stable/compute_hexorder_atom.html).

Jeśli detekcja molekuł jest zawodna, zacząłbym od tekstury. Jeśli środki są
wiarygodne, graf daje bardziej bezpośredni związek z geometrią ułożenia.
Nie ma potrzeby wymagać obu torów w pierwszej wersji.

## Proponowany przebieg analizy

1. Zachować surowy sygnał, skalę fizyczną i maskę poprawnych danych. Oddzielić
   przygotowanie pomiaru od ustawień gamma i zoomu podglądu.
2. Wyznaczyć maskę pokrycia: jako punkt odniesienia próg/proste regiony,
   następnie Chan–Vese na sygnale po uzgodnionym przygotowaniu. Przy słabym
   kontraście dopuścić cechy tekstury także w tej warstwie.
3. W obrębie pokrycia wyznaczyć cechy sieci: lokalne widmo/Gabor albo graf.
   Zwracać również pewność i stan „nierozstrzygnięte”. Nie utożsamiać braku
   poprawnych danych z fizycznym nieuporządkowaniem.
4. Grupować sąsiadujące miejsca o zgodnych cechach. Rozróżniać klasę
   orientacji od identyfikatora spójnej domeny.
5. Porównać wynik z wariantem wykorzystującym level set na tych samych cechach.
   Użycie kary za obwód ma uzasadnienie tylko wtedy, gdy poprawia zgodność
   granic z referencją, zachowując małe wyspy i wąskie obszary.

Kąty należy kodować okresowo, np. `(cos(mθ), sin(mθ))`, i porównywać zgodnie
z symetrią. To zapobiega sztucznemu skokowi na końcu zakresu kątów. Dla sieci
o symetrii 60° wartości 59° i 1° różnią się o 2°, nie o 58°.

## Co już jest w repozytorium

W [texture_domain_analysis.py](../../moltrack/analysis/texture_domain_analysis.py)
znajduje się eksperymentalny preset TTMAPP z trzema prototypami i lokalnymi
histogramami gradientów. Wbudowany opis mówi o kalibracji na klatkach 250–262
i walidacji czasowej na 263–268 **z jednej akwizycji**. Parametry obejmują
`render_scale=2`, promień 24 px renderowanych oraz `experimental=True`.
To źródło metody porównawczej, a nie dowód przenoszalności na nowe pomiary.

[local_multisymmetry_bond_order_computation.py](../../moltrack/analysis/local_multisymmetry_bond_order_computation.py)
oblicza kanały 3 i 6 na wspólnym grafie;
[rdzeń obliczeń](../../moltrack/analysis/_local_harmonic_bond_order.py)
uwzględnia liczbę sąsiadów i jakość geometrii. Można go ocenić jako bazę
eksperymentu. Istnienie kodu i testów nie zastępuje oceny skuteczności naukowej.

## Minimalny eksperyment przed decyzją

Poniższy protokół jest propozycją; liczby nie są deklarowaną dokładnością ani
wyliczonym wymaganiem statystycznym.

1. **Dane i identyfikacja.** Zebrać pilotażowo około 12–20 obrazów lub ROI
   z kilku niezależnych akwizycji: wyspy i puste podłoże, dwie orientacje,
   mała domena, defekty, słaby kontrast, artefakt skanu. Zapisać identyfikator
   pliku, hash, klatkę, ROI, kanał, nm/px i pochodzenie akwizycji.
2. **Referencja.** Narysować osobno maski pokrycia oraz granice domen sieci.
   W wybranych wnętrzach domen oznaczyć orientację i obszary niepewne.
   Druga osoba niezależnie ocenia przynajmniej część materiału; wyników algorytmu
   nie używać jako gotowej prawdy referencyjnej. Rozbieżności zachować.
3. **Podział.** Parametry dobierać na części rozwojowej, a ocenę końcową
   wykonać na odłożonych akwizycjach. Sąsiednie klatki tej samej serii oraz
   nakładające się ROI pozostają po tej samej stronie podziału. Jeśli dostępna
   jest jedna akwizycja, raportować wyłącznie sprawdzenie w jej obrębie.
4. **Przygotowanie i skala.** Zapisać poziomowanie, korekcję linii, filtrację,
   normalizację i maskowanie. Sprawdzić wariant z minimalnym przygotowaniem.
   Skale filtrów określać w nm i liczbie okresów sieci; pilotażowo porównać
   okna obejmujące np. 3, 5 i 8 okresów. Wyłączyć padding po rejestracji
   oraz okna, których poprawne pokrycie jest niewystarczające.
5. **Porównanie.** Dla pokrycia: prosty próg/regiony i Chan–Vese. Dla sieci:
   grupowanie lokalnych cech, graf jeśli są detekcje, Chan–Vese na jasności
   jako kontrola oraz model wektorowy na cechach. Ten ostatni porównać
   z grupowaniem dokładnie tych samych cech, aby oddzielić ich jakość
   od korzyści z regularizacji. Zapisać inicjalizację, parametry i czas.
6. **Miary.** Pokrycie ocenić przez IoU/Dice i błąd powierzchni; wyspy przez
   precision/recall obiektów i liczbę błędnych podziałów/połączeń. Domeny
   dopasować do referencji bez polegania na numerach etykiet. Granice ocenić
   przez F1 z ustaloną tolerancją fizyczną lub odległość w nm; orientację
   przez błąd kątowy modulo symetria. Osobno raportować udział pikseli
   nierozstrzygniętych, małe obiekty, wnętrza i pas przy granicy.
7. **Decyzja.** Przyjąć level set tylko wtedy, gdy poprawia istotne dla grupy
   wyniki względem prostszej metody przy akceptowalnym koszcie. Tolerancje
   i priorytet miar ustalić przed obejrzeniem wyników testowych. Stabilność
   w czasie sprawdzać dodatkowo, nie zamiast poprawności na pojedynczej klatce.

Nie wykonywano tego eksperymentu ani benchmarku. Literatura daje uzasadnione
kierunki prób, lecz wybór algorytmu nadal wymaga reprezentatywnych danych
i uzgodnienia, jakie granice grupa uznaje za istotne.
