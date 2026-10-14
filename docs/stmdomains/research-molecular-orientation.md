# Orientacja pojedynczej molekuły na obrazie STM

Data badania: **2026-10-14**. Status: **notatka badawcza, bez wyboru architektury**.
Wejście: obraz STM oraz centra lub bounding boxy molekuł z YOLO/ręcznych oznaczeń;
maski są opcjonalne. Badamy kąt w płaszczyźnie obrazu. Wykonano audyt wejścia,
ogląd wycinków i kontrolę anizotropii masek. Nie implementowano estymatora orientacji
w aplikacji ani nie oceniano skuteczności pomiaru kątów.

## Co można zmierzyć

**Znane centrum i bbox wystarczają do pobrania wycinka, ale sam bbox nie definiuje
orientacji molekuły.** Potrzebny jest kierunkowy szczegół obrazu: wydłużona oś,
układ płatków, wyróżnione ramię albo powtarzalny wzorzec. Bbox równoległy do osi
obrazu nie zawiera niezależnego pomiaru obrotu. Poniższe metody są kandydatami
do sprawdzenia; ich dobór zależy od widocznego motywu, nie od nazwy detektora.

Należy odróżnić **kąt wyglądu STM** od **kąta struktury chemicznej**. Grewal i in.
badali eksperymentalnie i teoretycznie PtPc na NaCl/Au: rozkład kątowy kontrastu
zmieniał się z warunkami obrazowania, a obraz LUMO wykazywał intensywność także
w kierunkach przekątnych, gdzie molekuła nie ma atomów. To konkretny kontrprzykład
dla utożsamiania każdego jasnego płatka z ramieniem chemicznym, nie wynik dotyczący
TTMAPP. [Grewal i in., ACS Nano, 29.04.2024](https://doi.org/10.1021/acsnano.3c12315),
[pełny tekst autorów](https://pmc.ncbi.nlm.nih.gov/articles/PMC11100283/).

Proponowany pierwszy cel: mierzyć obrót **wskazanego motywu obrazu** względem
ustalonego wzorca. Interpretacja chemiczna wymaga przypisania motywu do struktury,
np. przez referencję eksperymentalną lub symulację STM dla badanego układu i warunków.
Sam wzór chemiczny nie ustala takiego przypisania.

## Sprawdzone wejście TTMAPP i niewiadome

Audyt lokalnych plików z 2026-10-14:

- [detection_full.moltrack.json](../../data/TTMAPP/detection_full.moltrack.json),
  schema 1: 268 klatek roboczych, indeksy 0–267; 52 494 detekcje na 263 klatkach,
  w tym 49 226 YOLO i 3268 ręcznych. Detekcje mają identyfikatory, `frame_index`,
  osiowe `bbox_xyxy`, `confidence` i pochodzenie. Wszystkie są zapisane jako
  `expanded_aligned`; mediana rozmiaru bbox wynosi około 13,53 × 13,19 px.
- Powiązany [plik MPP](../../data/TTMAPP/MOVIE_23raw_TTMAPP_I_AU111.MPP) istnieje:
  zawiera 268 surowych klatek 256 × 256 px. JSON nie zastępuje ich sygnału.
- Jest 11 993 segmentacji SAM2, tylko dla klatek 0–39. Maski także są w układzie
  `expanded_aligned`, powiązane przez `prompt_detection_ids`. Nie każda detekcja
  ma maskę; poprawność masek nie została zwalidowana.
- `original_bbox_xyxy` **nie oznacza surowych współrzędnych**: kod transformuje
  zarówno bieżący, jak i oryginalny bbox do układu rozszerzonego. Powrót do obrazu
  raw wymaga odjęcia początku klatki, uwzględniającego padding i przesunięcie.
  Dla klatki 0 jest to `(224, 139)` px.
  [Transformacja detekcji](../../moltrack/core/registered_coordinates.py#L105),
  [wyrównywanie](../../nanotrack/registration/aligned.py).

Użytkownik potwierdził, że **nie ma jeszcze definicji orientacji**, a wartości
`1000 × 1000 nm`, bias 0 i current 0 w nagłówku są wartościami eksportu, nie
rzeczywistymi warunkami pomiaru. Nie ustalono stosunku skal X/Y ani odniesienia
do próbki/kryształu. Brak `Angle` w nagłówku; domyślne zero czytnika nie stanowi
pomiaru kąta skanu. [Czytnik MPP](../../napara/io/mpp_reader.py#L83).

**Roboczy cel dla tych danych:** orientacja widocznego motywu względem osi obrazu,
przy jawnym założeniu jednakowej skali pikseli X/Y. Bez potwierdzenia tej proporcji
nie jest to skalibrowany kąt fizyczny. Nie przypisujemy TTMAPP symetrii na podstawie
nazwy ani samych bboxów.

Klatka 0 ma 288 detekcji i 288 masek. Przy założeniu równych skal pikseli mediana
anizotropii drugich momentów masek wyniosła 0,240; 68 masek ma wynik poniżej 0,15,
czyli domyślnego progu obecnego estymatora maskowego MolTrack.
[Próg w kodzie](../../moltrack/analysis/molecular_orientation_mask.py#L36).
**To kontrola kształtu masek, nie ocena poprawności kątów**; przekroczenie progu
nie dowodzi poprawnej orientacji pozostałych molekuł. W 12 wycinkach 28 × 28 px
widać plamy kontrastu, częściowo wydłużone, pasy i sąsiadów. Ten ogląd nie ustala
symetrii ani jakości całego filmu.

Odtwarzalność: lokalny skrypt, raport i PNG są w ignorowanym przez Git katalogu
`.scratch/stmdomains/orientation-inspection/`. Wycinki wyświetlono bez wygładzania
i obrotu, z niezależnym zakresem percentylowym 2–98% każdego wycinka. SHA-256
wejściowego JSON:
`d0c4cb999bede28edb5dfd18ddbe146054711382f1c78363055be2330b3cdd2e`;
MPP: `8fbbfa5d515a90552c13cee2dbd289ff5cc16f000315547185c2a57bfe9f7c66`.

## Metody do krótkiego porównania

### Momenty i PCA — gdy istnieje wyraźna długa oś

Z maski obliczamy środek i macierz drugich momentów, a następnie kierunek większej
wariancji. Jest to oś bez zwrotu, czyli kąt modulo 180°. Oficjalne `regionprops`
definiuje orientację przez elipsę o tych samych drugich momentach; zwraca kąt
względem osi wierszy, co wymaga jawnego przeliczenia na przyjętą konwencję XY.
[Dokumentacja scikit-image](https://scikit-image.org/docs/stable/api/skimage.measure.html#skimage.measure.regionprops).

**Wniosek matematyczny:** przy równych wartościach własnych momentów oś nie jest
określona. Dotyczy to m.in. idealnie regularnego motywu trzy- lub czteropłatkowego,
choć jego obrót może być czytelny dla człowieka. Szum może wtedy wytworzyć pozorną
oś. Dlatego proponujemy kontrolę anizotropii `(λ₁−λ₂)/(λ₁+λ₂)` oraz stabilności
wobec zmian maski. PCA obwiedni pomija szczegóły wewnętrzne; wariant ważony
kontrastem wymaga zdefiniowania tła i wag, nie użycia dowolnych surowych wartości
wysokości jako masy. Żaden z wariantów nie daje automatycznie kąta wiązania.

### Obracany wzorzec i korelacja — gdy kształt jest powtarzalny

Proponowany eksperyment: porównać wycinek ze wzorcem obracanym przez cały zakres
kątów, używając znormalizowanej korelacji i ograniczonej korekty przesunięcia
centrum. Zachować pełną krzywą dopasowania, nie tylko zwycięski kąt. Oddzielne
wzorce mogą reprezentować różne wyglądy; muszą mieć wspólny kąt zerowy.

Alternatywa obliczeniowa to transformacja biegunowa wokół wspólnego środka:
obrót staje się przesunięciem wzdłuż osi kątowej. Oficjalny przykład scikit-image
pokazuje odzyskiwanie obrotu przez korelację fazową oraz błąd przy niewspólnym
centrum. Jest to demonstracja rejestracji obrazów, nie walidacja STM.
[Przykład autorów biblioteki](https://scikit-image.org/docs/stable/auto_examples/registration/plot_register_rotation.html).

Trzeba sprawdzić korektę centrum, wycięcie sąsiadów i warunki pozyskania wzorca.
Pobliska klatka tej samej molekuły nie jest niezależnym testem jakości.

### Profile biegunowe i harmoniczne — gdy motyw ma kilka ramion

Propozycja matematyczna: na wybranych pierścieniach wokół centrum wyznaczać
`cₘ(r) = Σφ I(r,φ) exp(i m φ)`. Dla idealnego obrotu o `α`, pomijając błędy
dyskretyzacji, w spójnej konwencji współrzędnych faza zmienia się o `mα`.
Nie wprowadzamy wag zależnych od kąta, które zaburzałyby tę własność.
Różnica faz względem
referencji daje zatem obrót modulo `360°/m`. Zachowujemy profil radialny i kilka
harmonicznych; zbyt wczesne uśrednienie promieni może usunąć przydatne szczegóły.

To proponowany deskryptor, a nie zweryfikowany estymator TTMAPP. Mała amplituda
oznacza niestabilną fazę; dominacja harmonicznej nie dowodzi chemicznej symetrii.
Należy sprawdzić centrowanie, promienie pierścieni, wpływ sąsiadów oraz zgodność
kątów uzyskanych z różnych części molekuły. Odwrócenie znaku kontrastu także
wymaga kontroli: zmienia fazę współczynnika i może wyglądać jak zmiana kąta.

### Uczenie — opcja dalsza

Ziatdinov i in. rozpoznawali stany obrotowe sumanenu na rzeczywistych obrazach STM,
korzystając z CNN, informacji o układzie i symulacji DFT. Wynik dotyczył ustalonych
klas obrotowych, nie uniwersalnego ciągłego kąta dowolnej molekuły.
[Ziatdinov, Maksov i Kalinin, 2017](https://doi.org/10.1038/s41524-017-0038-7).
Z kolei rVAE wydziela obrót i przesunięcie od pozostałych cech wycinka; przywołana
demonstracja dotyczyła obrazów STEM grafenu z krzemem, nie TTMAPP ani molekularnego
STM. [Kalinin i in., publikacja 2021, preprint 2020](https://arxiv.org/abs/2006.10267).

Uczenie pozostaje dalszą opcją: wymaga kalibracji zera, symetrii i walidacji.
Dobra rekonstrukcja wycinka nie dowodzi poprawnego kąta chemicznego.

## Minimalny kontrakt wejścia

Propozycja kontraktu eksperymentu; dostępne metadane należy odczytać automatycznie.

| Informacja | Do czego jest potrzebna |
| --- | --- |
| Obraz liczbowy i identyfikator klatki/kanału | Pobranie rzeczywistego sygnału; zapis przekształceń tła i kontrastu |
| ID obiektu, centrum lub bbox oraz konwencja współrzędnych | Pobranie wycinka; centrum można wyliczyć z bbox, rozmiar okna ustalić osobno |
| Układ `raw`/wyrównany, rozmiar obrazu, transformacja między układami | Zgodność obrazu i oznaczeń; przenoszenie kierunków wraz z pozycjami |
| Skala X/Y albo potwierdzenie izotropowych pikseli, obszar ważnych danych | Korekta geometrii i wykluczenie dopełnienia lub uciętych molekuł |
| Definicja mierzonego motywu oraz zero i zwrot kąta | Rozróżnienie osi, wyróżnionego ramienia i obrotu względem wzorca |
| Równoważne orientacje lub status „symetria do ustalenia” | Zakres kąta i uczciwe porównywanie wyników |
| Referencyjny wycinek albo ręczne wskazania kierunku na czytelnych przykładach | Kalibracja kąta oraz pierwsza ocena poprawności |

Maska może poprawić izolację molekuły, ale nie jest warunkiem metody obrazowej.
Napięcie, prąd zadany, tryb skanowania, kierunek skanu i informacje o zmianach
ostrza warto zachować jako warunki porównywalności, jeżeli są dostępne.
Kąt skanu lub kierunek sieci podłoża jest konieczny dopiero wtedy, gdy wynik ma być
odniesiony do tego układu; do kąta względem obrazu wystarcza jawna konwencja obrazu.
Przy transformacji zawierającej ścinanie nie wystarczy dodać jednego kąta rotacji:
trzeba przekształcić sam wektor kierunku.

W obecnym wejściu obraz i przeliczenie współrzędnych pikselowych są dostępne;
metryka X/Y pozostaje nieznana. **Do wspólnego ustalenia pozostają
widoczny motyw, jego odniesienie i rozróżnialność obrotów**; możemy zacząć od kilku
czytelnych przykładów, bez gotowej definicji chemicznej. Użytkownik nie musi
samodzielnie wybierać harmonicznej ani dostarczać katalogu domen. Przydatne będzie
potwierdzenie stosunku skal X/Y; tymczasowo zachowujemy jawne założenie izotropii.
Struktura chemiczna,
DFT i znany kierunek podłoża są dodatkowymi informacjami potrzebnymi przy przejściu
od wyglądu do interpretacji fizycznej, nie warunkiem rozpoczęcia prób.

## Symetria, niepewność i wynik

Proponowana konwencja: zero wzdłuż dodatniego X, dodatni obrót przeciwnie do ruchu
wskazówek zegara w skalibrowanym układzie z Y skierowanym w górę; przeliczenie
z indeksów obrazu zapisujemy jawnie. Dla osi bez zwrotu okres wynosi 180°, dla
trzech rzeczywiście nierozróżnialnych ramion 120°, dla czterech 90°. **Liczba jasnych
płatków sama nie rozstrzyga okresu**; trzeba uwzględnić cały wzorzec i rozdzielczość.
Jeżeli brak jakiegokolwiek rozróżnialnego kierunku, wynik powinien pozostać nieznany.

Równoważne maksima wynikające z symetrii są poprawnym wynikiem modulo symetria.
Kilka nierównoważnych dobrych dopasowań oznacza natomiast wieloznaczność. Odbicia
lustrzanego nie należy domyślnie utożsamiać z obrotem; może wymagać osobnego opisu.
Asymetria ostrza lub ucięcie wycinka nie powinny arbitralnie „wybierać” jednego
ramienia idealnie symetrycznej molekuły.

Wynik prób powinien zawierać kąt/zbiór kandydatów, okres symetrii, odniesienie,
metodę i wersję wzorca, miarę jakości oraz przyczynę braku wyniku. Szerokość piku
korelacji lub siła harmonicznej są diagnostyką, nie automatycznie skalibrowanym
prawdopodobieństwem poprawności. Pewność YOLO mierzy inne zadanie niż pewność kąta.
Rozróżniamy słaby sygnał, konflikt kandydatów, brak kierunkowego motywu i błąd
dopasowania centrum. Nie wnioskujemy z nich automatycznie o fizycznym nieporządku.

## Proponowana walidacja przed wyborem metody

1. Wybrać niewielki przekrój czytelnych i trudnych wycinków z różnych klatek
   i obszarów. Ustalić kierunek referencyjny, dopuszczalne symetrie i przypadki,
   w których człowiek również nie umie wiarygodnie określić orientacji.
2. Porównać PCA tam, gdzie istnieje długa oś, obracany wzorzec i profile biegunowe.
   Osobno ocenić wynik przy centrach poprawionych ręcznie i przy wejściowych
   centrach detektora. Oceniać na wycinkach nieużytych do wyboru wzorców/progów;
   dzielić po akwizycjach lub obszarach i odcinkach czasu, nie losowo po bliskich
   klatkach tej samej molekuły.
3. Sprawdzić sztuczne obroty czytelnych wycinków, przesunięcia centrów, szum,
   zmianę kontrastu, rozmiar okna, ucięcie i obecność sąsiada. To test odporności
   procedury, nie zastępstwo referencji na prawdziwych obrazach.
4. Mierzyć błąd kątowy modulo ustalony okres `P`:
   `d = abs(((θ_pred − θ_ref + P/2) mod P) − P/2)`.
   Raportować medianę i wysoki percentyl błędu wraz z odsetkiem przyjętych
   pomiarów oraz powodami odrzucenia. Nie poprawiać pozornie wyniku przez zmianę
   symetrii po obejrzeniu błędów.
5. Sprawdzić stabilność przy powtórnym oznaczaniu i przy zmianie warunków akwizycji.
   Zgodność z sąsiadami lub ciągłość czasowa mogą być dodatkową kontrolą, ale nie
   niezależną referencją: ich wymuszenie mogłoby ukryć prawdziwe różnice orientacji.

Dobór liczebności referencji i progów akceptacji pozostaje otwarty do pierwszego
oglądu danych. Dopiero taki pomiar pozwoli rozstrzygnąć, czy widoczny motyw TTMAPP
dostarcza użytecznej orientacji oraz czy potrzebujemy uczenia.
