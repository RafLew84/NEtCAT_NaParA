# Grupowanie zamrożonych cech — audyt do issue 19

Data: 2026-10-26. Zakres: zasady grupowania bez zadanej liczby klas, semantyka
lokalnego API oraz interpretacja wyniku FCN/DINO. Ten dokument nie zawiera
wyników wykrywania domen TTMAPP ani wyboru końcowej metody. Ustalenia
źródłowe oddzielono od proponowanego protokołu eksperymentu.

## Co rzeczywiście zapewnia HDBSCAN

`sklearn.cluster.HDBSCAN` wyznacza grupy gęstościowe bez argumentu `K`.
Domyślne `allow_single_cluster=False` wyklucza wynik z jedną grupą;
próba obejmująca jedną domenę wymaga jawnego `True`. `min_cluster_size`
i `min_samples` mają różne role, a przy `min_samples=None` drugi parametr
przejmuje pierwszy. W sklearn liczba sąsiadów zawiera badany punkt; względem
`scikit-learn-contrib/hdbscan` odpowiada jej wartość większa o jeden.
[Dokumentacja HDBSCAN 1.6.1](https://scikit-learn.org/1.6/modules/generated/sklearn.cluster.HDBSCAN.html)

`cluster_selection_epsilon` jest odległością w przestrzeni przekazanej do
HDBSCAN, a nie liczbą pikseli, kątem czy prawdopodobieństwem. Zwiększenie go
scala pobliskie mikrogrupy. Wybór progu zależy więc od metryki i skalowania
wektorów. EOM wybiera trwałe grupy hierarchii; wariant `leaf` zwykle daje
bardziej szczegółowy podział. Dokumentacja nie utożsamia trwałości grupy
z fizycznym uporządkowaniem materiału.
[Dokumentacja autorów: parametry](https://hdbscan.readthedocs.io/en/latest/parameter_selection.html)

Wniosek dla próby: wartości epsilon 0.1/0.25 z issue 17 nie mają automatycznie
tego samego znaczenia dla FCN, DINO oraz cech widmowych. Trzeba zapisać
transformację wektorów i jednostkę progu. Bezpośrednie użycie dawnych wartości
jest dopuszczalnym jawnym wariantem, ale nie dowodzi równoważnego traktowania
rodzin cech.

## Sprawdzenie lokalnej implementacji

W środowisku `netcat` importowano **sklearn 1.6.1**. Zbadano
`sklearn/cluster/_hdbscan/hdbscan.py`, sygnaturę i źródło `HDBSCAN.fit`:

- istnieje `fit_predict`, brak `predict` oraz `approximate_predict`;
- domyślna droga dla cech euklidesowych korzysta z sąsiadów i niejawnego
  drzewa wzajemnej osiągalności; nie trzeba samemu budować macierzy N × N;
- wejście jest walidowane jako float64;
- pojedynczy punkt powoduje wyjątek; `min_samples` nie może przewyższać
  liczby próbek. Puste i bardzo małe zbiory wymagają jawnej obsługi;
- parametr `random_state` nie należy do HDBSCAN. Brak losowania w API nie
  zastępuje sprawdzenia wpływu kolejności, remisów i wersji bibliotek.

Źródłem powyższych stwierdzeń jest inspekcja zainstalowanego kodu; wersjonowany
odpowiednik: [sklearn 1.6.1 — implementacja HDBSCAN](https://github.com/scikit-learn/scikit-learn/blob/1.6.1/sklearn/cluster/_hdbscan/hdbscan.py).
Ścieżka środowiska:
`/home/rlew/projekty/conda-migration-ubuntu-20261008/envs/netcat/`.

Mała kontrola semantyki API, wykonana lokalnie z
`min_cluster_size=12, min_samples=6, n_jobs=1`:

| Wejście | `allow_single_cluster=False` | `True` |
| --- | --- | --- |
| 100 identycznych wektorów 4D | 100 odrzuconych | jedna grupa: 100 |
| 1000 wektorów losowych jednostajnie w [0,1), 16D, `default_rng(19)` | 1000 odrzuconych | jedna grupa: 15; 985 odrzuconych |
| dwa obłoki 4D, N(-2,0.2) i N(2,0.2), po 100, RNG 19/20 | dwie grupy po 100 | dwie grupy po 100 |

To kontrprzykład interpretacyjny, nie test skuteczności na obrazach: dopuszczenie
jednej grupy jest potrzebne, ale samo jej znalezienie nie dowodzi istnienia
domeny. Jednolite wektory mogą pochodzić również z pustego lub stałego obrazu.
Nie należy z takiego przypadku automatycznie robić uporządkowanej domeny.

## Normalizacja i PCA zmieniają pytanie o podobieństwo

PCA sklearn centruje kanały, ale nie dzieli ich przez odchylenie standardowe.
`whiten=True` usuwa względne skale wariancji składowych. Solver `auto` zależy
od rozmiaru danych; przy `randomized` do odtwarzalności służy `random_state`.
Jawny `svd_solver='full', whiten=False` jest prostym punktem odniesienia;
trzeba zapisać liczbę składowych i zachowaną wariancję. Redukcja do np. 16
składowych jest ograniczeniem wymiaru, nie ustaleniem 16 klas.
[Dokumentacja PCA 1.6.1](https://scikit-learn.org/1.6/modules/generated/sklearn.decomposition.PCA.html)

`Normalizer(norm='l2')` normalizuje każdy wektor oddzielnie. Dla niezerowych
wektorów jednostkowych zachodzi matematyczna tożsamość
`||u-v||² = 2(1-cos(u,v))`; odległość euklidesowa odpowiada więc różnicy kierunku
wektorów. To nie gwarantuje niezmienniczości na jasność ani obrót obrazu.
[Dokumentacja Normalizer 1.6.1](https://scikit-learn.org/1.6/modules/generated/sklearn.preprocessing.Normalizer.html)

`StandardScaler` dopasowuje średnią i skalę osobno dla kanałów na zbiorze
uczącym transformację; jest wrażliwy na odstające wartości. Jego zastosowanie
nadaje mało zmiennym kanałom inny wpływ niż PCA na surowych wektorach. Dla
zamrożonych cech dopasowanie skalera lub PCA do nieoznaczonych danych nie
jest treningiem wag sieci, lecz nadal jest zależnością wyniku od tych danych.
[Dokumentacja StandardScaler 1.6.1](https://scikit-learn.org/1.6/modules/generated/sklearn.preprocessing.StandardScaler.html)

**Propozycja protokołu:** wybrać z góry małą liczbę pełnych, nazwanych
transformacji, np. L2 → PCA bez whitening oraz standaryzacja kanałów → PCA bez
whitening. Każde dodatkowe L2 po PCA jest osobną operacją i musi być zapisane.
Nie dobierać transformacji po obejrzeniu kolorowych referencji. Jeśli progi
odległości są względne, np. wielokrotność mediany odległości do k-tego sąsiada,
zapisać k, dokładną próbkę oraz obliczoną wartość; wykluczyć zerową skalę.
Taki próg jest własną heurystyką do porównania, nie zalecanym domyślnym
parametrem HDBSCAN.

## Jeden katalog dla deklarowanego zakresu

Skaler, PCA i HDBSCAN powinny otrzymać wspólny zbiór nieoznaczonych wektorów
z zadeklarowanego zakresu klatek. To wniosek z ich operacji `fit`: niezależne
fit dla każdej klatki zmieniają przestrzeń i przypisania, mimo identycznych
numerów etykiet. Samo sortowanie numerów klas nie łączy takich katalogów.
[API PCA](https://scikit-learn.org/1.6/modules/generated/sklearn.decomposition.PCA.html),
[API HDBSCAN](https://scikit-learn.org/1.6/modules/generated/sklearn.cluster.HDBSCAN.html)

Własne zalecenia do jawnego protokołu:

1. Wypisać identyfikatory klatek, tryb grid/centers, maskę podparcia i regułę
   próbkowania przed grupowaniem. Zachować pełne obrazy przy pobieraniu cech.
2. Zadeklarować, czy większa klatka lub klatka z większą liczbą centrów ma
   większą wagę poprzez większą liczbę wektorów. Regularne, silnie zachodzące
   okna są skorelowane; liczne próbki nie są licznymi niezależnymi dowodami.
3. Można ograniczyć próbkę służącą dopasowaniu skalera/PCA i transformować
   wszystkie wektory. Jednak HDBSCAN na podzbiorze plus przypisanie reszty
   do najbliższej grupy wymaga osobnej opisanej reguły odmowy; nie jest
   tym samym co wspólny `fit_predict` na wszystkich wektorach.
4. Kontrole syntetyczne mogą mieć odrębne katalogi dla niezależnych scen;
   klatki TTMAPP powinny mieć jeden katalog na dany wariant i zakres.
5. Porównanie szerszego/węższego zakresu wymaga ponownego fit i oceny zmian
   na wspólnych punktach. Stabilny numer w obrębie jednego zapisu nie oznacza
   tożsamości typu po zmianie zakresu.

## Czego cechy FCN i DINO nie rozstrzygają

DINOv2 dostarcza reprezentacje przenoszone między zadaniami. W artykule
pokazano PCA tokenów i dopasowanie fragmentów; część wyników segmentacji
pochodzi z dodatkowych trenowanych głowic. Kolory PCA są wizualizacją
kierunków zmienności, nie katalogiem fizycznych typów sieci. Artykuł nie
wykazuje rozdzielenia orientacji, rozstawu i porządku w obrazach STM.
[Artykuł DINOv2, sekcje 7.4–7.5](https://arxiv.org/html/2304.07193v2)

Lokalny ekstraktor issue 18 uśrednia mapy FCN lub tokeny DINO w oknie.
Powstaje jeden wektor opisujący otoczenie, o wsparciu szerszym niż punkt
na rysunku. To adaptacja, a nie gotowy segmentator domen. Dokładne warstwy,
wagi, pooling, rozdzielczość i zasięg kontekstu opisano w
[audycie ekstrakcji](research-frozen-feature-extraction-audit.md) i
[raporcie przygotowania](frozen-feature-preparation.md).

Własny wniosek: klastry tych wektorów należy nazywać **grupami wyglądu**,
aż kontrole pokażą, które różnice reprezentują. Potrzebne są osobne wyniki:

- etykieta podobieństwa cech i odmowa grupowania;
- niezależny dowód lokalnego uporządkowania lub brak takiego dowodu;
- orientacja/rozstaw z jawnie wskazanego pomiaru, jeśli są dostępne;
- spójne przestrzennie fragmenty po zastosowaniu ustalonej reguły łączenia.

Zewnętrzna bramka ACF może ograniczać każdy ekstraktor w identyczny sposób.
Raport powinien podać wyniki przed bramką, odsetek przejścia bramki i końcowe
przypisania. Wariant bez bramki jest diagnostyką grupowania; jego barwne płaty
nie stanowią automatycznie domen. Jeśli bramka zostanie zmieniona, trzeba
powtórzyć także klasyczny punkt odniesienia i jawnie przypisać zmianę temu
etapowi. Obrót tej samej sieci może zmienić grupę wyglądu bez zmiany typu
sieci; połączenie tych grup w typ wymaga dodatkowej, sprawdzonej reguły.

## Mały, uczciwy budżet porównania

Propozycja do zatwierdzenia w maszynowym protokole przed oceną referencji:

1. Najpierw zdefiniować skończoną listę wariantów modelu, okna, rozdzielczości,
   normalizacji i grupowania. Koszt ekstrakcji nie musi się powtarzać dla
   różnych parametrów HDBSCAN. Z góry ograniczyć liczbę wariantów grupowania
   na ekstraktor; nie rozszerzać jej dlatego, że referencja wygląda źle.
2. Na kontrolach rozwojowych wymagać jednocześnie: małej liczby fałszywych
   przypisań dla zera domen, zachowania jednej sieci bez nadmiernego podziału,
   rozdzielenia wyraźnego obrotu/rozstawu oraz jawnych odmów. Sam wysoki
   udział przypisań i sam brak błędów przy odrzuceniu wszystkiego nie
   spełniają celu. Zachować osobne kontrole kwalifikacyjne.
3. Zamrozić konfigurację i hash przed oceną częściowych referencji TTMAPP.
   Przedstawić nieoznaczone obszary bez przypisanej im globalnej trafności.
4. Sprawdzić powtórzenie z tą samą kolejnością, odwróconą kolejność i usunięcie
   plików referencji. Przy porównaniu kolejności odwrócić permutację punktów.
   Numerację klas kanonizować po stałych identyfikatorach elementów, a nie
   traktować surowej numeracji HDBSCAN jako fizycznej tożsamości.
5. Oprócz zgodności etykiet raportować odmowy, liczbę grup i komponentów
   przestrzennych. ARI jest niezmienniczy na permutację etykiet, ale wynik 1
   przy dwóch zestawach zawierających wyłącznie odmowy nie oznacza poprawnej
   detekcji. Warto osobno podać zgodność decyzji przyjęcia i ARI dla wspólnie
   przyjętych elementów wraz z ich liczbą.
   [Dokumentacja ARI](https://scikit-learn.org/1.6/modules/generated/sklearn.metrics.adjusted_rand_score.html)

Powyższy budżet jest propozycją audytu, a nie twierdzeniem, że konkretna
liczba składowych, epsilon lub HDBSCAN zapewnia wykrycie domen. Dobry wynik
próby oznacza przewagę wykazaną na zadanych kontrolach i dostępnym zakresie;
wynik negatywny nadal rozstrzyga użyteczność tej konfiguracji bez odrzucania
całej rodziny zamrożonych reprezentacji.
