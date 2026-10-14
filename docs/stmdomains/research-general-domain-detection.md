# Ogólne wykrywanie uporządkowania i domen molekularnych

Data badania: **2026-10-14**. Status: **notatka badawcza, bez wyboru architektury**.
Zakres: zarówno rozmieszczenie centrów molekuł, jak i orientacja samych molekuł.
**Pozycje molekuł będą danymi wejściowymi z YOLO albo ręcznego oznaczania.**
Mapa i tickety powstaną później. Nie przeprowadzono eksperymentów na danych użytkownika.

## Odpowiedź

**Tak: można szukać powtarzalnych lokalnych struktur i ich przestrzennych granic bez
zamkniętej listy domen A/B/C czy obowiązkowej symetrii M6.** Istnieje bezpośredni
precedens segmentacji tekstur na rzeczywistych obrazach STM monowarstw CN/Au{111}:
rozdzielenie tła i tekstury, empiryczne falki oraz grupowanie podobnych cech obrazu.
To potwierdzenie wykonalności podejścia, nie gwarancja skuteczności na dowolnym
układzie molekularnym. [Bui i in., preprint 2018, publikacja DOI](https://arxiv.org/abs/1804.08890),
[wydanie czasopisma](https://doi.org/10.1007/s10044-019-00824-0).

Proponowane znaczenie „ogólności” dla STM Domains: **typy lokalnego uporządkowania
wyłaniają się z danych, a użytkownik może je później interpretować**. Pozostają
założenia o skali sąsiedztwa, jakości sygnału, podobieństwie struktur i tym, co uznajemy
za granicę. To propozycja kierunku badania, a nie już potwierdzona właściwość programu.

Przy znanych centrach proponowany punkt startu eksperymentu to **sąsiedztwa punktów
→ cechy odległości i kątów → pomiar motywu na wycinku obrazu przy każdym centrum
→ przestrzennie spójne domeny**. Maski molekuł są opcjonalne. Analiza FFT/falkowa
całego obrazu może uzupełniać i kontrolować wynik; nie trzeba ponownie rozwiązywać
zadania detekcji molekuł.

Przegląd uzupełniono o prace z lat 2024–2026, opisane niżej w sekcji
„Nowsze rozwiązania”. Najbliższe naszemu wejściu są odkrywanie powtarzalnych
komórek przez SBC/MatID oraz grupowanie deskryptorów punkt + orientacja molekuły.
Nadal są to kandydaci do porównania.

## Co rzeczywiście zakłada MolTrack

Audyt kodu bieżącego worktree, baza Git `0e8bc53`:

- Nie ma listy dozwolonych absolutnych pozycji XY: analiza przyjmuje skalibrowane
  centra molekuł i buduje ich sąsiedztwo. Nie narzuca też z góry liczby znalezionych
  domen. [Wejście analizy](../../moltrack/analysis/orientation_domain_analysis.py#L203).
- Gałąź M6 narzuca `symmetry_m=6`; ma też konfigurowalne zakresy odległości pierwszej
  otoczki, domyślnie 1,0–2,6 nm, oraz progi orientacji, jakości i liczebności.
  [Ustawienia M6](../../moltrack/analysis/m6_settings.py#L64).
- Nowszy klasyfikator lokalnej symetrii porównuje modele `trifold`, `sixfold`,
  `mixed` i `disordered`. Ciągła orientacja sieci jest już analizowana, ale katalog
  modeli struktury pozostaje określony w kodzie.
  [Klasyfikator](../../moltrack/analysis/local_symmetry_evidence_classifier.py#L55),
  [modele](../../moltrack/analysis/local_symmetry_evidence_models.py#L14).
- Teksturowy preset TTMAPP używa trzech klas A/B/C i ustalonych prototypów histogramów.
  Jest oznaczony jako eksperymentalny; jego opis podaje kalibrację i walidację czasową
  w obrębie jednej akwizycji. Adapter pobiera obraz wokół znanych centrów molekuł.
  [Preset](../../moltrack/analysis/texture_domain_analysis.py#L628),
  [adapter](../../moltrack/analysis/domain_analysis/texture_abc_adapter.py#L32).
- Istnieje też estymator orientacji pojedynczej molekuły: oś PCA maski oraz
  zastępczy pomiar z topografii. To kandydat do ponownego użycia dla osi modulo 180°, a nie
  uniwersalny pomiar dowolnego motywu. Niższa warstwa obliczeń porządku przyjmuje
  wiele harmonicznych mimo ograniczeń publicznych ustawień M6.
  [Estymator](../../moltrack/analysis/molecular_orientation_estimator.py#L79),
  [harmoniczne](../../moltrack/analysis/_local_harmonic_bond_order.py#L45).

Zatem uogólnienie dotyczyłoby przede wszystkim **reprezentacji lokalnej struktury
i sposobu znajdowania jej odmian**, a nie samego dopuszczenia dowolnych współrzędnych.

## Co rozdzielić w wyniku

Poniższe rozróżnienia są proponowaną definicją problemu na potrzeby przyszłego
eksperymentu. Nie stanowią jeszcze modelu danych aplikacji.

| Wielkość | Pytanie | Przykładowy wynik |
| --- | --- | --- |
| Uporządkowanie położeń | Czy centra tworzą powtarzalny układ? | Mapa regularności, skali i lokalnej geometrii |
| Orientacja sieci | W którą stronę biegnie układ sąsiadów? | Pole kątów wraz z niejednoznacznością symetrii |
| Orientacja molekuły | Jak obrócony jest motyw pojedynczej cząsteczki? | Kąt lub kilka nierozróżnialnych kątów; jakość pomiaru |
| Uporządkowanie orientacyjne | Czy orientacje cząsteczek tworzą spójny wzór? | Zgodny kierunek albo powtarzalny układ naprzemienny |
| Typ struktury | Które fragmenty mają podobny lokalny wzór? | Typ 1, typ 2… odkryte w danych |
| Konkretna domena | Gdzie leży spójny obszar danego uporządkowania? | Maska i granica pojedynczego obszaru |

Proponujemy zachować oddzielne wyniki dla położeń i orientacji molekuł. Dwa odległe
obszary mogą należeć do tego samego typu, ale stanowić osobne domeny. Regularna sieć
centrów z chaotycznymi orientacjami cząsteczek nie powinna dostawać takiego samego
opisu jak układ uporządkowany na obu poziomach. Naprzemienne orientacje również
trzeba traktować jako możliwy wzór, a nie automatycznie jako nieporządek.

## Metody warte porównania

### Sąsiedztwo znanych centrów — proponowany punkt startu

Parametr dwuwymiarowego uporządkowania wiązań można zapisać jako
`ψₘ(i) = Σⱼ wᵢⱼ exp(i m θᵢⱼ) / Σⱼ wᵢⱼ`, gdzie `θᵢⱼ` to kierunek do sąsiada.
Moduł opisuje zgodność kierunków z daną harmoniczną; faza niesie orientację.
Orientacja reprezentowana przez `ψₘ` jest określona modulo `2π/m`. Biblioteka
freud udostępnia taki parametr dla dowolnego wybranego `m`, nie tylko 6.
[Oficjalna dokumentacja Hexatic/k-atic](https://freud.readthedocs.io/en/stable/modules/order.html#freud.order.Hexatic).

Propozycja uogólnienia: zamiast zwycięstwa jednego modelu M6 użyć wektora wielu
harmonicznych wraz z odległościami i korelacjami sąsiedztwa; zestaw harmonicznych
pozostaje parametrem metody. Sam wysoki moduł jednej harmonicznej nie będzie
w tym eksperymencie wystarczającym kryterium wykrycia domeny.

Boattini i in. grupowali środowiska cząstek, używając wektorów parametrów
uporządkowania, autoenkodera i mieszanin Gaussa. Pokazali różne lokalne struktury
w symulacjach koloidów, także przy współistnieniu faz i granicach ziaren.
To precedens odkrywania środowisk, ale nie walidacja detekcji z surowego STM.
[Boattini, Dijkstra i Filion, 2019](https://arxiv.org/abs/1907.02420).

Bardziej ciągłą reprezentację podobieństwa sąsiedztw oferuje SOAP, który opisuje
otoczenie przez gęstości sąsiadów. Oryginalna praca dotyczy środowisk atomowych
i dopasowania energii, nie segmentacji STM. Niezmienniczość względem obrotu jest
celową właściwością tej reprezentacji; sama nie zachowa orientacji domeny.
Wniosek dla eksperymentu: ewentualny deskryptor tego typu trzeba uzupełnić
osobną informacją o obrocie.
[Bartók, Kondor i Csányi, 2013](https://arxiv.org/abs/1209.3140).

### Motyw pojedynczej molekuły i jego orientacja

Ziatdinov i in. analizowali rzeczywiste obrazy STM sumanenu na złocie, rozpoznając
stany strukturalne i obrotowe molekuł przez model pola Markowa i sieć konwolucyjną.
Następnie badali korelacje przestrzenne tych stanów. Wykorzystali informacje
o badanym układzie i symulacje DFT, więc nie jest to rozwiązanie bez ustalonego
katalogu klas. Praca potwierdza jednak zasadność odrębnego pomiaru motywu
cząsteczki i korelacji pomiędzy sąsiadami.
[Ziatdinov, Maksov i Kalinin, 2017](https://www.nature.com/articles/s41524-017-0038-7).

Propozycja: badać kąt i wygląd lokalnego motywu razem z relacjami sąsiedztwa.
Naprzemienne orientacje lub jodełka powinny móc tworzyć jedną uporządkowaną
domenę; grupowanie wyłącznie pojedynczych kątów rozdzieliłoby taki wzór błędnie.

### Od podobnych cech do przestrzennych domen

HDBSCAN umożliwia grupowanie bez zadanej liczby klastrów i pozostawienie części
próbek poza klastrami. Nadal wymaga m.in. metryki i minimalnej wielkości grupy;
siła przynależności nie jest automatycznie prawdopodobieństwem fizycznej poprawności.
[Oficjalna dokumentacja HDBSCAN](https://scikit-learn.org/stable/modules/generated/sklearn.cluster.HDBSCAN.html).

Propozycja: porównać taki wariant z prostym grupowaniem i łączeniem sąsiadujących
podobnych obszarów. Zachować oddzielnie identyfikator typu i identyfikator domeny.
Wymagać przestrzennej spójności, ale nie wygładzać granic tak silnie, żeby znikały
małe domeny albo wąskie przerwy. Klaster odrzucony przez algorytm nie powinien być
automatycznie nazwany fizycznym nieporządkiem.

### Lokalna tekstura obrazu — uzupełnienie i kontrola

**Lokalna autokorelacja i lokalne widmo FFT.** Wang i in. obliczają lokalne
deskryptory symetrii, redukują ich wymiar przez PCA i grupują je przez k-means,
bez wcześniejszej znajomości struktury kryształu. Przykłady obejmują HAADF-STEM
i filmy TEM: to materiał do przeniesienia na STM, nie dowód walidacji na STM.
Autorzy porównują lokalną korelację z widmem FFT i pokazują ograniczenia małych
okien oraz potrzebę doboru parametrów.
[Wang i in., 2021](https://doi.org/10.1017/S1431927621012770).

**Falki kierunkowe / empiryczne.** Bui i in. pokazują segmentację obrazów STM
według lokalnej energii składowych tekstury; w badanej metodzie liczba klastrów
jest wybierana przez użytkownika. Automatyczne znalezienie składowych widma nie
oznacza automatycznego ustalenia liczby fizycznych domen. Wyniki zawierają również
przykłady błędów przy granicach i złożonych teksturach.
[Bui i in., §4–5](https://arxiv.org/pdf/1804.08890).

Borodinov i in. pokazali analizę domen molekularnych w AFM przez cechy tekstury
i uczenie nadzorowane. Kryteria klasyfikacji są tam wcześniej wybrane; nie jest
to gotowy algorytm odkrywania nieznanych typów.
[Borodinov i in., 2020, opis autorów w ORNL](https://www.ornl.gov/publication/machine-learning-based-multidomain-processing-texture-based-image-segmentation-and).

Propozycja: porównać wynik analizy punktów z mapami lokalnej autokorelacji,
FFT lub falek w kilku rozmiarach okna, szczególnie przy spornych granicach.

## Nowsze rozwiązania — przegląd na 2026-10-14

Nowsze publikacje rozwijają kilka różnych części zadania: wyszukiwanie
periodycznych obszarów, odkrywanie klas otoczenia, opis orientacji molekuł
i segmentację obrazu. Nie należy traktować tych wyników jako wymiennych.
Poniższy wybór uwzględnia znane centra z YOLO lub ręcznych oznaczeń;
sprawdzono dostępność publicznego kodu, ale nie odtwarzano jego działania ani wyników.

**SBC / MatID — Denell i in., 6.02.2025.** Algorytm znajduje lokalnie komórkę
powtarzalnego układu, a następnie przypisuje do niej zgodne punkty. Wejściem są
współrzędne i gatunki atomów, wynikiem grupy oraz odpowiadające im komórki.
Badanie obejmuje modele stosów materiałów 2D i granic ziaren, z kontrolowanymi
zakłóceniami. Nie wymaga uczenia ani katalogu szablonów kryształów.
[Publikacja](https://doi.org/10.1038/s41524-024-01498-x).
Publiczny [kod MatID](https://github.com/FAIRmat-NFDI/matid) i
[dokumentacja SBC](https://fairmat-nfdi.github.io/matid/docs/learn/symmetry-based-clustering/)
udostępniają analizę struktur skończonych i periodycznych. Ograniczeniem jest
założenie powtarzalności w dwóch lub trzech kierunkach oraz dobór tolerancji,
rozmiaru komórki i promieni definiujących połączenia.
[Parametry implementacji](https://fairmat-nfdi.github.io/matid/docs/reference/sbc/).
Obecna implementacja nie obsługuje struktur powtarzających się tylko w jednym
kierunku, np. łańcuchów.
[Zakres SBC](https://fairmat-nfdi.github.io/matid/docs/learn/symmetry-based-clustering/).
Wniosek: to konkretny kandydat dla regularnych pól znanych centrów; przeniesienie
z atomów na molekuły wymaga adaptacji skali i relacji sąsiedztwa. Nie zapewnia
pomiaru obrotu samej molekuły ani wykrycia każdego rodzaju porządku nieperiodycznego.

**Deskryptory środowiska + UMAP — Ulugöl i in., publikacja 2026.** Praca porównuje
PCA, autoenkodery i UMAP na deskryptorach uporządkowania wiązań oraz asymetrii
otoczenia. Walidacja obejmuje symulacje i eksperymentalnie wyznaczone pozycje
cząstek koloidalnych w strukturze 3D. UMAP dawał najlepsze wyniki w badanych
przypadkach. To nowsze rozwinięcie podejścia Boattini, bez zadanej listy klas
w samym grupowaniu. [Artykuł, online 10.02.2026](https://doi.org/10.1063/5.0302107),
[preprint od 8.09.2025](https://arxiv.org/abs/2509.07186).
[Repozytorium autorów](https://github.com/alptug/Comparing-dimensionality-reduction-methods-for-local-structural-identification-in-colloidal-systems)
zawiera kalkulator deskryptorów, notebooki i przykładowe dane. Transfer wymaga
reprezentacji odpowiedniej dla 2D i osobnego kanału orientacji: skalarne cechy
niezmiennicze względem obrotu nie wystarczą do rozdzielenia obróconych domen.
Wyjściowa klasa środowiska nadal wymaga sprawdzenia spójności przestrzennej.

**Pozycja i orientacja w jednym deskryptorze — Kuroshima i in., 3.07.2024.**
Reprezentacja *punkt + wektory* obejmuje środki molekuł i ich względne
orientacje; alternatywą jest graf atomistyczny. Autorzy klasyfikują otoczenia
w symulacjach kryształów mocznika i nikotynamidu, także przy interfejsach.
Klasyfikator jest nadzorowany i rozpoznaje znane polimorfy, więc nie jest gotowym
rozwiązaniem odkrywania nieznanych domen. [Publikacja](https://doi.org/10.1021/acs.jctc.4c00418),
[preprint od 29.03.2024](https://arxiv.org/abs/2404.00155).
Dostępne są [MolStrucClassifier](https://github.com/rogalj/MolStrucClassifier)
i [wariant grafowy](https://github.com/InfluenceFunctional/MXtalTools/tree/mol_classifier).
Dla STM Domains interesująca jest reprezentacja: pozwala uwzględnić różne
układy obrotów przy identycznych centrach. Jej połączenie z grupowaniem bez etykiet
byłoby naszym eksperymentem, nie wynikiem już wykazanym w tej pracy.

**Segmentacja domen bezpośrednio na STM — Kolev i in., publikacja 2026.**
Pierwszy moduł wykorzystuje cechy wczesnych warstw sieci FCNResNet101,
wytrenowanej wcześniej na ImageNet, oraz k-means. Na rzeczywistym Si(001)
pokazano rozdzielenie obszarów rzędów dimerów obróconych o 90°. Zmiana
rozdzielczości przetwarzania zmienia szczegółowość podziału. Liczbę klastrów
wybiera użytkownik; dalszy moduł few-shot wymaga wskazanych klas i przykładów.
[Publikacja](https://doi.org/10.1088/2632-2153/ae520e),
[pełny tekst, §3.2 i rys. 3f; preprint 2025, wersja 2 z 18.06.2026](https://arxiv.org/html/2506.01678v2).
Jest [publiczny kod i modele](https://github.com/nickkolev97/FSL_STM).
To bezpośredni nowszy precedens segmentacji orientacji sieci w STM, lecz jeszcze
nie walidacja odkrywania domen dowolnych molekuł. Przy naszych znanych centrach
warto rozważyć go jako obrazową kontrolę wyniku.

**UniMR — online 15.12.2025, wydanie czasopisma 2026.** Praca rozpoznaje
molekuły w pięciu układach molekuła/podłoże STM. Porównuje reprezentację pikselową
i CLIP, wybierając cechy przez analizę GMM, następnie wyszukuje obiekty podobne
do wskazanego wzorca. Normalizacja wyrównuje obroty i odbicia lustrzane.
[Publikacja](https://doi.org/10.1002/advs.202516428).
Wniosek: to pomoc w porównywaniu wyglądu, ale normalizacja usuwa różnice ważne
dla domen orientacyjnych i chiralnych. Nie jest gotowym miernikiem orientacji.
Mimo deklaracji autorów o otwartym rozwiązaniu nie potwierdzono publicznego
repozytorium powiązanego z publikacją; dostępność kodu wymaga dalszego ustalenia.

**Sąsiedztwo bez sztywnej otoczki.** mSANN poprawia nadliczanie sąsiadów starego
SANN w układach o małej koordynacji; opisano testy układów 2D i 3D.
[Publikacja, online 16.03.2026](https://doi.org/10.1063/5.0311865),
[preprint od 13.11.2025, aktualizacja 10.09.2026](https://arxiv.org/abs/2511.10748),
[kod SANNpy](https://github.com/alptug/SANNpy).
To komponent do porównania z Delaunay i lokalną skalą, nie kompletny detektor domen.
W dalszej perspektywie istnieje też grafowy autoenkoder MEAGraph (2026),
grupujący deskryptory atomowych środowisk; jego demonstracje dotyczą baz
potencjałów atomowych, a nie przestrzennej segmentacji STM.
[Publikacja](https://doi.org/10.1088/2632-2153/ae39a1),
[kod](https://github.com/LLNL/MEAGraph).

**Nowsze grupowanie nie usuwa potrzeby walidacji.** Kývala i in. (27.02.2025)
porównali PCA, UMAP i PaCMAP na symulacjach krzemu oraz wody. Wskazali
sztuczne klastry zależne od inicjalizacji, trudności przy nierównych liczebnościach
i konieczność uśredniania niektórych deskryptorów w czasie. Nie potwierdzili
uniwersalnej przewagi PaCMAP. [Publikacja](https://doi.org/10.1038/s41524-025-01544-2),
[dane autorów](https://zenodo.org/records/13789144).
Wniosek dla prób: wybór deskryptora, skali oraz stabilność wyniku są równie
istotne jak wybór algorytmu grupowania. Kolorowe klastry w rzucie 2D nie są
samodzielnym dowodem istnienia fizycznych domen.

## Ograniczenia istotne dla obu rodzajów uporządkowania

Lokalna autokorelacja nie zachowuje całej informacji o motywie. Wang i in.
wskazują, że różne symetrie motywu mogą mieć tę samą symetrię Pattersona;
proponują dodatkowe deskryptory obrotów i odbić.
[Wang i in., sekcje o translacji, obrotach i odbiciach](https://doi.org/10.1017/S1431927621012770).

Wniosek matematyczny dla naszego zadania: przesunięcie idealnego okresowego
motywu zmienia fazę Fouriera, lecz nie jego widmo mocy. Dlatego dwie domeny
przesunięte względem siebie, z tym samym okresem i orientacją, mogą wyglądać
tak samo w deskryptorze widmowym; sygnał może pozostać tylko w pasie granicy.
W przyszłym porównaniu potrzebny jest osobny przypadek antyfazy, a przy jego
niepowodzeniu analiza fazy/przemieszczeń lub jawnych relacji sąsiedztwa.

Proponowane reguły interpretacji wyniku:

- Rozdzielać **brak wykrytego porządku**, **nieznany uporządkowany wzór** oraz
  **zbyt słaby sygnał do oceny**.
- Nie utożsamiać niskiej jakości obrazu z nieporządkiem molekularnym.
- Dla orientacji molekuły zachować niejednoznaczność: jeżeli widoczny motyw ma
  symetrię `q`, kąt jest rozróżnialny tylko modulo `2π/q`. Nie narzucać jednej
  wartości `q` wszystkim możliwym molekułom.
- Wykrywać orientację motywu tylko tam, gdzie sygnał pozwala ją odróżnić.
  Sam układ centrów nie zawiera pomiaru obrotu cząsteczki wokół jej centrum.
- Sprawdzić osobno zmiany kontrastu, dryf, pasy skanowania, ubytki detekcji
  i nadmierne wygładzanie. Są to proponowane próby odporności, nie stwierdzenie,
  że konkretne dane użytkownika zawierają te problemy.
- Dopuszczać ciągły gradient orientacji bez wymuszania dowolnej liczby ostrych granic.

## Proponowany eksperyment przed mapą

To plan sprawdzenia hipotezy; **żadnego z poniższych pomiarów jeszcze nie wykonano**.

1. Przygotować niewielki zestaw różnych akwizycji STM, obejmujący regularne
   rozmieszczenie, różne orientacje molekuł, granice i obszary trudne do oceny.
   Dla każdego wejścia zapisać lokalną ścieżkę, SHA-256, identyfikator akwizycji,
   kanał, klatkę, skalę x/y, warunki obrazowania i wszystkie operacje przygotowania.
   Dane i duże wyniki pozostawić poza Git.
2. Zachować wejściowe centra i niezależnie oznaczyć referencje: orientacje
   z ich symetrią i pewnością, obszary domen oraz pasy niepewnych granic.
   Jeśli to możliwe, porównać oznaczenia
   dwóch osób. Obszarów nierozstrzygalnych nie używać jako pewnej prawdy odniesienia.
3. Dodać kontrolowane obrazy syntetyczne: różne sieci, obrócone ziarna, antyfaza,
   identyczne centra z różnymi obrotami motywu, naprzemienne obroty/jodełka,
   powtarzalny motyw wielomolekułowy, gradient orientacji oraz brak domen.
   Osobno zmieniać jakość obrazu i błędy wejściowych pozycji/brakujące centra.
   Syntetyki sprawdzają znane własności; nie zastępują oceny na eksperymencie STM.
4. Porównać dwie hipotezy: **odkrywanie powtarzalnych komórek i obszarów przez
   SBC/MatID** oraz **wieloskalowe deskryptory centrów, grupowanie i osobny kanał
   orientacji molekuł**. Obecną analizę MolTrack pozostawić jako punkt odniesienia
   na zgodnych z nią przypadkach. Sprawdzić kilka definicji sąsiedztwa, w tym mSANN.
   Kontrolę obrazową zacząć od autokorelacji/FFT; metodę Koleva i in. rozważyć jako kolejny
   wariant. Oddzielić błędy grupowania na poprawnych centrach od skutków błędów
   wejściowych pozycji. To kolejność prób, nie wybór architektury.
5. Dobierać parametry na jednych akwizycjach, sprawdzać na innych. Nie traktować
   sąsiednich nakładających się wycinków tej samej klatki jako niezależnego testu.
   Zachować parametry, ziarno losowania, wersję kodu, maskę ważnych pikseli i wyniki.
   Sprawdzić również różne inicjalizacje i udział małych domen, żeby nie uznać
   niestabilnych klastrów ani zaniku rzadkiej struktury za własność próbki.

| Oceniany aspekt | Proponowany pomiar |
| --- | --- |
| Jakość wejściowych centrów | Wrażliwość wyników na błąd pozycji w nm, braki i duplikaty |
| Orientacja molekuł i sieci | Oddzielne rozkłady błędu kątowego modulo właściwa symetria; odsetek odmów pomiaru |
| Obszary domen | IoU/Dice po dopasowaniu masek, liczba nadmiernych podziałów i błędnych scaleń |
| Granice | Precision/recall w zadanym pasie tolerancji oraz błąd odległości w nm |
| Uporządkowanie | Wykrycie znanego porządku i liczba fałszywych domen na kontrolach bez porządku |
| Nieznane / niska jakość | Udział odrzucony oraz błąd wśród zaakceptowanych wyników, raportowane razem |
| Powtarzalność | Zmiana masek, kątów i liczby domen po zmianie okna, parametrów i zakłóceń |
| Użyteczność | Czas i pamięć dla zadanych rozmiarów obrazu; czas ręcznej korekty |

Progi akceptacji trzeba ustalić po poznaniu rozdzielczości danych i niepewności
referencji. Nie ma obecnie podstaw do deklaracji konkretnej dokładności programu.

## Materiały umożliwiające odtworzenie metod

Kod autorów Bui jest udostępniony jako narzędzia MATLAB wraz z obrazami
i skryptami odtwarzającymi segmentację.
[Microscopy-Codes](https://github.com/kbui1993/Microscopy-Codes).
Implementacja deskryptorów i segmentacji Wang jest dostępna jako pySTEM.
[Repozytorium autorów](https://github.com/NingWang1990/pySTEM).

Przeczytanie prac i kodu jest podstawą oceny wykonalności. W tej notatce nie
potwierdzamy instalacji, odtworzenia wyników publikacji ani skuteczności na danych
STM Domains. Dalszy wybór metody powinien wynikać z opisanego porównania.
