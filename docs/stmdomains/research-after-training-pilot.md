# Po próbach 21–26: wnioski i następny kierunek badań

Data: **2026-11-01**. Synteza zapisanych wyników i przegląd źródeł pierwotnych.
To rekomendacja badawcza, **bez nowego treningu, eksperymentu i wyboru detektora**.
Odbiór 13 i jakość 04 pozostają otwarte. Użytkownik poprosił o porównanie
wariantu bez etykiet treningowych z wariantem z małymi ręcznymi oznaczeniami.

**Rekomendacja:** najpierw rozstrzygnąć, czy potrafimy odczytać lokalną granicę
z obrazu przy zachowaniu informacji przestrzennej. Dopiero po takim wyniku
uczyć mały model relacji/granic, ewentualnie z gotowym zamrożonym enkoderem.
Obecne wyniki nie uzasadniają kolejnej szerokiej serii autoenkoderów ani
treningu dużego modelu od zera. Sama zmiana nazwy enkodera nie adresuje
wykazanych problemów: mieszania kontekstu, błędów granic i limitu bramki.
To wniosek projektowy z poniższych badań, nie dowód niemożliwości użycia SSL.

## 1. Czego dowiodły wykonane próby

| Próba | Wynik istotny dla decyzji | Wniosek w granicach wykonanego testu |
| --- | --- | --- |
| [21: AE/rVAE](autoencoder-domains-trial.md) | 18 fitów; brak poprawy końcowych domen | Odtwarzanie wycinka nie wystarczyło jako cel uczenia reprezentacji dla obecnego podziału. |
| [21a: dekoder i KL](rvae-decoder-kl-trial.md) | Słabsze KL poprawia rekonstrukcję o około 14%; transfer nadal 0/174 | Naprawa części zachowania rVAE nie rozwiązuje zadania domen. |
| [22: lokalny SSL](local-self-supervised-trial.md) | 9 fitów; transfer 0/174, transdukcja najwyżej 4/782; błędy granic także przed odmowami | Zastosowany cel podobieństwa i odczyt cech nie zapewniają potrzebnych relacji przestrzennych. |
| [23: porównanie](training-comparison-and-next-step.md) | Brak wyboru detektora po porównaniu 19/21/21a/22 | Negatywna decyzja o ówczesnym pilocie, później rozszerzonym poleceniami 24–26. |
| [24: grafowy SSL](graph-self-supervised-trial.md) | FH przypisuje 178–183/204 centrów testowych, lecz scala wszystkie oceniane pary różnych referencji; MWS 0/204 | Duże przypisanie może oznaczać błędną jedną domenę. Uczenie grafu samo nie usuwa problemu definicji sąsiedztwa i granicy. |
| [24a: kontekst grafu](graph-context-boundary-trial.md) | Bez treningu usunięto sztuczny podział jednej sieci: 121/121 centrów w jednej domenie; rzeczywiste granice nadal nie przechodzą kryteriów | Część błędu była konstrukcją kontekstu przy brzegu, a nie brakiem treningu. Naprawa tego błędu nie rozwiązała granic. |
| [25: maskowane AE](masked-autoencoder-trial.md) | Około 58,8% mniejszy błąd zakrytych pikseli; F1 czterech głównych granic 0 także przed odmowami | Rekonstrukcja może znacząco poprawiać się bez przydatnego sygnału podziału. |
| [26: adaptacja DINOv2](pretrained-self-supervised-trial.md) | 6 fitów; zmienne cechy bez zapadnięcia do stałej; brak wymaganej przewagi nad zamrożonym DINO; F1 głównych granic 0 przed odmowami | Ograniczona adaptacja ostatniego bloku z odczytem `mean384` nie poprawiła całej metody. Nie jest to test wszystkich gęstych odczytów ani pełnego treningu DINO. |

**0/174 nie znaczy „wykrywamy 0% molekuł”.** To przypisanie miejsc siatki
w ograniczonym zakresie częściowych referencji po odmowach. Wyniku 204 centrów
z 24 nie wolno porównywać jako tej samej czułości z 174 lub 782 miejscami siatki.
W 22 zachowana bramka ze spójnością już ograniczała końcowe przypisanie do
0/174 w transferze i 4/782 w transdukcji. Zatem sama wymiana enkodera nie mogła
podnieść tych liczb przy niezmienionej bramce. Jednocześnie niepowodzenia
**przed** bramką pokazują, że nie jest ona jedynym problemem.
[Raport 22](local-self-supervised-trial.md), [raport 26](pretrained-self-supervised-trial.md).

Przewaga DINO nad FFT w części miar istniała przed adaptacją: w transferze/MWS
fragmentacja wynosiła około 28,59% dla oryginalnego DINO i 27,73% po adaptacji,
przy 77,55% dla FFT. To argument za zachowaniem gotowych cech jako bazy,
ale nie za ogłoszeniem skutecznego detektora. [Raport 26](pretrained-self-supervised-trial.md).

## 2. Co ogranicza interpretację i czego nie powtarzać

Obecne TTMAPP pochodzi z jednej akwizycji. Klatki, ramki i rodziny syntetyków
były już wielokrotnie oglądane. Nowe ziarno znanego generatora nie tworzy
niezależnego sprawdzianu generalizacji na inną molekułę lub podłoże.
Przy transferze 174 miejsca rozkładają się BLACK/RED/YELLOW jako 172/2/0;
jest tylko 28 par różnych referencji i jedna lokalna krawędź między nimi.
W transdukcji 782 miejsca to 671/9/102 i 17 takich krawędzi. Dlatego obecne
wyniki słabo rozstrzygają skuteczność lokalizacji rzeczywistych granic STM.
[Liczebności w porównaniu 23](training-comparison-and-next-step.md),
[raport 26](pretrained-self-supervised-trial.md),
[audyt referencji](partial-domain-reference-audit.md).

Nie wracamy do hipotezy „PCA usunęło informację”. [Diagnoza cech z 19](feature-separation-trial.md)
wykazała rozróżnialność czystych wnętrz przez uśrednione FCN/DINO i niewielki
wpływ PCA. [Próba lokalnego grafu](local-feature-graph-trial.md) pokazała,
że to inne pytanie niż odczyt granicy: dla obrotu 8° AUC DINO na siatce
spadło z 1,000 dla wnętrz do 0,760 dla lokalnych krawędzi, a FCN do 0,543.
Nie dowiedziono, że samo uśrednianie jest przyczyną porażki. Niewykonany
pozostaje konkretny odczyt przestrzennego pola cech przy granicy.

**Prosta faza obrazu też była już testowana.** [Ticket 12](phase-boundaries-trial.md)
używał demodulacji dwoma wektorami, filtrów Gaussa i zawiniętych różnic faz.
Miał fałszywe cięcia po odwróceniu kontrastu, wielokrotne wskazania i pomijane
granice; dwa piki przyjęto tylko w 7/54 wnętrz TTMAPP. Polecanie zwykłego
lock-in jako zupełnie nowego kierunku powtarzałoby wykonaną próbę.

Również geometria była szeroko badana: [faza i tolerancyjne dopasowanie](tolerant-fit-phase-trial.md),
[wiele baz](basis-candidates-trial.md), [motyw i kompletność](motif-completeness-trial.md)
oraz [diagnoza jakości dopasowania](fit-quality-diagnosis.md).
Nowy kierunek musi zmienić konkretny brak informacji lub sposób jej odczytu.
Kolejne progi dla tych samych dopasowań nie stanowią nowego uzasadnienia.

## 3. Co wnosi literatura i dostępny kod

### A. Przestrzenne cechy gotowego modelu: ograniczona próba przed nowym modelem

Pierwszy kandydat to **już dostępny DINOv2 z zachowaniem tokenów**, zamiast
jednego uśrednionego wektora okna. Proponowany odczyt porównywałby ustalone
pasy lub pary tokenów po obu stronach lokalnej kandydatki na granicę,
z parami o tym samym dystansie i kierunku wewnątrz pasów. Położenia i kierunki
kandydatów muszą wynikać z ustalonej procedury, nie z referencji testowej.
Warstwy i parametry wybieramy przed jej oceną. Odczyt wzdłuż znanej granicy
byłby tylko diagnozą rozróżnialności, nie dowodem jej lokalizacji. Token ma położenie,
ale przez attention jego informacja zależy także od dalszego kontekstu:
trzeba jawnie zachować wsparcie i sposób kafelkowania. Jest to hipoteza,
nie opublikowany wynik STM. Uzasadnienie lokalne: takie przestrzenne porównanie
nie zostało wykonane w 19 ani 26; powtarzanie samego AUC wnętrz niczego nie doda.
[Zakres pierwszego badania 19](frozen-feature-domains-trial.md), [zakres 26](pretrained-self-supervised-trial.md).

DINOv3 rozwija jakość gęstych cech, m.in. przez Gram anchoring; ma publiczny
kod i różne rozmiary modeli. FeatUp uczy zwiększania rozdzielczości cech i ma
gotowy wariant dla DINOv2. Są sensownymi **warunkowymi** porównaniami, jeśli
diagnoza wykaże ograniczenie rozdzielczości lub jakości map. Żadna z tych
prac nie potwierdza detekcji domen molekularnych STM. Wyższa rozdzielczość
mapy nie jest dodatkowym niezależnym pomiarem struktury.
[DINOv3 — praca](https://arxiv.org/abs/2508.10104),
[kod i warunki wag](https://github.com/facebookresearch/dinov3),
[FeatUp — praca](https://arxiv.org/abs/2403.10516),
[kod FeatUp](https://github.com/mhamilton723/FeatUp).

Wynik DINOv3 „bez dostrajania” enkodera nie oznacza, że pokazane zadania
segmentacji nie uczą głowic z etykietami. Jego patch 16 nie jest drobniejszy
od patch 14 DINOv2. W FeatUp próba bez nowego treningu dotyczyłaby gotowego
JBU, nie wariantu dopasowywanego osobno do obrazu; bazą musi być też zwykła
interpolacja. Oficjalny FeatUp ma ekstraktor `dinov2_vits14`, zgodny z rodziną
używaną w 19/26. [DINOv3 — eksperymenty](https://arxiv.org/html/2508.10104v1),
[FeatUp — warianty i wagi](https://github.com/mhamilton723/FeatUp),
[ekstraktor FeatUp](https://github.com/mhamilton723/FeatUp/blob/main/featup/featurizers/util.py).

### B. Pola periodyczności: kandydat do pomiaru, nie gotowa segmentacja

Praca Lee i in. używa przestrzennego lock-in do map amplitudy i fazy CDW
po obu stronach granicy bliźniaczej w **STM GdTe₃**. Pokazuje użyteczność
zespolonego pola dla konkretnego układu z rozpoznanymi wektorami modulacji.
Nie dowodzi ogólnego wykrywania domen molekularnych ani nie unieważnia
negatywnego wyniku naszego 12. [Publikacja i metody](https://arxiv.org/html/2312.08986v1),
[Nano Letters 2023](https://doi.org/10.1021/acs.nanolett.3c03721).

Yang, Lu i Ying wyznaczają lokalne wektory falowe, orientację, deformację
i defekty transformacjami synchrosqueezed. Mają przykłady syntetyczne i obrazy
kryształów; kod SynLab obejmuje MATLAB/MEX i przykłady analizy kryształów.
To uzasadnienie alternatywnego estymatora lokalnej periodyczności, nie dowód
transferu na TTMAPP. SynCrystal **był już wymieniony**, ale nie był wykonany
w [wcześniejszym przeglądzie](research-domain-discovery-and-object-clustering.md).
[Praca](https://doi.org/10.1137/140955872),
[PDF autorów](https://web.stanford.edu/~lexing/crystalSS.pdf),
[SynLab](https://github.com/HaizhaoYang/SynLab).

Nowszy LWM bezpośrednio szacuje lokalne wektory falowe z transformacji Hougha,
po wybraniu i odfiltrowaniu składowej widmowej; omija potrzebę globalnego
rozwijania fazy do pomiaru lokalnego gradientu. Autorzy pokazują syntetyki
i STM NbSe₂. To **preprint z 7 października 2026**, z publicznym kodem Python
i przykładowym notebookiem. Nadal wymaga wyboru składowych i lokalnego
podparcia; nie daje automatycznie katalogu struktur ani masek domen.
[LWM — tekst](https://arxiv.org/html/2610.10255v1),
[kod autorów](https://github.com/jsntxyang/LocalWavevectorMeasurement).

Sens nowej próby tej rodziny byłby w **adaptacyjnym rozdzielaniu kilku
orientacji/częstotliwości i ocenie niepewności**, w porównaniu ze stałymi
dwoma wektorami z 12. Trzeba zachować amplitudę, fazę i rozstaw oraz osobno
sprawdzić zmianę kontrastu, harmoniczne i brak pełnej periodyczności 2D.
Sama zgodność kierunku nie odróżnia niezależnie przesuniętych rzędów od
spójnej sieci. To proponowana hipoteza; nie rekomendujemy ponownego uruchomienia
samego `phase_raw` z kolejnymi progami. Ze względu na historię 12/19 jest to
drugi, warunkowy kierunek, po diagnozie przestrzennego odczytu granic.

### C. Mały model uczony pod relacje: bardziej celny cel niż rekonstrukcja

MALIS uczy afiniczność pod wynik połączeń segmentacji, a nie pod odtwarzanie
obrazu. Mutex Watershed wykorzystuje atrakcyjne i odpychające relacje,
bez zadawania liczby segmentów. Opublikowane dowody pochodzą z segmentacji
mikroskopowej, m.in. obrazów biologicznych; nie są gotowym modelem STM.
Nowością względem naszych prób MWS byłoby **uczenie znaczenia relacji**,
zamiast zamiany odległości uśrednionych cech na wagi stałą regułą.
[MALIS](https://arxiv.org/abs/0911.5372),
[Mutex Watershed, ECCV 2018](https://www.ecva.net/papers/eccv_2018/papers_ECCV/html/Steffen_Wolf_The_Mutex_Watershed_ECCV_2018_paper.php).

Istnieje bezpośredni przykład uczenia na syntetykach i zastosowania do STM:
Seifert i in. wykrywają oraz klasyfikują chiralne komórki znanej sieci,
używając Faster R-CNN i YOLO trenowanych na generowanych obrazach.
To wąskie zadanie ze znanym układem i modelem generowania, nie odkrywanie
dowolnych domen. Uzasadnia próbę synthetic→real jako hipotezę, bez przenoszenia
ich dokładności do naszego problemu. [Publikacja 2024](https://doi.org/10.1002/smtd.202400549),
[pełny tekst](https://d-nb.info/1341517918/34).

ELIT pokazuje ważne ograniczenie na obrazach **STEM**: podobna jakość modeli
na syntetykach nie gwarantuje podobnego zachowania na pomiarze, a samo
uśrednienie ensemble nie rozwiązuje różnic rozkładu danych. Autorzy korzystają
z eksperckiej oceny poprawności predykcji przed iteracyjnym uczeniem na
pomiarach. To argument za audytem małej części rzeczywistych przykładów,
nie za automatycznym traktowaniem pseudoetykiet jako prawdy.
[ELIT — pełny tekst](https://arxiv.org/pdf/2101.08449).

Nasz proponowany model: mały CNN/U-Net lub mała głowica nad zamrożonymi
cechami, zwracająca relacje „razem / rozdzielić / brak podstaw”, ewentualnie
osobne pole uporządkowania. Model nie musi znać katalogu konkretnych domen
ani ich liczby. **Etykiety granic i regionów z generatora są nadzorem**,
nawet gdy ręcznie nie oznaczymy żadnego STM. Nie nazywamy takiej metody
beznadzorowanym odkrywaniem ani SSL tylko dlatego, że prawda jest syntetyczna.
Na początek wystarczy prosty cel uczenia relacji; pełny MALIS lub złożona
strata topologiczna nie są warunkiem próby. Wspólny obrót obrazu i etykiet
powinien obracać wynik. Wymuszanie identycznego opisu niezależnie obróconych
wycinków może usuwać różnicę orientacji potrzebną do zadania; to hipoteza
projektowa, nie wykazana już przyczyna negatywnego wyniku naszych prób.

## 4. Dwa warianty danych i ich konsekwencje

„Bez ręcznych etykiet” obejmuje dwa różne kontrakty: czyste uczenie bez
targetów domen oraz nadzorowany trening na targetach syntetycznych.
Tylko pierwszy spełnia ścisły warunek braku etykiet domen do uczenia.

| Kwestia | Bez ręcznych etykiet do uczenia | Małe ręczne oznaczenia |
| --- | --- | --- |
| Co można zrobić teraz | Odczyt gotowych map cech; analityczne pola; kontrola geometrii, skal i kontekstu | To samo oraz oznaczenie wybranych odcinków granic, wnętrz i obszarów niepewnych |
| Następny trening | Czysty SSL: bez targetów domen, tylko przy nowym uzasadnieniu celu. Osobny wariant: jawnie nadzorowany synthetic→real, bez ręcznych etykiet pomiaru | Mała głowica/CNN uczona na relacjach, możliwie wsparta syntetykami; znacznie prostsze sprawdzenie rozbieżności synthetic→real |
| Największe ryzyko | Generator lub analityczny model uznaje własne założenia za prawdę i nie odpowiada kontrastowi STM | Mały zbiór odzwierciedla jedną akwizycję; błędna lub niejednoznaczna granica staje się celem uczenia |
| Co oznacza brak wyniku | Brak wystarczającego dowodu w danych/modelu, nie automatycznie brak domeny | Niska pewność lub obszar bez etykiety, nie automatycznie negatywna klasa |
| Co da się uczciwie ocenić na obecnym MPP | Poprawność mechanizmu i wynik rozwojowy w tej akwizycji | To samo; ręczne etykiety nie tworzą niezależnej nowej akwizycji |

**Preferowany wariant, jeśli ręczne oznaczenia są wykonalne:** przed wyborem
metody wydzielić część rozwojową i ukrytą część testową. Część rozwojową
wykorzystać najpierw do diagnozy granic i błędów, a następnie ewentualnie
do małego treningu. Zbiór użyty już do wyboru metody jest rozwojowy,
nie staje się ponownie niezależnym testem. Same prostokątne wnętrza
nie zastępują konturów.
Nie trzeba od razu rysować całych masek każdej klatki: użyteczne są odcinki
pewnej granicy, pewne wnętrza, pary sąsiadów oraz jawna niepewność.
Próbki testowe muszą być oddzielone od wyboru parametrów i treningu.
W jednym MPP wymaga to m.in. buforów między blokami przestrzennymi i
przypisania powiązanych czasowo widoków tego samego miejsca do jednego zbioru.
Scribble lub para punktów nie jest pełną referencją konturu; oceniamy tylko
to, co rzeczywiście oznaczono. Jest to rekomendacja projektu, nie obietnica
ustalonej skuteczności przy określonej liczbie kliknięć.

Warstwa materiału, porządek 2D, orientacja, struktura i konkretna domena
pozostają odrębnymi pojęciami. Kontrastowa plama nie jest automatycznie
granicą domeny; wykrycie każdej molekuły również nie rozwiązuje podziału.
[Przyjęte definicje](issues/02-order-types-and-domains.md).

## 5. Proponowana kolejność i warunki zatrzymania

1. **Zamrozić pytanie o lokalną granicę i zakres oceny.** Zachować stare
   wyniki; oceniać granice orientacji, rozstawu i przesunięcia osobno.
   Kontrole jednej sieci, zmiany kontrastu, rzędów, braków centrów oraz
   ucięcia kadrem mają ujawniać fałszywy sygnał. Nie obniżać bramki tylko
   po to, by podnieść końcowy procent przypisania.
2. **Jedna ograniczona diagnoza bez treningu.** Porównać istniejący odczyt
   `mean384` z przestrzennym odczytem tokenów tego samego DINOv2, przy
   ustalonych warstwach, skali i kontekście. Sprawdzić lokalizację granicy,
   wnętrza, przesunięcie początku siatki i wspólne przesunięcie obrazu.
   Nie powtarzać badania samych czystych wnętrz/PCA. Niskie błędy uzyskane
   dzięki odmowie większości miejsc nie spełniają warunku korzyści.
3. **Oddzielić błąd sygnału od błędu podziału.** Na syntetykach można
   diagnostycznie podać idealne relacje do tego samego grafu/solvera:
   jeśli nadal nie odtwarza granicy, dalsze uczenie enkodera nie naprawia
   tej konstrukcji. Taki test z prawdą jest testem mechaniki, nigdy wynikiem
   skuteczności metody. Dobre relacje przed odmowami i niski wynik po nich
   wymagają osobnej przebudowy dowodu porządku, bez udawania rozwiązania.
4. **Jeżeli pojawi się wiarygodny sygnał, porównać dwa małe warianty:**
   model relacji z etykietami syntetycznymi oraz taki sam model z małą
   częścią ręcznych etykiet. Jeden ustalony cel i odczyt, kontrola bez
   treningu, ten sam budżet oraz jawne oddzielenie walidacji od testu.
   Jeśli problemem okaże się fizyczny pomiar periodyczności, alternatywą
   jest jedna próba SynLab/LWM przeciw bazie 12, nie jednoczesny przegląd
   kilkunastu nowych architektur.
5. **Dopiero po obiecującym wyniku wewnętrznym rozszerzyć dane.** Dodać
   niezależne pola/akwizycje z wiarygodną skalą i ustawieniami pomiaru;
   sprawdzić transfer bez dostrajania na ich ocenie. Utrzymać oba rodzaje
   błędów: scalenia i fragmentację, wraz z dostępnością oraz jakością granicy.

Warunek przejścia nie może być „loss spada” lub „kolorowe obszary wyglądają
dobrze”. Potrzebna jest powtarzalna poprawa lokalizacji rzeczywistej granicy
bez rozcinania jednej sieci i bez jej ukrywania odmową. Liczbowe kryteria
należy zapisać przed uruchomieniem nowej próby; obecne progi mogą pozostać
bazą porównania, lecz nie zastępują uzgodnienia tolerancji fizycznej.
Jeśli nowy odczyt nie wykazuje sygnału, zatrzymać wymianę modeli i wyjaśnić
brak: rozdzielczość, kontrast, definicja granicy lub niedostateczna referencja.
Negatywny wynik przestrzennego DINO dotyczyłby tego odczytu; nie dowodziłby
braku informacji w obrazie ani niemożliwości nauczenia innej reprezentacji.

## 6. Ile danych przygotowywać i czego teraz nie instalować

Nie ma uzasadnionej uniwersalnej liczby plików, klatek ani wycinków.
Ważniejsza jest różnorodność niezależnych pól i obecność ocenialnych granic
niż tysiące sąsiednich klatek tego samego układu. Potrzebne informacje to:
surowy obraz, rozmiary skanu i jednostki, identyfikacja molekuły/podłoża,
akwizycji i pola; jeśli dostępne, kanał, bias, prąd i kierunek skanu.
Znana skala w metadanych nowych MPP/STP jest zaletą; trzeba zweryfikować jej
odczyt i zgodność z eksportem. Historyczna kalibracja TTMAPP nie staje się
przez to automatycznie wiarygodna. [Audyt geometrii](import-geometry-audit.md).

Rozszerzanie danych powinno odpowiadać wykrytym błędom, a ilość oznaczeń
wynikać z krzywych uczenia i niepewności między akwizycjami. Nowe molekuły
i podłoża zwiększają zakres zadania; warto najpierw oddzielnie sprawdzić
nową akwizycję tego samego układu i transfer do innego układu.
Nie potrzeba przygotowywać całego archiwum, by wykonać powyższą diagnozę.

Pierwszy krok wykorzystuje istniejący DINOv2 i obecne dane; ten przegląd
nie uzasadnia instalacji kolejnego środowiska. SynLab wymaga MATLAB/MEX
według instrukcji autorów; zgodności z Octave nie sprawdzono. DINOv3 ma
własną licencję i procedurę uzyskania wag; dostępność repo nie oznacza
gotowych wag w naszym środowisku. LWM udostępnia kod badawczy Python,
ale nie sprawdzono jego uruchomienia lokalnie.
[SynLab — instalacja](https://github.com/HaizhaoYang/SynLab),
[DINOv3 — dostęp](https://github.com/facebookresearch/dinov3),
[LWM — repozytorium](https://github.com/jsntxyang/LocalWavevectorMeasurement).

Przegląd zweryfikował źródła i zakres ich dowodów. Nie reprodukowano prac
zewnętrznych, nie pobierano wag i nie potwierdzono jakości żadnej z propozycji
na TTMAPP. Wybranie dalszego eksperymentu jest odrębnym krokiem od tej syntezy.
