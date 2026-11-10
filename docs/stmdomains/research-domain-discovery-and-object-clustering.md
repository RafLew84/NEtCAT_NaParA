# Wyszukiwanie domen i grupowanie zaznaczonych obiektów

Data przeglądu: **2026-10-21**. Baza dokumentacji projektu: `035bc11`.
Status: **badanie źródeł, propozycja trzech porównań; bez wykonania nowych prób**.
Uzupełnienie [wcześniejszego przeglądu](research-general-domain-detection.md)
i [audytu MolTrack](moltrack-method-audit.md).

## Wniosek dla STM Domains

Istnieją metody, które pozwalają szukać struktur bez katalogu A/B/C i bez
obowiązkowej symetrii M3/M6. Najbardziej użyteczny kierunek to **opis lokalnego
otoczenia → podobieństwo struktur → podział na przestrzennie spójne domeny**.
Opis może pochodzić z zaznaczonych obiektów, obrazu albo obu źródeł. To nasza
synteza opisanych niżej badań, nie gotowa i zwalidowana metoda STM Domains.

Nie należy utożsamiać trzech różnych wyników:

| Wynik | Przykład | Czego jeszcze nie dowodzi |
| --- | --- | --- |
| Skupisko położonych blisko obiektów | Zwarta grupa molekuł | Że ma jeden typ sieci lub orientację |
| Grupa podobnych obiektów lub otoczeń | Molekuły o podobnym kształcie albo podobnym układzie sąsiadów | Że wszystkie należą do jednej przestrzennej domeny |
| Domena | Spójny obszar uporządkowania z granicą i informacją o jakości | Że znamy powierzchnię całego płata materiału |

Zgodnie z ustaleniami projektu obrócona sieć może zachować typ, a należeć do
innej domeny. Istotnie inny rozstaw może zmieniać typ. Również granica
niedopasowania przy tym samym typie i kącie może dzielić domeny. Dlatego sama
jedna etykieta klastra nie opisuje całego wyniku.
[Definicje projektu](issues/02-order-types-and-domains.md),
[próba granic](phase-boundaries-trial.md).

## Sześć rodzin metod

### 1. DBSCAN / HDBSCAN / OPTICS: skupiska i grupowanie cech

**Wejście:** współrzędne obiektów albo wektory opisujących je cech.
**Wyjście:** etykieta grupy dla obiektu oraz obiekty nieprzypisane.
HDBSCAN analizuje gęstość na wielu skalach i nie wymaga zadania liczby grup;
pozostają parametry minimalnej liczebności i metryki. Domyślnie nie dopuszcza
wyniku z jednym klastrem, co trzeba świadomie zmienić w naszej próbie jednej
jednorodnej sieci. Jego siła przynależności jest właściwością grupowania,
nie skalibrowanym prawdopodobieństwem poprawnej domeny.
[Dokumentacja HDBSCAN](https://scikit-learn.org/stable/modules/generated/sklearn.cluster.HDBSCAN.html).

OPTICS zachowuje informację o strukturze skupisk przy zmiennym promieniu;
pozwala później wybrać sposób wydzielenia grup. Implementacja scikit-learn
ma czasową złożoność `O(n²)`, więc nie należy bez pomiaru stosować jej do każdego
piksela dużego filmu.
[Dokumentacja OPTICS](https://scikit-learn.org/stable/modules/generated/sklearn.cluster.OPTICS.html).

**Wniosek dla nas:** na samych XY to dobry prosty punkt odniesienia dla skupisk,
ale dwie stykające się sieci o podobnej gęstości mogą być nierozróżnialne.
Po podaniu cech struktury HDBSCAN staje się kandydatem do odkrywania typów;
oddzielny etap przestrzenny nadal musi wyznaczyć domeny. Luki w detekcjach
zmieniają gęstość, więc nieprzypisanie nie może automatycznie znaczyć
„nieuporządkowanie” ani „odsłonięte podłoże”. Koszt wejścia jest niski:
gotowe implementacje CPU w scikit-learn.

### 2. Deskryptory lokalnego otoczenia: podobieństwo bez gotowych wzorców

**Wejście:** centra, ewentualnie cechy obiektów oraz ich otoczenia.
**Wyjście:** opis i podobieństwo otoczeń; po grupowaniu — kandydaci na typy.
SOAP opisuje sąsiedztwo przez wygładzoną gęstość punktów i pozwala porównywać
otoczenia bez listy dopuszczalnych sieci. Oryginalna praca dotyczy atomów
i modeli energii, nie detekcji domen STM. Niezmienniczość obrotu jest przydatna
do typu, ale usuwa informację o orientacji; niezmienniczość odbicia ogranicza
też rozróżnianie chiralności.
[Bartók, Kondor i Csányi](https://arxiv.org/abs/1209.3140).

Gotowy SOAP w DScribe ma parametry promienia, rozmycia oraz liczby składowych
radialnych i kątowych. Skala odległości pozostaje w reprezentacji; normalizacja
długości samego wektora cech nie jest tym samym co przeskalowanie współrzędnych.
Wariant dla punktów 2D umieszczonych w płaszczyźnie 3D jest **naszą propozycją
adaptacji**, wymagającą sprawdzenia. Wszystkie centra jednej klasy mogą dostać
wspólny znacznik gatunku; nie oznacza to chemicznego modelowania molekuły.
[API i definicja SOAP w DScribe](https://singroup.github.io/dscribe/latest/tutorials/descriptors/soap.html).

Alternatywą są prostsze cechy odległości, kątów i kilku otoczek sąsiadów.
Boattini i współautorzy pokazali odkrywanie lokalnych środowisk przez wektor
parametrów porządku, autoenkoder i mieszaniny Gaussa na symulacjach koloidów,
także przy granicach. Nowsza praca Ulugöl i współautorów porównuje PCA,
autoenkoder i UMAP przy **ustalonych deskryptorach i sposobie grupowania**;
obejmuje symulacje oraz jeden eksperymentalny układ koloidów. Nie jest dowodem,
że UMAP lub te deskryptory są najlepsze dla STM.
[Boattini i in.](https://arxiv.org/abs/1907.02420),
[Ulugöl i in., metody i zakres porównania](https://arxiv.org/html/2509.07186v2).

**Wniosek dla nas:** porównać łatwe do interpretacji cechy z SOAP; zachować
osobno kąt i rozstaw w jednostkach obrazu lub fizycznych. Nie normalizować
każdego otoczenia do identycznego rozmiaru. UMAP traktować opcjonalnie:
jego dokumentacja ostrzega o niezachowaniu gęstości i możliwych sztucznych
rozcięciach klastrów. Ładny wykres 2D nie jest kryterium wykrycia domen.
[Ograniczenia UMAP przy grupowaniu](https://umap-learn.readthedocs.io/en/latest/clustering.html).

To podejście wymaga dostatecznych oznaczeń. Należy badać osobno brakujące
centra, fałszywe detekcje i obiekty przy brzegu. Biblioteka deskryptorów nie
rozwiązuje tego automatycznie. Przewidywany koszt wdrożenia jest średni:
ekstrakcja sąsiedztwa i cech, grupowanie oraz późniejszy podział przestrzenny.

### 3. SBC / MatID: odkrywanie powtarzalnej komórki z punktów

**Wejście:** współrzędne i znaczniki gatunku; **wyjście:** grupy punktów oraz
odtworzone komórki. SBC wyszukuje lokalną translacyjną powtarzalność bez
treningu i katalogu szablonów. Autorzy pokazują warstwy 2D, granice ziaren
i kontrolowane zaburzenia. Przykłady określane w publikacji jako dane
rzeczywiste pochodzą ze zrelaksowanych symulacji atomistycznych; nie są
walidacją na pozycjach molekuł wykrytych w STM.
[Denell i in., 2025](https://www.nature.com/articles/s41524-024-01498-x).

Implementacja obsługuje układy skończone i periodyczne, lecz szuka powtarzania
w dwóch lub trzech kierunkach; dokumentacja wyłącza struktury jednowymiarowe.
To kandydat dla regularnych sieci, nie uniwersalne grupowanie dowolnych
nieregularnych obiektów.
[Dokumentacja autorów, źródło MDX](https://github.com/FAIRmat-NFDI/matid/blob/5aa27776df0277e2b75af8680bd0faf760cf924a/docs/docs/learn/symmetry-based-clustering/symmetry-based-clustering.mdx).

Odczyt kodu wersji `5aa27776df0277e2b75af8680bd0faf760cf924a` ujawnił istotne
warunki adaptacji: `max_cell_size`, `pos_tol`, promienie obiektów, progi połączeń
i nakładania oraz ziarno losowania. Dozwolona jest własna tablica promieni.
Domyślne promienie atomowe i odległości w Å nie są sensownym modelem bboxów
molekuł. Po wyszukiwaniu i łączeniu regionów `_clean_clusters` pozostawia
największą połączoną część każdego regionu; funkcja nie wraca potem do
wyszukiwania nowych regionów. Wpływ na kompletność dwóch rozłącznych skupisk
tego samego wzoru trzeba sprawdzić — nie zakładamy, że obie domeny zawsze
zostaną zachowane.
[SBC: implementacja](https://github.com/FAIRmat-NFDI/matid/blob/5aa27776df0277e2b75af8680bd0faf760cf924a/matid/clustering/sbc.py).

**Wniosek dla nas:** wartościowy niezależny kandydat punktowy, szczególnie jako
sprawdzenie, czy metoda potrafi odkryć komórkę inną niż trójkątna. Odporność na
braki detekcji, granice przesunięcia i wielomolekularne motywy pozostaje do
zmierzenia. Zależności obejmują ASE, spglib, NumPy, scikit-learn i NetworkX;
pakiet ma także komponent kompilowany. Dostępność kodu i testów nie jest
potwierdzeniem transferu do STM.
[Konfiguracja MatID](https://github.com/FAIRmat-NFDI/matid/blob/main/pyproject.toml),
[testy SBC](https://github.com/FAIRmat-NFDI/matid/blob/5aa27776df0277e2b75af8680bd0faf760cf924a/tests/clustering/test_sbc.py).

### 4. Lokalne widmo, autokorelacja i EWT: domeny z obrazu

**Wejście:** obraz; **wyjście:** mapy lokalnego wzoru, następnie segmenty.
Najbliższy bezpośredni precedens STM to Bui i współautorzy: rozdzielenie obrazu
na składową jasności i teksturę, dwuwymiarowe falki empiryczne oraz grupowanie
tekstur. Pokazano obrazy monowarstw cyjankowych na Au(111). Oryginalna metoda
wymaga wybrania liczby klastrów; automatyczne znalezienie składowych widma
nie oznacza samoczynnego ustalenia liczby typów lub domen.
[Bui i in., pełny tekst, zwłaszcza §4–5](https://arxiv.org/pdf/1804.08890).

Publiczny pakiet `pyewt` autora EWT udostępnia transformacje 2D, w tym
kierunkowe curvelets i warianty oparte na Voronoi/watershed. Jest dostępny
w Pythonie na licencji MIT. To implementacja transformacji, a nie potwierdzone
odtworzenie całego procesu segmentacji STM z publikacji.
[Repozytorium pyewt](https://github.com/jegilles/pyewt).

Prostszy dostępny składnik porównania to bank Gabora: filtry dla wybranych
kierunków i częstotliwości, z których można budować lokalny opis tekstury.
Przykład scikit-image pokazuje klasyfikację tekstur, ale także błędne
dopasowanie obróconego przykładu; nie jest dowodem pełnej odporności na obrót.
[Dokumentacja i przykład Gabora](https://scikit-image.org/docs/stable/auto_examples/features_detection/plot_gabor.html).

Dalszy kandydat to SynCrystal: transformacje synchrosqueezed do analizy
granic ziaren, orientacji i deformacji na obrazach kryształów. Autorzy
udostępniają MATLAB/MEX i przykłady. Rozwinięcie *phase-space sketching*
buduje opis niezmienniczy także względem skali — dlatego u nas rozstaw
musiałby pozostać dodatkową cechą. Jest to alternatywa badawcza dla obrazów
z wyraźną periodycznością, z większym przewidywanym kosztem przeniesienia
do Python niż Gabor.
[Kod SynCrystal](https://github.com/SynCrystal/SynCrystal),
[Lu i Yang: reprezentacja i jej niezmienniczości](https://arxiv.org/abs/1703.10877).

**Wniosek dla nas:** to pierwszy kandydat do próby obrazowej, porównany
z prostszą lokalną autokorelacją lub bankiem filtrów Gabora w kilku skalach.
Może dostarczać informacji również pomiędzy oznaczeniami. Trzeba oddzielić
podobieństwo typu od kierunku oraz zachować częstotliwość odpowiadającą
rozstawowi. Samo widmo mocy nie daje pełnego opisu granicy przesunięcia;
to już ujawniła [próba 12](phase-boundaries-trial.md). Lokalny brak widocznego
wzoru pozostaje brakiem dowodu, szczególnie w ciemnej niższej warstwie.
Koszt przewidywany: średni; pamięć rośnie wraz z liczbą skal i kierunków,
więc próba powinna mierzyć czas i pamięć na klatkę.

### 5. Graf podobieństw i granic: zamiana cech w konkretne domeny

**Wejście:** obiekty, piksele lub małe regiony oraz dowody „należą razem”
i „powinny być rozdzielone”. **Wyjście:** przestrzenny podział.
Mutex Watershed uwzględnia krawędzie przyciągające i odpychające, bez ustalonej
liczby segmentów. Publikacja pokazuje segmentację mikroskopii elektronowej
z relacjami przewidywanymi przez sieć. Określenie algorytmu jako bezparametrowego
dotyczy etapu podziału grafu; nie usuwa konieczności skonstruowania dobrych
relacji wejściowych.
[Wolf i in.](https://arxiv.org/abs/1904.12654),
[implementacja affogato](https://github.com/constantinpape/affogato).
Biblioteka eksportuje także `compute_mws_clustering` dla grafu, obok wariantu
segmentacji obrazu. Dostępność tego interfejsu nie dostarcza automatycznie
wag relacji odpowiednich dla molekuł.
[Eksportowane funkcje](https://github.com/constantinpape/affogato/blob/master/src/python/module/affogato/segmentation/__init__.py).

Wariant wspomagany użytkownikiem daje ilastik: mapa granic, małe regiony
i ich łączenie przez multicut. Mapę można otrzymać przez uczenie klasyfikatora
na wskazanych przykładach lub dostarczyć zewnętrznie. To gotowy warsztat
do badania informacji o granicach, nie gotowy detektor domen molekularnych.
[Dokumentacja multicut](https://www.ilastik.org/documentation/multicut/multicut),
[klasyfikacja pikseli](https://www.ilastik.org/documentation/pixelclassification/pixelclassification).

**Wniosek dla nas:** najbardziej uniwersalna konstrukcja dla dowolnych
zaznaczonych elementów, o ile umiemy opisać ich podobieństwo. Węzeł może
oznaczać molekułę albo inny obiekt. Relacje mogą łączyć geometrię, wygląd
i granicę widoczną w obrazie. Powinny być lokalne, aby nie zlewać odległych
obszarów tego samego typu w jedną domenę. To nasza adaptacja, nie wynik
publikacji STM. Sama suma masek obiektów nadal nie wyznacza powierzchni
całego płata. ilastik wymagałby przykładów granic lub decyzji „połącz/rozdziel”;
obecne przybliżone ramki nie są takimi dokładnymi etykietami.

### 6. Uczone cechy wycinków: możliwość na późniejszy etap

**Wejście:** wycinki obrazu; **wyjście:** opis wyglądu i ewentualnie osobny
obrót. AtomAI implementuje rotacyjny autoenkoder wariacyjny `rVAE`, który
rozdziela zmienne kąta, przesunięcia i treści wycinka; model trzeba dopasować
do danych. Publiczne API używa PyTorch. Nie zwraca bezpośrednio domen ani
gotowego katalogu struktur.
[Kod i przykład treningu rVAE](https://atomai.readthedocs.io/en/latest/_modules/atomai/models/dgm/rvae.html).

Istnieje też bezpośredni przykład użycia cech wstępnie wytrenowanej sieci
na STM: Kolev i współautorzy grupują cechy pierwszych warstw FCNResNet101
przez k-means. Pokazują m.in. dwa kierunki rzędów dimerów na Si(001).
Liczbę grup wybiera użytkownik, a rozdzielczość przetwarzania zmienia podział;
nie jest to automatyczne odkrywanie dowolnych sieci molekularnych. Autorzy
udostępniają kod, więc ten wariant można później porównać z ręcznie
dobranymi cechami tekstury.
[Kolev i in., §3.2](https://arxiv.org/html/2506.01678v2#S3.SS2),
[repozytorium autorów](https://github.com/nickkolev97/FSL_STM).

**Wniosek dla nas:** rozsądny drugi etap, jeżeli cechy geometryczne i teksturowe
nie rozróżnią istotnych motywów. Wycinek musi obejmować otoczenie, jeśli
szukamy układu sąsiadów; wycinek jednej molekuły może dać tylko podobieństwo
jej wyglądu. Przy symetrycznych motywach odzyskany kąt może być niejednoznaczny.
Trening, wybór rozmiaru wycinka i stabilność między akwizycjami zwiększają
koszt w porównaniu z pierwszą próbą bez uczenia. Nie rozpoczynamy od tej
rodziny tylko dlatego, że jest bardziej złożona.

## Jak objąć także inne zaznaczone elementy

Nie trzeba wymagać chemicznej tożsamości obiektu. Można użyć jego centrum,
maski lub bboxa, cech wyglądu oraz relacji do sąsiadów. Gotowe narzędzia
pomiaru oznaczonych regionów zwracają m.in. pole, środek, wydłużenie,
orientację i statystyki jasności.
[scikit-image: regionprops](https://scikit-image.org/docs/stable/api/skimage.measure.html#skimage.measure.regionprops).

Proponowane rozdzielenie jest następujące: **cechy samego obiektu** odpowiadają
na pytanie, które elementy wyglądają podobnie; **cechy jego otoczenia** mówią,
które leżą w podobnym układzie; **graf przestrzenny** wskazuje, które tworzą
jedną domenę. Te trzy informacje można łączyć, zachowując osobne wyniki.
Przykładowo podobne molekuły w dwóch odległych wyspach mogą mieć ten sam typ,
lecz różne identyfikatory domen. Różny wygląd dwóch molekuł naprzemiennie
ułożonych w jednej sieci nie musi dzielić tej sieci na dwie domeny.

Ten opis możliwości nie przywraca do zakresu implementacji odłożonego pomiaru
orientacji pojedynczej molekuły. Orientacja obiektu i orientacja sieci są
różnymi wielkościami; bieżący wybór metody nadal podlega [mapie](map.md).

## Trzy zalecane próby

Poniższa kolejność jest **naszą rekomendacją**, nie wyborem metody docelowej.
MolTrack pozostaje zamrożonym porównaniem. Nie dopasowujemy nowej metody
wyłącznie do odzyskania trzech kolorów TTMAPP.

1. **Zaznaczone elementy → opis otoczenia → typy i domeny.** Porównać prosty
   opis geometrii z SOAP, zastosować grupowanie bez ustalonej liczby typów,
   a domeny wydzielić po sąsiedztwie i zgodności orientacji. XY + HDBSCAN
   będzie kontrolą, która pokaże, ile wnosi sama gęstość. Pierwsze pytanie:
   czy metoda odróżnia układ i rozstaw bez narzucenia M3/M6?
2. **SBC / MatID na tych samych punktach.** Sprawdzić odkrywanie komórek,
   obrócone ziarna i rozłączne kopie tej samej sieci. Pierwsze pytanie:
   czy jawna powtarzalność daje stabilniejszy wynik niż grupowanie lokalnych
   cech, przy realistycznych brakach i błędach detekcji?
3. **Obraz → tekstura w kilku skalach → domeny.** Porównać EWT z prostszą
   autokorelacją/Gaborem, następnie grupowanie cech oraz lokalne łączenie
   fragmentów. Rozdzielić orientację i typ. Pierwsze pytanie: czy obraz
   niesie wystarczającą informację także tam, gdzie detekcje są niekompletne?

We wszystkich próbach potrzebny jest jawny wynik niepewny lub brak danych.
Algorytm nie może być nagradzany za poprawność tylko na kilku wybranych
punktach przy jednoczesnym odrzuceniu większości materiału. Raportujemy
osobno zgodność przypisań, odsetek odmów, fałszywe podziały/scalenia,
zachowanie kąta i rozstawu oraz czas i pamięć. Następnie porównujemy, czy
połączenie obrazu i punktów poprawia konkretny stwierdzony błąd.

## Dane i granice możliwego odbioru

Używamy istniejących 54 wnętrz referencyjnych w 18 klatkach TTMAPP.
BLACK/RED/YELLOW oznaczają głównie różne orientacje tej samej sieci.
To nie trzy typy struktury i nie pełna segmentacja klatek. Nieoznaczona
część obrazu nie jest negatywną referencją. Kontury są przybliżone.
[Próba pokrycia](coverage-partial-reference-trial.md),
[próba katalogu](structural-type-catalogue-trial.md).

Obecne dane pozwalają porównywać wnętrza, zgodność orientacji, odmowy
i stabilność w znanych miejscach. Do kontroli ogólności wykorzystujemy
syntetyczne sieci o różnej geometrii i rozstawie, obrót bez zmiany typu,
dwie rozłączne kopie tego samego wzoru, granicę przesunięcia, pojedyncze
defekty, pas bez porządku oraz losowe punkty. Osobno zmieniamy kontrast,
szum, liczbę pominiętych centrów i liczbę fałszywych detekcji.

Nie deklarujemy trafności pełnego pokrycia ani dokładności granic z tych
referencji. Kolejne oznaczenia powinny odpowiedzieć na konkretną niewiadomą
ujawnioną próbą; nie są warunkiem rozpoczęcia powyższego porównania.
Kalibrację parametrów i ocenę należy oddzielić, a sąsiednich klatek tej samej
akwizycji nie przedstawiać jako niezależnego sprawdzenia na nowym materiale.

## Status badania

Sprawdzono metadane lokalnego środowiska `netcat`: dostępne są NumPy 2.2.5,
SciPy 1.15.2, scikit-learn 1.6.1, scikit-image 0.25.2, ASE 3.25.0 i
PyTorch 2.9.1+cu128. HDBSCAN jest częścią tej wersji scikit-learn; osobny pakiet
`hdbscan` nie jest wymagany do pierwszej próby. Brakuje zainstalowanych
MatID, DScribe, pyewt, affogato, AtomAI i umap-learn. To odczyt metadanych,
bez importowania tych bibliotek i bez potwierdzenia ich zgodnego działania.

Sprawdzono publikacje, dokumentację autorów i wskazane implementacje.
W MatID odczytano również sekwencję wyszukiwania, łączenia i czyszczenia
klastrów oraz konfigurację zależności. Nie instalowano bibliotek, nie
uruchamiano nowych algorytmów ani testów ich skuteczności na TTMAPP.
Kroki 10–12 zachowują status zakończonych eksperymentów; wybór i odbiór
metody nadal pozostają otwarte.
