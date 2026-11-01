# Protokół próby grafowej — 24

Data: **2026-11-01**. Bezpośrednie polecenie użytkownika „wykonaj 24”
wybiera to rozszerzenie po zakończeniu pierwszego pilota w 23.
25/26 i dodatkowe MPP/STP pozostają odłożone. To osobny eksperyment,
bez ponownego otwierania 19 lub zmiany zamrożonych wyników 20–23.

## Hipoteza i porównanie

Maskowane odtwarzanie geometrii lokalnych otoczeń może dać lepsze relacje
między centrami niż sam klasyczny opis tego samego otoczenia. Sprawdzamy
granice, błędne scalenia/podziały i odmowy; niska strata nie dowodzi domeny.
Wynik 15 uzasadnia kontrolowany punkt odniesienia, nie pełną wiarygodność
centrów: ma częściowe przypisania TTMAPP, lecz zawodzi przy fazie z jitterem
i niezależnych rzędach. Nie zakładamy, że uczenie usunie te błędy.

Główne porównanie: klasyczny opis geometryczny / encoder przed uczeniem /
encoder po uczeniu × FH k=4 / MWS. Wszystkie mają identyczne centra,
wsparcie, graf podziału, kryterium porządku i minimum ośmiu centrów.
Osobny punkt odniesienia stanowi zachowana procedura komórki z 15:
`cell-0.65-0.12-0.3-seed`, przeliczona na tym samym dostępnym wejściu.
Nie przypisujemy różnicy całej procedury 15 wyłącznie cechom.

## Dane, wsparcie i jawne adaptacje 20

Te same 24 klatki TTMAPP i zapisane oznaczenia, bez nowych pomiarów.
Referencje pozostają poza treningiem, doborem modelu, transformacją cech
i predykcją. Transfer zachowuje bloki klatek, pasy expanded i bufory 8 px
z [20](self-supervised-training-protocol.md). Transdukcja jest oddzielna.
Jedna skorelowana akwizycja i niepewna rejestracja nie dowodzą generalizacji.

Główną próbką jest teraz **centrum oznaczenia i otoczenie 72 × 72 reference_px**.
To jawna zmiana względem siatki 48 px w 21/22, dobrana do promienia R36
zachowanej bazy 15. Całe otoczenie musi mieścić się w pomiarze i swoim pasie.
Najpierw wycinamy centra, potem liczymy wszystkie cechy i warstwy grafowe
wyłącznie w tym otoczeniu. Eksportujemy embedding jego centrum. Węzły
przy brzegu mają kontekst ograniczony z definicji; nie korzystają z globalnego
cache sąsiadów. Liczby centrów i mianowniki zostaną zapisane przed treningiem.
Padding nie jest pomiarem; ponad 128 węzłów oznacza jawną niedostępność.
Przygotowanie wykazało 76 grafów train (66 w klatce 1 i 10 w klatce 50;
klatka 100 nie ma pełnego wsparcia), 27 validation (19/8 w klatkach 150/200),
831 testowych i 3795 dostępnych w całej serii. To mały zbiór zależnych
obserwacji, bez przesuwania podziału dla poprawy liczebności.
Nie ma rotacji, skalowania ani dodawania jitteru do danych treningowych.

W TTMAPP jednostką pozostaje px: kalibracja tego wejścia nie jest wiarygodna.
Kontrole resamplingu przeliczają współrzędne przez `pixel_spacing_xy` na
`reference_px`. Nie normalizujemy każdego otoczenia przez jego własny rozstaw.

Każdy węzeł otrzymuje 57 cech: miękki histogram względnych położeń
(4 promienie 6/12/18/24 px × 12 kierunków pełnego obrotu, szerokości
3 px i pi/12, sąsiedzi do 24 px, suma bez normalizacji), cztery najbliższe
odległości podzielone przez stałe 24 px, liczebność/10 i cztery flagi
dostępności odległości. Brak odległości zapisujemy jako zero z osobną flagą.
Graf ego ma binarne krawędzie do `min(24, 1.65 × mediana dodatniego NN)`
i pętle własne. Dokładne duplikaty zachowują krawędzie zerowej długości,
ale nie zerują estymaty rozstawu. Nie narzucamy sześciu sąsiadów lub symetrii.

## Model i zamknięty budżet

Mała własna implementacja inspirowana GraphMAE, bez DGL/PyG i pobierania wag.
Encoder: dwa bloki agregacji średniej, szerokość 64, GELU, wyjście z32,
bez BatchNorm. Maskujemy 50% całych wektorów węzłów tokenem, co najmniej
jeden i najwyżej N−1. Projekcja i ponowne wyzerowanie zamaskowanych
latentów poprzedzają jeden blok grafowy dekodera. Do dekodera nie trafia
dodatkowa kopia celu, surowe xy ani odległości krawędzi.

Główny cel: `SCE(alpha=2) + MSE` czterech dostępnych kanałów odległości,
waga MSE=1; wariant diagnostyczny: samo SCE. Strata dotyczy zamaskowanych
rzeczywistych węzłów. SCE normalizuje wektory i nie mierzy ich normy;
MSE zachowuje jawny cel skali. Zerowe cele geometryczne nie wchodzą do
SCE; ich liczba jest raportowana. Całkowicie nieinformacyjny batch pomija
optymalizację, zużywając próbę kroku bez zastępczego losowania lub fitu.
Nie nazywamy tego reprodukcją publikacji.
[GraphMAE](https://arxiv.org/abs/2205.10803),
[model autorów](https://github.com/THUDM/GraphMAE/blob/main/graphmae/models/edcoder.py),
[strata](https://github.com/THUDM/GraphMAE/blob/main/graphmae/models/loss_func.py).

Najwyżej **9 fitów**: 2 cele × 3 ziarna transferu, następnie 3 refity
transdukcyjne tylko głównego celu. Ziarna 20261101–20261103; wspólne
inicjalizacje, losowania i maski dla porównania celów. Zachowujemy własne
wagi początkowe jako kontrolę bez uczenia. Trening losuje równo klatki,
następnie dostępne centra; batch 64, AdamW lr=0.001, wd=0.0001, clip 1,
float32, bez AMP. Transfer: najwyżej 2000 kroków, checkpoint co 100,
wybór najmniejszej straty na stałych maskach walidacyjnych bez etykiet.
Transdukcja: mediana wybranych kroków trzech głównych fitów transferowych.

Limity: 900 s/run, 8100 s łącznie, 8 GiB tensorów GPU, 12 GiB RSS,
10 GiB checkpointów, 7200 s CPU pozostałych etapów. Techniczny preflight
nie wybiera architektury; audyt wznowienia może wykonać najwyżej 12 kroków
poza fitami jakościowymi, bez wykorzystania jego wag. Nie ma zastępczych
ziaren, restartów optymalizacji, strojenia na domenach ani zwiększania budżetu.
RTX 5090 jest docelowym urządzeniem; większy sprzęt nie należy do próby.

## Relacje, porządek i katalog

Transformację cech dopasowujemy tylko na dozwolonym train: standaryzacja
kanałów i PCA do `min(24,D,n−1)`, bez wybielania i bez L2 każdego wektora.
To jawna adaptacja 20 chroniąca informację o normie i skali. Mediana dodatnich
odległości krawędzi i kwantyle q25/q75 również pochodzą wyłącznie z train.
FH/MWS zachowują algorytmy 20. Graf podziału korzysta z tych samych lokalnych
krawędzi centrów dla wszystkich reprezentacji; transferowe metryki mają
osobny graf wyłącznie miejsc testowych, bez połączeń przez resztę klatki.

Wspólna bramka to **geometryczna powtarzalność z 15**: R36, tolerancja
0.24 rozstawu, poprawiony tryb bez gwarantowanego trafienia centrum,
score >0.25. Spójność liczymy po odmowach; minimum 8. Nie zmieniamy tej
bramki po wynikach. Procedura komórki 15 dodatkowo zachowuje fraction 0.65,
odległość baz 0.12, fazę 0.3 i zgodność z początkiem rozrostu.
Zmiana wobec obrazowego ACF w 21/22 jest jawna: wyniki 24 nie są rankingiem
tamtych encoderów i nie dziedziczą ich mianownika ani limitu 0/174.

Wspólny dla zakresu katalog podobieństwa można dopasować tylko na train
przez HDBSCAN (minimum 8, min_samples 4, dopuszczona jedna grupa), bez zadanej
liczby klas. Przypisanie nowych deskryptorów ma jawny warunek odmowy.
Klastry pozostają grupami opisów, bez automatycznego fizycznego typu,
orientacji lub materiału. Domena, typ i powierzchnia pozostają osobne.

## Kontrole, zamrożenie i ocena

Nowe ziarna kontroli **920021–920023**: 27 rodzin 20 oraz cztery celowane
zmiany samych oznaczeń: jitter 0.36 px, jitter 0.72 px, 10% duplikatów oraz
granica przesunięcia z jitterem 0.72 px. Obraz i prawda pozostają zachowane;
duplikaty mają osobne ID. To świeże realizacje znanych rodzin, nie nowe STM.
Kontrole nie trenują, nie wybierają checkpointów i nie kalibrują progów.
Kod, model i plan przypinamy przed fitami; kompletne predykcje przed oceną.

Przed/po odmowach raportujemy błędy wszystkich par i rzeczywistych krawędzi,
zakres przypisań, zero/jedną/wiele domen, ziarna i dostępność mianowników.
Dla nieregularnego grafu centrów granice używają midpointów **wszystkich**
lokalnych krawędzi między różnymi przypisaniami; tolerancja 8 reference_px.
Nie stosujemy osiowego filtra siatki z 20 ani dokładnego F1 do ramek TTMAPP.
Pary przerwa materiału/brak oznaczeń mogą mieć identyczną geometrię:
wynik geometryczny nie rozstrzyga wtedy materiału.

Liczbowe kryteria 20 zachowujemy tam, gdzie są ocenialne: pełna sieć
coverage≥0.90/split≤0.02; dwie części coverage≥0.50, każda≥0.30,
merge≤0.02/split≤0.10 i F1≥0.70 na styku; ujemne rzędy/losowe centra
bez domen; TTMAPP coverage≥0.20 i ≥0.10 na reprezentowanych kolorach.
Puste wejście centrów nie zalicza rozpoznania obrazu szumu/pasów:
zero domen jest zachowaniem technicznym, a miary geometrii są niedostępne.
Braki centrów oceniamy na zachowanych ID i pełnym mianowniku, nie wymogiem
niezmienności całej siatki. Dla braków centrów, jitteru pełnej sieci i duplikatów
wymagamy jednej domeny, coverage≥0.50 i split≤0.10. Granica fazowa z jitterem
ma warunki dwóch części i F1≥0.70; każde zaburzenie raportujemy osobno.

Przewaga wymaga mediany poprawy średniego błędu o ≥5 pp przy wspólnym
coverage≥0.20, bez pogorszenia składnika >2 pp i bez przeciwnego znaku
w pozostałych ziarnach; alternatywnie wzrost coverage≥10 pp przy zachowanych
błędach. Sprawdzamy to względem klasycznego opisu i własnej inicjalizacji,
osobno na kontrolach i TTMAPP. Stabilność: spread coverage≤10 pp,
zmienione relacje≤0.10 przy jawnym wspólnym zakresie. Pusta odpowiedź
nie zalicza kryteriów. Oddzielamy częściowy zysk przed bramką od końcowych
domen. Negatywny wynik kończy zaplanowaną próbę; bez automatycznego 25/26.
