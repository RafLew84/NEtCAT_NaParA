# ML i deep learning bez własnego treningu do odkrywania domen

Data przeglądu: **2026-10-21**. Baza dokumentacji: `2a35377`.
Status: **przegląd źródeł i publicznego kodu; bez uruchamiania modeli na TTMAPP**.
Uzupełnia [badania STM/AFM](research-stm-afm-unsupervised-domain-discovery.md)
i [plan eksperymentów](unsupervised-domain-experiments.md).

## Odpowiedź i znaczenie „bez treningu”

**Możemy zastosować ML oraz gotowe sieci bez trenowania ich na obrazach
użytkownika.** Najbardziej uzasadniona próba to porównanie zamrożonych
deskryptorów obrazu z istniejącymi opisami geometrii i tekstury, a potem
grupowanie bez zadanej liczby klas. To kandydat do eksperymentu, nie
potwierdzona metoda wykrywania wszystkich rodzajów domen STM.

Nie mamy jeszcze wybranej metody produkcyjnej. Mamy kandydatów i warunki
ich oceny. Samo zastosowanie głębokiej sieci nie rozstrzyga, czy znaleziono
sieć molekularną, zmianę jasności, defekt końcówki czy granicę domeny.

| Wariant | Czy potrzebuje ręcznych przykładów domen? | Czy zmienia model na TTMAPP? |
| --- | --- | --- |
| Geometria/tekstura + nienadzorowane grupowanie | Nie | Dopasowuje grupy do danych, bez uczenia sieci |
| Gotowy, zamrożony DINO/CNN + grupowanie | Nie | Nie zmienia wag sieci; dopasowuje etap grupowania |
| Autoenkoder lub uczenie self-supervised na naszych obrazach | Nie | Tak, trenuje sieć na nieoznaczonych obrazach |
| Dopasowanie klasyfikatora do kilku zaznaczonych domen | Tak | Tak, albo używa przykładów jako wzorców |

Zamrożony model nadal był wcześniej trenowany przez autorów. W tym raporcie
„bez własnego treningu” oznacza brak optymalizacji wag sieci na TTMAPP,
w tym brak douczania małej głowicy klasyfikacyjnej. Dopasowanie PCA lub
HDBSCAN do nieoznaczonych cech pozostaje dozwoloną analizą nienadzorowaną;
nie należy przedstawiać jej jako procesu bez jakiegokolwiek dopasowania
statystycznego. To rozróżnienie odpowiada naszemu celowi: nie uczyć programu
kolorowych ramek ani z góry zakładać istnienia określonych domen.

## Kandydaci i siła dowodu

| Kandydat | Co rzeczywiście pokazano | Własny trening i ograniczenie |
| --- | --- | --- |
| **Wczesne cechy FCN–ResNet101** | Moduł 1 pracy Koleva: nienadzorowany podział rzeczywistych obrazów STM | Cechy gotowej sieci, bez nowego treningu tego modułu; końcowe k-means wymaga ręcznego `K`. Pełny proces zawiera już trening i few-shot learning. [Źródło, §3.2 i algorytm 2](https://arxiv.org/html/2506.01678v2) |
| **DINOv2** | Gotowe lokalne reprezentacje obrazów; benchmarki ogólnej wizji komputerowej | Można użyć zamrożonych wag bez własnych etykiet. Nie jest gotowym detektorem porządku ani zweryfikowanym przez nas rozwiązaniem domen STM. [Karta modelu](https://github.com/facebookresearch/dinov2/blob/main/MODEL_CARD.md) |
| **DINOv3** | Nowsze reprezentacje lokalne; autorzy poprawiają jakość gęstych map cech | Również dostępny bez fine-tuningu. Wyniki na zdjęciach i zobrazowaniach satelitarnych nie dowodzą skuteczności na molekularnym STM. [Publikacja](https://arxiv.org/abs/2508.10104), [karta modelu](https://github.com/facebookresearch/dinov3/blob/main/MODEL_CARD.md) |
| **FeatUp / AnyUp** | Zwiększanie rozdzielczości istniejących cech, nie samodzielne odkrywanie domen | Dostępne gotowe modele. W FeatUp trzeba odróżnić gotowy JBU od wariantu trenowanego na pojedynczym obrazie. [FeatUp](https://github.com/mhamilton723/FeatUp), [AnyUp](https://github.com/wimmerth/anyup) |
| **SAM 2 / μSAM** | Maski obiektów; μSAM specjalizuje modele dla mikroskopii biologicznej | Można używać istniejących wag. Automatyczny zbiór masek nie dowodzi rozpoznania sieci, jej typu ani orientacji. [SAM 2](https://github.com/facebookresearch/sam2), [μSAM](https://computational-cell-analytics.github.io/micro-sam/) |
| **AtomAI rVAE** | Nienadzorowany opis lokalnych obrazów z oddzieleniem obrotu/przesunięcia od zawartości | W opisanym użyciu wymaga treningu na zbiorze wycinków. To opcja bez etykiet, lecz nie bez własnego treningu. [Kod i przykład autorów](https://github.com/pycroscopy/atomai#variational-autoencoders-vae) |

### Bezpośredni precedens STM jest ważniejszy niż nazwa modelu

Kolev i współautorzy używają początkowych warstw gotowej FCN–ResNet101 do
opisania lokalnej tekstury STM. Autorzy pokazują m.in. różne orientacje
rekonstrukcji powierzchni. Jednak użytkownik zmienia liczbę grup, a dalsze
moduły trenują U-Net i klasyfikator korzystający z przykładów. Możemy
porównać **sam ekstraktor cech**, zastępując regułę grupowania zgodnie
z naszym protokołem. Wynik takiej modyfikacji będzie naszą adaptacją.
[Publikacja, §3.2–3.4 i dodatek](https://arxiv.org/html/2506.01678v2),
[kod autorów](https://github.com/nickkolev97/FSL_STM).

UniMR dla STM również deklaruje działanie bez własnego treningu,
wykorzystując m.in. gotowy CLIP oraz cechy pikselowe. Użytkownik wskazuje
jednak poszukiwane molekuły; to rozpoznawanie wybranego obiektu, nie
samodzielne odkrywanie nieznanych domen sieci. Nie uznajemy tego za
spełnienie obecnego wymagania.
[Publikacja UniMR, §2.2](https://doi.org/10.1002/advs.202516428).

Istnieje także bezpośredni precedens nienadzorowanej analizy domen w PFM,
technice wywodzącej się z AFM: Kalinin i współautorzy opisują geometrię
ścian domen ferroelektrycznych za pomocą VAE z rozdzieleniem obrotu.
To inny sygnał i inne znaczenie domeny niż sieć molekularna STM.
Przykład uzasadnia zainteresowanie autoenkoderem, ale nie dostarcza gotowego
modelu bez własnego treningu do naszego zadania.
[Publikacja autorów](https://arxiv.org/abs/2007.06194),
[przykład treningu rVAE w AtomAI](https://github.com/pycroscopy/atomai#variational-autoencoders-vae).

**APL-SAM** dotyczy bezpośrednio segmentacji SPM, lecz korzysta z
oznaczonych przykładów, trenowanych adapterów i uczenia promptów.
Wariant one-shot nadal wymaga przykładu wskazującego poszukiwany obszar.
Nie spełnia zatem naszego wymagania odkrywania domen bez przykładów;
brak ręcznego klikania podczas predykcji nie oznacza braku treningu.
[APL-SAM, metody III-A–III-C](https://arxiv.org/html/2410.12562v1).

Termin „mikroskopia” nie wystarcza do przeniesienia wyniku. μSAM ma modele
do komórek/jąder w mikroskopii świetlnej oraz organelli w mikroskopii
elektronowej. Praca Zenesis dotyczy FIB-SEM, wykorzystuje opis tekstowy
oraz GroundingDINO/SAM, a STM wymienia jako przyszłe rozszerzenie.
**SEM i STEM nie są STM**, a segmentacja komórek nie jest segmentacją
porządku molekularnego.
[Dokumentacja μSAM](https://computational-cell-analytics.github.io/micro-sam/),
[Zenesis, publikacja konferencyjna](https://doi.org/10.1145/3750720.3757283).

Nowszy **SAM 3** przyjmuje tekst lub przykłady wizualne i segmentuje
instancje wskazanego pojęcia; SAM 3.1 rozwija śledzenie obiektów. To nie
jest udokumentowana walidacja odkrywania sieci molekularnych w STM.
Nasza ocena: samo polecenie „znajdź domeny” nie zastępuje sprawdzenia,
czy maski odpowiadają uporządkowaniu i jego granicom.
[Oficjalny opis SAM 3 i aktualizacji 3.1](https://github.com/facebookresearch/sam3).

## Jak wykorzystać gotowe cechy bez uczenia domen

DINOv2 i DINOv3 zwracają wektory opisujące fragmenty obrazu. Do naszych
celów potrzebne są **lokalne cechy**, nie pojedynczy opis całej klatki ani
gotowy klasyfikator obiektów codziennych. DINOv2 ViT-S używa fragmentów
14 × 14 pikseli wejściowych; DINOv3 ViT-S — 16 × 16. Oba małe modele
mają około 21 mln parametrów. Karty modeli udostępniają większe warianty,
ale nie ma obecnie dowodu, że potrzebujemy ich do tej próby.
[Karta DINOv2](https://github.com/facebookresearch/dinov2/blob/main/MODEL_CARD.md),
[repozytorium DINOv3](https://github.com/facebookresearch/dinov3).

Nasza propozycja: pobierać cechy z regularnej siatki oraz z otoczeń
wszystkich poprawnych centrów molekuł. Porównywać kilka jawnie określonych
skal obejmujących sąsiadów. Nie skalować każdego otoczenia według jego
rozstawu, bo mogłoby to usunąć różnicę między typami sieci. Nie sprowadzać
całej klatki do miniatury przed analizą drobnej tekstury. Dopełnienie
wymagane przez model trzeba odróżnić od rzeczywistego pola pomiaru.

Podobieństwo cech trzeba następnie połączyć z przestrzenną łącznością
i niezależnym dowodem uporządkowania. HDBSCAN nie wymaga podania `K`,
ale wymaga parametrów skali grup; wariant jednej grupy należy jawnie
dopuścić. Nieprzypisanie punktu do klastra nie oznacza fizycznego braku
porządku, a znalezienie klastra nie wystarcza, by nazwać go domeną.
[Dokumentacja HDBSCAN](https://scikit-learn.org/stable/modules/generated/sklearn.cluster.HDBSCAN.html).

Nie zakładamy też, że DINO automatycznie oddziela typ sieci od orientacji.
To hipoteza do sprawdzenia na kontrolach: ten sam układ po obrocie powinien
zachować typ, podczas gdy granica orientacyjna może rozdzielać domeny.
Jawny pomiar orientacji z geometrii lub autokorelacji może być potrzebny
obok wektora sieci. Analogicznie granica przesunięcia wymaga osobnej oceny;
cechy użyteczne do rozpoznania podobnej tekstury mogą ją pomijać.

### Większa rozdzielczość cech nie jest nową informacją pomiarową

FeatUp oferuje gotowe modele JBU dla określonych ekstraktorów, m.in.
DINOv2. Alternatywny wariant implicit dopasowuje sieć do konkretnego
obrazu, więc nie spełnia wariantu bez własnego treningu. AnyUp udostępnia
model pozwalający zwiększać rozdzielczość różnych rodzajów cech bez
trenowania osobnego modelu dla każdego ekstraktora. To możliwe rozszerzenia
po zbadaniu map w ich natywnej rozdzielczości; nie są konieczne na start.
[Instrukcje FeatUp](https://github.com/mhamilton723/FeatUp#using-pretrained-upsamplers),
[publikacja AnyUp, ICLR 2026](https://openreview.net/pdf?id=Y9UAgPehqo).

Nasza ocena: gładki i szczegółowy obraz po zwiększeniu rozdzielczości
nie potwierdza dokładności granicy. Trzeba sprawdzić, czy wynik nie podąża
głównie za jasnymi krawędziami molekuł lub pasami skanowania. SAM może
wspomóc propozycje masek, lecz jego automatyczny generator pobiera siatkę
punktów i filtruje maski według jakości/stabilności; nie ocenia okresowości
sieci. Przy już dostarczonych oznaczeniach molekuł nie ma powodu uzależniać
pierwszej próby od ponownego wykrywania instancji.
[Kod generatora SAM 2](https://github.com/facebookresearch/sam2/blob/main/sam2/automatic_mask_generator.py).

## Małe porównanie w ramach istniejących kroków

To **propozycja rozszerzenia próby 17**, porównywana z niezmienioną bazą
geometryczną z kroku 15. Nie wybiera metody produkcyjnej.

1. W [kroku 17](issues/17-image-texture-domains.md) porównać obecną
   autokorelację/EWT z cechami początkowych warstw FCN–ResNet101 oraz
   zamrożonym DINOv2 ViT-S. DINOv3 ViT-S dodać jako dodatkowe porównanie,
   jeśli uzyskamy wagi; ich dostępność nie blokuje pozostałych prób.
2. Nadal w kroku 17 sprawdzić cechy obrazowe wokół dostarczonych centrów
   jako wariant obok regularnej siatki. Porównać go z geometrią sąsiedztwa
   z [kroku 15](issues/15-local-neighborhood-domains.md), zachowując jej
   niezależny wynik. Połączenie reprezentacji rozważyć dopiero, gdy wyniki
   pokażą ich uzupełniające się błędy.
3. Zachować wspólne wejście, kontrole i regułę budowania domen z
   [kroku 14](issues/14-unsupervised-input-and-controls.md). Porównanie
   powinno zmieniać reprezentację przy możliwie wspólnym grupowaniu,
   z zapisanym i ograniczonym zakresem parametrów. Nie wymagać identycznych
   liczbowych progów od cech o różnych skalach.

Analiza obejmuje całe poprawne pola klatek MPP; żaden ekstraktor nie
otrzymuje kolorowych ramek, ich liczby ani wycinków wybranych według domen.
Nie trenujemy sieci, nie dobieramy klasyfikatora na tych ramkach i nie
uzupełniamy nieoznaczonej części obrazu etykietą tła. Referencje odsłaniamy
po zapisaniu predykcji. Ponieważ wcześniej służyły już do badań, nie
przedstawiamy ich jako całkowicie niezależnego końcowego testu.

Rozstrzygające wyniki: zero domen na kontrolach bez porządku; jedna na
jednorodnej sieci; rozdzielenie orientacji i różnego rozstawu; zachowanie
rozłącznych obszarów; odporność na braki oznaczeń, kontrast i defekty;
jawna odmowa przy braku danych. Sprawdzamy również granicę przesunięcia,
stabilność między klatkami, czas i pamięć. Wysoki udział odmów nie może
ukrywać słabej detekcji. Ładna projekcja PCA nie jest miarą skuteczności.

## Kod, wagi i ograniczenia przeglądu

- **DINOv2:** publiczny kod i standardowe wagi na Apache-2.0; wariant
  `dinov2_vits14` jest bezpośrednio dostępny w oficjalnym loaderze.
  Nie przenosić automatycznie tej licencji na dodatkowe rodziny modeli
  dopisane do tego repozytorium.
  [README](https://github.com/facebookresearch/dinov2).
- **DINOv3:** publiczny kod, wagi przez opisany przez autorów formularz
  dostępu; własna DINOv3 License obejmuje kod i wagi.
  [Dostęp do modeli](https://github.com/facebookresearch/dinov3#pretrained-models),
  [licencja](https://github.com/facebookresearch/dinov3/blob/main/LICENSE.md).
- **FeatUp:** repozytorium MIT, linki do gotowych upsamplerów;
  **AnyUp:** repozytorium na CC-BY-4.0, gotowe wagi oraz opcjonalny
  wariant NATTEN. Licencje użytych ekstraktorów pozostają osobnym elementem.
  [FeatUp](https://github.com/mhamilton723/FeatUp),
  [AnyUp i wagi](https://github.com/wimmerth/anyup),
  [licencja AnyUp](https://github.com/wimmerth/anyup/blob/main/LICENSE).
- **SAM 2:** gotowe wagi, kod i modele Apache-2.0; **μSAM:** narzędzie
  MIT z modelami dostosowanymi przez autorów do zadań mikroskopowych.
  [SAM 2](https://github.com/facebookresearch/sam2#license),
  [μSAM](https://github.com/computational-cell-analytics/micro-sam).

Praktyczny koszt trzeba zmierzyć dla wielkości naszych obrazów. Początkowa
próba powinna używać małych modeli, ograniczonych partii wycinków i cache
cech. Sam rozmiar wag nie określa pamięci potrzebnej na duże mapy.
Zapisujemy model, wersję kodu, sumę kontrolną wag, normalizację i skale.
Nie instalowano bibliotek, nie pobierano wag i nie zmieniano środowiska
`netcat`. Nie sprawdzono jeszcze kompatybilności sprzętu ani jakości
predykcji. Nie znaleziono w sprawdzonych źródłach dowodu, że gotowy model
spełnia łącznie wszystkie nasze warunki wykrywania domen STM.
