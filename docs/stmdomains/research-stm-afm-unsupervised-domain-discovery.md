# Samodzielne wyszukiwanie domen: co pokazano w STM i AFM

Data przeglądu: **2026-10-21**. Baza dokumentacji: `53e5fb4`.
Status: **przegląd publikacji i publicznych implementacji; bez uruchomienia
nowych metod na TTMAPP**. Uzupełnienie
[przeglądu grupowania obiektów](research-domain-discovery-and-object-clustering.md).
Następny etap opisuje [plan eksperymentów](unsupervised-domain-experiments.md).

## Pytanie i odpowiedź

Użytkownik dostarczył obrazy i zapis z zaznaczonymi molekułami. Poszukiwane
rozwiązanie ma samodzielnie wskazywać istniejące domeny, bez podania ich
liczby, typów ani przykładów domen do nauczenia klasyfikatora. Oznaczenia
molekuł są wejściem. Kolorowe ramki domen pozostają wyłącznie częściową
referencją do późniejszej oceny. Nie oznaczamy pozostałego obrazu jako tła.

**Tak, istnieją badania nad nienadzorowaną analizą lokalnych struktur oraz
segmentacją domen w STM i AFM. W sprawdzonych źródłach nie znaleźliśmy jednak
gotowej metody, której walidacja obejmowałaby łącznie cały nasz zakres:**
nieznane typy sieci, nieznaną liczbę domen, możliwość niewykrycia żadnej,
niepełne oznaczenia molekuł oraz granice orientacyjne i przesunięcia.
To zakres ustalenia z tego przeglądu, a nie dowód, że takie rozwiązanie nie
istnieje nigdzie. Poniższe publikacje dają konkretne składniki i precedensy.

Kluczowe rozróżnienie: **brak ręcznych etykiet treningowych nie oznacza
braku narzuconej liczby grup**, a rozpoznanie lokalnego układu nie oznacza
wyznaczenia przestrzennej domeny. Liczba grup wyglądu lub faz materiału może
być inna niż liczba rozłącznych domen. Wnioski o przydatności dla STM Domains
są naszą oceną, oddzieloną poniżej od wyników autorów.

## Bezpośrednie precedensy STM i AFM

| Metoda i źródło | Wejście i rzeczywisty wynik | Nadzór i liczba grup | Znaczenie dla nas |
| --- | --- | --- | --- |
| [Bui i in., EWT, 2018/2019](https://arxiv.org/pdf/1804.08890) | Obraz STM monowarstwy CN/Au(111); osobna segmentacja jasności i tekstury | Brak ręcznie oznaczonego zbioru treningowego w wariancie k-means; liczbę grup wybiera użytkownik | Najbliższy obrazowy precedens segmentacji domen; wymaga zmiany sposobu wyboru grup |
| [Borodinov i in., 2020](https://doi.org/10.26434/chemrxiv.11542632.v1) | Molekularnie rozdzielcze AFM cieczy jonowych i melemu; orientacje, granice, statystyki | Nadzorowany wybór wzorców i kryteriów; FFT/PCA, inne deskryptory, progi lub k-means | Bardzo bliski temat, lecz oryginalny proces nie spełnia warunku samodzielnego odkrywania |
| [AiSurf, Corrias i in., 2023](https://cris.unibo.it/retrieve/handle/11585/957786/becc29d6-651e-4c91-bf89-ddb9ac837f9e/Corrias_2023_Mach._Learn.__Sci._Technol._4_015015.pdf) | AFM powierzchni krystalicznych; grupy cech, wektory sieci, komórka, deformacje | Bez zbioru treningowego; grupowanie hierarchiczne i wybór liczby grup przez silhouette w zadanym zakresie | Odkrywanie komórki bez katalogu symetrii, ale autorzy wyraźnie wyłączają rozróżnianie domen z zakresu tej wersji |
| [Paruchuri i in., 2024](https://pubs.rsc.org/en/content/articlehtml/2024/dd/d4dd00215f) | AFM mieszanin polimerów; dwie fazy tekstury i rozkłady rozmiarów | Nienadzorowane DFT/DCT + statystyki + k-means; w badaniu `K=2` | Gotowy kod obrazowego porównania; dwie fazy polimeru nie dowodzą odkrywania nieznanych domen sieci |
| [m2py, Tatum i in., 2020](https://par.nsf.gov/servlets/purl/10183757) | Wielokanałowe SPM polimerów; fazy materiałowe, następnie osobne obiekty | PCA/GMM bez etykiet przykładów, lecz liczbę faz określa użytkownik; liczba obiektów wynika z łączności lub watershed | Przydatne rozdzielenie podobieństwa i przestrzennych domen; inne cechy pomiarowe niż nasza sieć molekuł |
| [Laanait i in., 2016](https://link.springer.com/article/10.1186/s40679-016-0028-8) | Lokalne cechy atomów i sąsiedztwa; pokazano STM grafitu z defektami oraz STEM | SIFT i nienadzorowane grupowanie hierarchiczne, ocena podziałów przez silhouette | Ważny precedens grupowania otoczeń obiektów; nie kompletny detektor obszarów domen molekularnych |
| [Kolev i in., wersja 2026](https://arxiv.org/html/2506.01678v2) | STM Si, Ge, TiO₂; segmentacja i klasyfikacja defektów | Moduł nienadzorowany: cechy gotowej FCN–ResNet101 + k-means; człowiek zmienia `K`; pełny proces zawiera też uczenie i przykłady klas | Może dostarczać deskryptorów, ale pełnej metody nie przyjmujemy jako rozwiązania bez przykładów |

### Co dokładnie oferuje EWT

Bui i współautorzy rozdzielają obraz na składową jasności i teksturę.
Pierwszą segmentują wariantem Chan–Vese, drugą przez empiryczne falki 2D,
lokalne energie i grupowanie. Transformacja dobiera składowe widma z danych,
ale **liczba końcowych grup jest zadawana osobno przez użytkownika** (§5.3).
Wygładzający wariant MBO korzysta z części etykiet uzyskanych wcześniej
przez k-means; nie jest to trening na ręcznie wybranych domenach.
[Pełny tekst](https://arxiv.org/pdf/1804.08890).

Nasza adaptacja może zachować analizę tekstury i zastąpić ostatni etap
grupowaniem bez zadanego `K`. To już nowa kombinacja do sprawdzenia, nie
odtworzenie potwierdzonych wyników autorów. Sam level set odpowiada za
podział/wygładzenie przy zadanej informacji o regionach; nie zastępuje
rozpoznania lokalnej struktury. Dostępny
[pyewt autora transformacji](https://github.com/jegilles/pyewt) dostarcza
transformacji, nie pełnego gotowego programu do odkrywania domen STM.

### Dlaczego AFM dostarcza użytecznych przykładów, ale nie gotowego wyboru

Praca Borodinova jest szczególnie bliska naszym obrazom: dotyczy wzorów
molekularnych, rozstawu i orientacji. Autorzy jednak świadomie wprowadzają
wiedzę o układzie podczas wyboru wzorców, składowych i reguł przypisania.
Brak dużego zbioru treningowego nie usuwa tego nadzoru. Cennym składnikiem
jest przestrzeń lokalnych cech tekstury, nie gotowe klasy wybrane dla
konkretnego materiału.
[Tekst autorów](https://doi.org/10.26434/chemrxiv.11542632.v1),
[kod i dane](https://github.com/nickborodinov/multidomainprocessing).

U Paruchuriego bezpośrednio porównano kilka reprezentacji obrazów AFM;
DFT/DCT ze statystykami wariancji działały korzystnie dla badanego podziału
polimerów. Kod udostępnia parametr liczby klastrów `-NC`; przykład wywołania
ustawia go na `2`. Zastosowanie na TTMAPP wymaga więc nowego etapu wyboru
grup i walidacji cech. Nie przenosimy wyników ilościowych z polimerów na
molekuły STM.
[Publikacja, §2.3](https://pubs.rsc.org/en/content/articlehtml/2024/dd/d4dd00215f),
[repozytorium autorów](https://github.com/arthijayaraman-lab/Automated-Atomic-Force-Microscopy-Image-Analysis).

m2py najpierw rozróżnia materiałowe fazy na podstawie kanałów pomiaru,
następnie dzieli je na przestrzenne obiekty. W publikacji liczba faz GMM
jest wyborem użytkownika; przykładowo można założyć dwie czyste fazy
i jedną mieszaną. Watershed uwzględnia wybrany kanał, domyślnie wysokość,
a jego nadmierne dzielenie ogranicza próg trwałości. **Liczba obiektów
wynikająca z watershed nie jest automatycznie odkrytą liczbą typów sieci.**
[Publikacja, §2.2–2.3](https://par.nsf.gov/servlets/purl/10183757),
[m2py autorów](https://github.com/ponl/m2py).

### AiSurf: ważne ograniczenie mimo obiecującego tytułu

AiSurf wydobywa komórkę bez wcześniejszego wskazania symetrii. Jednak
§2 publikacji mówi wprost, że metoda nie została zaprojektowana do
rozróżniania różnych domen, a domeny translacyjne i obrotowe są traktowane
wspólnie. Ocena obejmuje eksperymentalne AFM wybranych tlenków oraz
symulowany obraz grafenu. To dobry kandydat do odtwarzania lokalnego wzorca,
nie dowód gotowego rozwiązania naszego zadania.
[Opublikowany tekst, §2 i wnioski](https://cris.unibo.it/retrieve/handle/11585/957786/becc29d6-651e-4c91-bf89-ddb9ac837f9e/Corrias_2023_Mach._Learn.__Sci._Technol._4_015015.pdf).

Publiczny notebook wymaga zakresów liczby grup i ustawień detekcji;
domyślne zakresy w README nie obejmują pojedynczej grupy. Trzeba osobno
sprawdzić przypadek jednej sieci i braku wiarygodnej struktury.
Rozszerzenie AiSurf do wzorów quasikrystalicznych dotyczy ich kafelkowania,
co również nie dowodzi ogólnego wyszukiwania domen dowolnej warstwy.
[Repozytorium AiSurf](https://github.com/QuantumMaterialsModelling/AiSurf-Automated-Identification-of-Surface-images),
[Kender i in.](https://arxiv.org/abs/2503.05472).

### Grupowanie zaznaczonych obiektów ma uzasadnienie w SPM

Laanait i współautorzy opisują obiekt przez lokalny punkt oraz gradienty
obrazu w jego otoczeniu, a potem grupują podobne deskryptory. W swojej
wersji celowo zachowują informację o orientacji. Przykład STM wyodrębnia
odmienne otoczenia przy defektach grafitu. To wspiera wykorzystanie naszych
oznaczeń jako punktów, wokół których pobieramy opis struktury, bez uczenia
klas z kolorowych ramek. Przeniesienie na molekuły i zbudowanie z tych
etykiet domen pozostaje naszą propozycją adaptacji.
[Publikacja, metody i przykład STM](https://link.springer.com/article/10.1186/s40679-016-0028-8).

W nowszej pracy Koleva moduł nienadzorowany startuje z `K=5`, a użytkownik
zmienia `K`, dopóki segmentacja go nie zadowala (algorytm 2). Pełny proces
klasyfikacji wymaga przykładów poszczególnych klas (algorytm 1).
Nie należy przedstawiać go jako autonomicznego odkrywania nieznanych domen.
[Pełny tekst, §11.2](https://arxiv.org/html/2506.01678v2).

## Rozwiązania o podobnych nazwach, ale innym celu

- **ASD-STM** odtwarza strukturę atomową pojedynczych molekuł przez modele
  uczone na obrazach symulowanych. Odkrywanie struktury chemicznej nie
  jest tutaj segmentacją domen warstwy.
  [Kurki i in., publikacja](https://pmc.ncbi.nlm.nih.gov/articles/PMC11064214/).
- **GMM dla wartości Z w STM** rozdziela poziomy sygnału. W pracy
  Cazzadoriego liczbę grup wybiera człowiek po oglądaniu segmentacji;
  nie analizuje to samo w sobie porządku i orientacji sieci.
  [Publikacja, §3.2](https://onlinelibrary.wiley.com/doi/full/10.1111/jmi.13426).
- **Benchmark grupowania AFM polimerów PHA** grupuje całe skany według
  ich cech i warunków, nie domeny wewnątrz obrazu. Nie jest walidacją
  lokalnego detektora domen.
  [Oryginalna publikacja](https://pmc.ncbi.nlm.nih.gov/articles/PMC11097174/).
- **Segmentacja lokalnych symetrii Wanga i in.** to interesujący
  nienadzorowany deskryptor, lecz pokazane wyniki pochodzą z mikroskopii
  elektronowej i wykorzystują k-means. Nie oznaczamy ich jako dowodu STM/AFM.
  [Publikacja autorów](https://pure.mpg.de/pubman/item/item_3349386).
- **SimuScan (2026)** usuwa konieczność ręcznego oznaczania dużego zbioru
  AFM przez generowanie obrazów i masek zadanych geometrii. Nadal trenuje
  modele detekcji/segmentacji; nie jest pokazem odkrywania nieznanych
  domen uporządkowania bez określenia poszukiwanych klas.
  [Publikacja](https://www.nature.com/articles/s41467-026-70421-3).

## Co z tego wynika dla naszych eksperymentów

Poniżej jest nasza synteza, nie wynik porównania na TTMAPP. Warto zachować
trzy niezależne drogi:

1. **Otoczenie zaznaczonych molekuł → podobieństwo → domeny.** Opisywać
   odległości, kąty i powtarzalność kilku otoczek sąsiadów, ewentualnie
   porównać z SOAP. Grupować bez gotowych klas, potem wymagać lokalnej
   spójności przestrzennej. Obrót zachować osobno od typu sieci.
2. **Lokalne obrazy → podobieństwo tekstury → domeny.** Porównać proste
   lokalne widmo/autokorelację z EWT. Oznaczenia molekuł mogą wyznaczać
   miejsca pomiaru cech; równoległa próba na regularnej siatce pokaże wpływ
   braków detekcji. Liczby grup nie pobierać z liczby kolorów referencji.
3. **Odkrywanie komórki z punktów.** SBC/MatID pozostaje kandydatem
   bez treningu i katalogu szablonów. Jego źródłowa walidacja dotyczy
   układów atomistycznych; nie znaleźliśmy potwierdzonego transferu do
   niepełnych oznaczeń molekuł STM. AiSurf może być dodatkowym porównaniem
   odzyskiwania komórki, ze świadomie uwzględnionym ograniczeniem domen.
   [SBC: publikacja autorów](https://www.nature.com/articles/s41524-024-01498-x).

HDBSCAN pozwala grupować cechy bez zadania `K`, lecz wymaga m.in. skali
minimalnej grupy i metryki. Wariant próby jednej domeny musi świadomie
dopuścić jeden klaster. Grupa stabilna według algorytmu nie dowodzi jeszcze
fizycznego uporządkowania: potrzebne są przypadki kontrolne bez domen,
badanie powtarzalności oraz jawny wynik „brak wystarczających danych”.
[Dokumentacja HDBSCAN](https://scikit-learn.org/stable/modules/generated/sklearn.cluster.HDBSCAN.html).

Próby mają działać na **pełnych klatkach** dostarczonej serii, ze wszystkimi
poprawnymi oznaczeniami, bez wycinania wejścia do znanych domen.
Ramki można odsłonić dopiero po uzyskaniu wyniku i wykorzystać do oceny
oznaczonej części. Nie należy dobierać liczby grup ani parametrów tak,
aby odtworzyć BLACK/RED/YELLOW. Są to głównie orientacje jednej sieci.
Wyniki poza ramkami pozostają propozycjami do oglądania, nie automatycznie
błędami. Obecne referencje wystarczą do pierwszego porównania.

Krytyczne kontrole to: obraz bez porządku, jedna jednorodna sieć, kilka
orientacji tej samej sieci, różny rozstaw, granica przesunięcia, izolowane
defekty, usuwane oznaczenia i zmiana kontrastu. Kolorowy podział każdego
obrazu nie stanowi sukcesu: trzeba pozwolić na **zero, jedną lub wiele
domen**, a także odmowę przypisania przy braku dowodów. Powierzchnie płatów
materiału wymagają oddzielnej oceny; nie uznajemy automatycznie otoczek
punktów za prawdziwą granicę warstwy.

## Zakres sprawdzenia

Przejrzano źródła pierwotne STM/AFM/SPM, teksty metod, założenia liczby
grup oraz publiczne repozytoria wskazane przez autorów. Nie traktowano
przeglądów, streszczeń marketingowych ani samych tytułów jako dowodu
spełnienia wymagań. Tam, gdzie strona wydawcy była niedostępna, użyto
autorskiego preprintu lub instytucjonalnej kopii. Kod bibliotek nie został
zainstalowany ani uruchomiony w ramach tego przeglądu. Nie wykonano nowej
walidacji danych ani GUI; nie wybrano metody produkcyjnej.
