# SD-V4-26 — protokół przed pomiarami

2026-11-09. Baza kodu `04d28d5`. Protokół zapisany przed implementacją
i uruchomieniem porównania. Środowisko `netcat`: NumPy 2.2.5, SciPy 1.15.2,
scikit-image 0.25.2. Bez nowych zależności, treningu i ręcznych korekt wejścia.

## Pytanie i projekt porównania

Czy alternatywny podział na tych samych pomiarach ogranicza rozdrobnienie,
bez scalenia różnych sieci, zamknięcia luk i usunięcia małych domen?
Porównujemy kompletne przebiegi analizy, nie sam solver. Każda klatka jest
blokiem: identyczny obraz, centra i jeden obiekt pomiarów z 16 dla obu metod.
TTMAPP259–266 to zależne obrazy jednej, wcześniej oglądanej akwizycji;
wyniki opisowe, bez testów istotności, accuracy i deklaracji generalizacji.

Kontrole z generatora 17: regularna sieć, dwie orientacje, płynne zgięcie,
skok fazy, brakujące centra, luka, losowe centra, rzędy 1D, zbyt mało centrów.
Dodać małą wyspę obróconej sieci oraz artefakt liniowy na regularnej sieci.
Referencja punktowa pochodzi z konstrukcji generatora, nie z algorytmu.
Skok fazy ma dwie domeny; zero wyników jest pominięciem, a nie sukcesem.
Nie liczymy błędu konturu: nie posiadamy zwalidowanych masek granic.
Źródło TTMAPP, SHA256 wejść, liczby punktów i wersje parametrów zapisuje raport.

Z góry ustalone ustawienia: geometria 12°, 16%, koherencja ≥0,75,
lokalnie ≥10 i Neff ≥8; minimum domeny 8; promień wsparcia 0,85 NN.
Geometria ma dodatkowo krawędzie ≤1,5 NN. Level set: siła 0 / 0,25 / 1,
limit 120 iteracji. Każdą konfigurację liczymy z barierami domyślnymi oraz
wyłączonymi, razem osiem wariantów na wejście. Bez dostrajania po klatkach.
Kolejność wariantów losowana wewnątrz klatki, seed 20261109. Jedno wykonanie;
czas segmentacji oddzielony od wspólnego pomiaru, nie jest benchmarkiem.

Raport: domeny, przypisania/aktywne centra, przyczyny odmów, błędne scalenia,
rozdzielone regiony referencyjne, całkiem pominięte regiony, fałszywe domeny
w kontrolach bez sieci 2D oraz czas. Pokrycie podajemy osobno od błędów.

## Jedna adaptacja: `gibou_fedkiw_features_v1`

Inspiracją jest §3 [Gibou–Fedkiw, A Fast Hybrid k-Means Level Set Algorithm
For Segmentation](https://physbam.stanford.edu/papers/stanford2002-08.pdf):
ewolucja funkcji poziomicowej siłą danych, okresowa rekonstrukcja odległości
i osobna regularyzacja krzywizną. Poniższy wieloregionowy wariant i jego
stałe są naszą adaptacją; nie odtworzeniem wyników ani wydajności publikacji.

1. Pomiary i odmowy jak w 17: dwie stabilne rodziny kierunek–rozstaw,
   te same bariery obrazu, kalibracja X/Y. Każda rodzina ma
   `(cos(2θ), sin(2θ), log(p))`. Koszt jest średnią kwadratów rozbieżności
   dwóch rodzin; norma cięciwy kąta dzielona przez `2 sin(12°)`, log-rozstaw
   przez `log(1+0,16)`. Minimum z dwóch wspólnych permutacji rodzin
   zachowuje parę kierunek–rozstaw. W aktualizacji prototypów dopasowujemy
   permutację, uśredniamy i normalizujemy wektory kierunkowe.
2. Początkowe prototypy: deterministyczny przegląd pomiarów `(y,x,ID)`;
   dodaj nowy, gdy odległość geometryczna z 17 od wszystkich dotychczasowych
   przekracza 1. Przydział do najbliższego prototypu. Maksimum 32 prototypy;
   przekroczenie daje jawny błąd zasobów, nie obcięcie danych. To regiony
   modelu, nie klasy fizyczne ani końcowe domeny.
3. Mapy pikselowe: najbliższe aktywne centrum w metryce skalibrowanej,
   w promieniu 0,85 NN. Niepoprawny pomiar, niefinitywny obraz oraz bariera
   dają twardą maskę nieważności. Braki pozostają brakami; bez interpolacji
   przez lukę. Limit piksele × regiony modelu: 4 miliony.
4. Dla regionu r funkcja φ dodatnia wewnątrz, odległość do innego ważnego
   regionu minus odległość do własnego. Rekonstrukcja przez dokładny EDT
   SciPy zamiast Fast Marching. Odległości w jednostkach mediany NN,
   siatka `(dy/NN, dx/NN)`. Siła danych: koszt najlepszego konkurenta minus
   koszt własny, ograniczona do [-1,1]; krok 0,2. Rozstrzygnięcie argmax φ,
   remis najmniejszym ID. Prototypy aktualizowane w każdym kroku.
5. Co 5 kroków rekonstrukcja i przepływ krzywizny
   `div(grad φ / sqrt(|grad φ|² + 1e-8))`. Łączny czas wygładzania
   `0,05 × siła`; podkroki ≤`0,2/(1/hx²+1/hy²)`.
   Warunek Neumanna: brakujący sąsiad zastępowany bieżącą wartością,
   także na granicy maski. Maska nieważności nigdy nie staje się regionem.
6. Stop: niezmieniony podział przez dwa pełne bloki po 5 kroków, jeden
   pozostały region lub limit iteracji. Zapisujemy powód i rzeczywistą
   liczbę kroków; stabilny podział nie jest dowodem zbieżności PDE.
7. Końcowe domeny to osobne składowe 8-spójne. Centrum przypisujemy według
   piksela zaokrąglonego w oryginalnych współrzędnych. Usuwamy składowe
   bez centrów lub mniejsze niż minimum; ID sortowane po centroidach.
   Maska i przypisania opisują ten sam końcowy podział, bez późniejszego
   odmalowania Voronoi. Typ nieznany, brak katalogu klas. Render raw/aligned
   korzysta z istniejących transformacji, bez ponownego liczenia solvera.

UI udostępnia siłę 0–2 i limit 1–500; domyślnie 0,25 / 120.
Parametr łączenia krawędzi grafu jest nieaktywny w Level set.
Zmiana pól jest szkicem; obliczenie tworzy osobny wynik. Zapis/eksport
zachowują parametry, maskę i przypisania. Brak sygnału fazy w cechach
pozostaje jawnym ograniczeniem niezależnie od wygładzania.

## Uzupełnienia wykonawcze

Wyłączenie barier realizuje istniejący parametr minimalnej długości = 100 NN
(zasięg przekracza szerokość tych obrazów). Skrypt sprawdza, że maska jest
pusta; ustawienie stosowane identycznie do obu metod. Nie zmienia obrazów.

Przygotowanie protokołu wspierała procedura `experimental-design`. Źródło
oprogramowania: Timothy Kassis, Vinayak Agarwal, Yuhuan He, Darshil Patel,
Aubrey M. Brueckner (2026), *Scientific Agent Skills: A Library of Procedural
Knowledge for Research Agents*, [arXiv:2609.00065](https://arxiv.org/abs/2609.00065).
Sprawdzono aktualny rekord 2026-11-09 (rewizja z 2026-09-02); ta publikacja
nie jest dowodem skuteczności algorytmu domen.
