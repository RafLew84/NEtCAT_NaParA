# AE/rVAE — propozycja kolejnych eksperymentów

Data: **2026-11-10**. Gałąź: `ml_domain`, baza `dfac8e5`.
Status: **propozycja**, bez rozpoczęcia opisanych eksperymentów i bez nowych
ticketów wykonawczych. Właściciel decyzji: użytkownik. Środowisko: `netcat`.
Przy opracowaniu wykonano wyłącznie audyt źródeł i małą kontrolę inferencji
dwóch istniejących modeli tiny16, opisaną poniżej. Nie trenowano modeli.

## Pytanie i proponowana kolejność

Co ogranicza wynik AE/rVAE: informacja w wycinku, sposób jej kodowania,
odczyt podobieństwa, podział grafu czy odmowy po podziale? Najpierw chcemy
wyznaczać przestrzenne instancje domen; przypisywanie całych domen do klas
jest późniejszym zadaniem i nie wymaga teraz ustalenia K.

Rekomendacja: **E1 → E2 → E3**, czyli trzy próby bez nowego treningu.
Następnie **E4**, jeśli nadal chcemy rozwijać rVAE; **E5** sprawdza lokalność
i skalę informacji. **E6–E7 są warunkowe**, zależnie od diagnozy. Nie jest to
zlecenie wykonania całej macierzy ani wybór gotowego detektora.

Priorytety dobrano jakościowo według: zdolności rozróżnienia konkurencyjnych
wyjaśnień, kosztu, możliwości użycia istniejących danych oraz znaczenia
wyniku negatywnego. Nie stosowano punktowego rankingu hipotez.

## Co już wiemy

- [21](autoencoder-domains-trial.md): bramka dopuszcza 52/3456 pełnych okien
  transferowych TTMAPP. Przed odmowami FH nadmiernie scala, a MWS rozdrabnia.
  MWS i FH różnią się również interpretacją relacji; ich różnica nie izoluje
  samego solvera. Wynik 0/174 dotyczy częściowej referencji miejsc siatki,
  nie skuteczności wykrywania molekuł na całym obrazie.
- [21a](rvae-decoder-kl-trial.md): zmniejszenie KL i Fourier w dekoderze
  poprawiają część miar reprezentacji, ale nie końcowe domeny. Kąt pozostaje
  niewiarygodny. Rekonstrukcja nie jest miarą poprawności domen.
- Dekoder AE z32 ma 126 833 parametrów, a pierwotny dekoder rVAE tylko
  6465 (Fourier: 7745). Zbliżona liczba parametrów całych modeli maskuje
  różnicę ich rozkładu między enkoderem i dekoderem. To kandydat na
  ograniczenie, nie dowód jego przyczyny. [Architektury](../../stmdomains/experiments/training/models.py).
- Główny opis rVAE **już zawiera treść oraz sinus/cosinus kąta**, z równym
  ważeniem bloków. E2 bada ich wkład, nie proponuje dodania kąta jako nowości.
- Trening 21 **już usuwał sztucznie dodane zakłócenia fotometryczne**:
  zaszumione wejście miało czysty cel. „Dodać denoising” samo w sobie nie
  jest nowym eksperymentem. [Kod treningu](../../stmdomains/experiments/training/fit.py).
- Skale 32/48/64 px były testowane osobno. E5 dotyczy wspólnego odczytu
  wielu skal i przestrzennej mapy enkodera, a nie ponowienia starej tabeli.
- Zaledwie 28 par różnych referencji, w tym jedna lokalna krawędź w
  transferze, ogranicza ocenę rzeczywistych granic. Nowe syntetyczne ziarna
  nie zastępują niezależnych akwizycji. [Synteza wcześniejszych prób](research-after-training-pilot.md).

### Kontrola istniejących modeli podczas przygotowania propozycji

Odczytano dwa checkpointy tiny16 z kroku 2000, jednego ziarna treningowego.
Inferencja CPU w netcat, te same 16 wycinków, 8 losowań posteriora, seed
20261110. Dane, wagi i metadane starszych prób zachowały hashe.

| Model tiny16 | MSE dekodowania średniej | Średnie MSE 8 losowań | Mediana odchylenia treści posteriora |
| --- | ---: | ---: | ---: |
| beta=1e-3 | 0,0277572 | 0,0289363 | 0,991989 |
| beta=0 | 0,0216786 | 0,0216498 | 0,005365 |

Przy beta=0 różnica MSE wynosi około 0,13%. Losowość w końcowym
checkpointcie nie wyjaśnia więc głównej części jego rozmycia. Nie wyklucza
to wpływu losowania na wcześniejszą trajektorię treningu. MSE dla średniej
każdego wejścia wynosi 0,0429696, a dla osobno dopasowanej płaszczyzny
0,0344651: model odtwarza więcej niż te dwie proste bazy. Nie jest to dowód
odtworzenia molekuł lub granic. Oceniono tylko 16 wycinków, nie cały korpus.

Odtwarzalny skrypt i JSON z hashami, wersjami oraz parametrami:
`.scratch/ae-rvae-proposal-20261110/checkpoint_readout.py` i
`.scratch/ae-rvae-proposal-20261110/checkpoint-readout.json`.
To ograniczona diagnostyka istniejących wag, nie wynik E1–E7.

## E1 — gdzie znika domena: bramka i mechanika podziału

**Hipoteza:** znaczną część użytecznych przypisań usuwa konkretna składowa
odmowy. **Alternatywa:** odrzucany podział już wcześniej jest błędny.

- Zachować modele AE, rVAE i FFT, graf, wsparcie wycinków oraz algorytm
  podziału. Pokazać w każdym miejscu wszystkie przyczyny odrzucenia, a nie
  wyłącznie pierwszą. Oddzielić brak danych od niskiej oceny porządku.
- Wykonać **8 kombinacji włączenia/wyłączenia** trzech decyzji: próg ACF,
  dodatkowy filtr drugiego kierunku widma, minimum wielkości komponentu.
  Sam ACF już szuka dwóch niekolinearnych maksimów; wyłączenie filtra
  widmowego nie usuwa tego wymagania. Ważność danych, finite, dodatnia
  energia i kompletne wsparcie pozostają wymagane we wszystkich kombinacjach.
  Przeliczenie komponentów po usunięciu węzłów zachować jawnie i jednakowo.
  Raportować również interakcje: utrata węzłów zmienia wielkość komponentów.
- Osobno, tylko na syntetykach, zastąpić relacje grafu relacjami wynikającymi
  z prawdy generatora; osobno zastąpić maskę dopuszczenia maską miejsc
  należących do prawdziwych domen według generatora. Obecność materiału
  i support to odrębne informacje: niezależne rzędy zawierają materiał,
  lecz nie stanowią domeny 2D. To test mechaniki przy idealnym wejściu,
  **nie detektor**.
  Przypadki pozbawione odpowiednich krawędzi grafu raportować jako brak
  możliwości rozdzielenia tego efektu, nie naprawiać ukradkiem grafu.
  Tło kontroli bez domen nie może otrzymać jednej wspólnej „idealnej
  domeny”; obecność domeny to osobna maska od relacji między domenami.
- Uwzględnić jedną domenę, dwie orientacje, granicę przesunięcia, przerwę,
  szum, pasy i niezależne rzędy. Obecne GUI geometrii ma inne bramki;
  jego parametrów nie utożsamiać z bramką eksperymentu AE/rVAE.

**Odczyt:** pokrycie znanych wnętrz, błędne scalenia/podziały i domeny na
negatywnych kontrolach; oddzielnie przed odmowami, po bramce i po minimum.
Jeśli idealne relacje zawodzą, priorytetem jest graf/odczyt wyniku. Jeśli
pomaga tylko idealna maska, badać pomiar porządku. Jeśli wyłączenie bramki
jedynie zwiększa błędne przypisania, nie traktować go jako poprawy.
Koszt: **niski**, cache/CPU, bez treningu i nowych etykiet.

## E2 — czy użyteczna informacja jest w treści, kącie i odległościach

**Hipoteza:** niestabilny kąt lub sposób porównania cech osłabia przydatny
sygnał treści. **Alternatywa:** cechy nie rozróżniają rzeczywistych granic.

Porównać na tych samych wycinkach: AE, treść rVAE, obecne treść+kąt,
sam kąt jako diagnostykę oraz FFT. Zachować trening enkoderów zamrożony.
Dodać prostą bazę samych cech jasności/kontrastu, żeby mierzyć informację
wykraczającą poza te zmienne.
Dla zmienionego odczytu dopasować normalizację/adapter wyłącznie na dawnym
treningu; pokazać dystanse również przed adapterem. Kontrolę z tasowaniem
cech wykonywać wewnątrz jednorodnych grup testowych jako bazę braku sygnału,
nie źródło nowych etykiet lub kalibracji.

**Odczyt:** rozkłady odległości sąsiadów wewnątrz domen i przez granicę,
krzywe precision–recall i ROC dla dostępnych relacji, z liczebnościami
oraz oceną osobno według rodzaju granicy. Następnie te same odczyty przez
niezmieniony podział grafu. Nie utożsamiać łatwej separacji czystych wnętrz
z lokalizacją brzegu. Nie powtarzać ogólnej hipotezy o PCA na FCN/DINO,
którą wcześniej już oceniono.

Jeśli treść rVAE pomaga bez kąta, rozwijać ten odczyt bez deklaracji
fizycznego pomiaru orientacji. Jeśli AE pomaga bardziej, może pozostać
główną bazą. Brak sygnału na relacjach uzasadnia zmianę reprezentacji,
a nie szersze strojenie solvera. Koszt: **niski**, bez nowego treningu.

## E3 — czy model opisuje strukturę, czy warunki obrazowania

**Hipoteza:** niewielka zmiana tła/kontrastu zmienia cechy mocniej niż
zmiana struktury. **Alternatywa:** korelacja z jasnością nie odpowiada
za błąd lokalnych relacji lub jasność jest tu częścią rzeczywistej różnicy.

Zamrożone modele otrzymują pary tego samego wycinka ze zmianą offsetu,
gainu i osobno łagodnego gradientu. Zacząć od zakresów dotychczasowego
treningu: gain 0,9–1,1, offset ±0,1, sigma szumu 0–0,03 w jednostkach
znormalizowanego wejścia; zmiany gradientu określić z części train.
Zapisywać clipping i wspólne wsparcie, nie dodawać obrotu i fotometrii
jednocześnie w pojedynczym kontraście. Na syntetykach osobno zmieniać
orientację/rozstaw/przesunięcie struktury przy stałej fotometrii.

**Odczyt:** względna zmiana cech, relacji i przypisań; zgodność konturu
po transformacjach zachowujących strukturę. Zachować pełny obraz źródłowy,
ponieważ skok wysokości rzeczywistej warstwy nie jest automatycznie szumem.
Dominacja fotometrii uzasadnia pojedynczy wariant normalizacji w E6.
Stabilne cechy przy słabych domenach kierują uwagę ku relacjom/grafowi.
Koszt: **niski/średni**, nowa inferencja istniejących wag, bez treningu.

## E4 — co potrafi odtworzyć rVAE na 16 wycinkach

**Hipoteza:** ograniczenie leży w dekoderze współrzędnych lub optymalizacji
enkodera. **Alternatywy:** ograniczona informacja wejściowa, nieodpowiednia
strata albo wpływ stochastycznego treningu. KL nie jest jedynym kandydatem.

Użyć identycznych 16 wejść z 21a, bez augmentacji, beta=0. Proponowana
drabina ma najwyżej pięć konfiguracji, uruchamianych etapami:

1. AE z32 jako kontrola, czy dane i budżet pozwalają zapamiętać szczegóły.
2. Sam pierwotny dekoder współrzędnych 2×64, z osobno uczonym kodem każdego
   wycinka, bez enkodera, posteriora i uczenia pozy (kąt/przesunięcie = 0).
3. Ten sam test z jednym większym dekoderem 2×256 (około 75 tys. parametrów).
4. Warunkowo jeden wariant Fouriera w większym dekoderze, jeśli surowe
   współrzędne nie pozwolą odtworzyć szczegółów. Bez przeszukiwania pasm.
5. Jeśli któryś dekoder działa, dołączyć enkoder przy tej samej stałej
   pozie, bez KL i losowania. To sprawdzian uczenia kodu.

Limit: do 5 konfiguracji × 2 ziarna × 2000 kroków = **20 000 kroków**.
Te same batche, optimizer i jawna liczba parametrów. Samo deterministyczne
**dekodowanie** nie jest nowością — już służyło do walidacji 21/21a.
Nowy trening deterministyczny nie izoluje sam wpływu losowania bez
równoległego, identycznego wariantu stochastycznego; taki wniosek nie jest
celem tej drabiny. Porównanie Fourier obejmuje też zmianę wejścia dekodera.

MSE mierzyć razem z profilem rzędów, odtwarzaniem okresowości i błędem
przestrzennych gradientów, przy jednej skali jasności wejścia i rekonstrukcji.
Wykresy całej trajektorii, bez dobierania kroku według wyglądu domen.
To celowe zapamiętywanie, bez wniosku o transferze lub fizycznym kącie.

Jeśli sam dekoder odtwarza szczegóły, a cały model nie, szukać ograniczenia
enkodera/uczenia. Jeśli AE odtwarza, a oba dekodery współrzędnych nie,
ma sens przebudowa tej części. Niepowodzenie w skończonym budżecie nie
dowodzi matematycznej niemożliwości; nie zwiększać automatycznie budżetu.
Koszt: **kilka mikrotreningów**, bez dodatkowych obrazów i etykiet.

## E5 — lokalność, skala i położenie wycinka

**Hipoteza:** pojedynczy kod całego okna miesza dwie domeny i gubi miejsce
granicy. **Alternatywa:** cechy w ogóle nie opisują potrzebnej struktury.

Testować czynniki kolejno, nie zmieniać wszystkich jednocześnie:

1. Zamrożony AE: obecny z32 kontra jeden ustalony odczyt przestrzennej mapy
   enkodera 64×7×7, przy tej samej skali i kontekście. Regułę lokalizacji,
   receptive field i wymiar adaptera zamrozić przed oceną.
2. Obecny odczyt pojedynczej skali kontra połączenie osobnych opisów
   32/48/64 px. Nie dobierać najlepszej skali osobno dla każdej referencji.
3. Wykorzystać dotychczasową diagnostykę siatki i grafów centrów z 21.
   Nowy, izolowany kontrast centrowania: te same węzły rzeczywistych
   molekuł i te same krawędzie, lecz wycinek wycentrowany dokładnie na
   molekule albo przesunięty na najbliższy punkt ustalonej siatki. Ta sama
   skala, wspólne pełne wsparcie i jawne przesunięcia. To odróżnia wpływ
   centrowania od wcześniejszego porównania dwóch różnych grafów.

Uwzględnić przesunięcie siatki, brzegi, defekty i kontrolę jednej sieci,
żeby nie uznać obrysu każdej molekuły za granicę domeny. Pełne wsparcie
wszystkich porównywanych skal ma być wspólne albo jawnie rozdzielone.
**Odczyt:** lokalizacja granicy oraz fałszywe cięcia przy zachowaniu wnętrz.
Koszt: **średni**, inferencja/przygotowanie odczytu bez treningu enkodera.

## E6 — jeden nowy cel lub sposób przygotowania obrazu

Etap tylko po E3/E4. Nie uruchamiać szerokiej macierzy KL × z × decoder ×
loss. Wybrać jedną przyczynę do testu i zapisać ją przed treningiem:

- Jeśli E3 wykazuje dominację tła: dotychczasowa normalizacja kontra
  usuwanie lokalnej płaszczyzny, z zachowaniem jej parametrów i raw obrazu
  do kontroli. Nie stosować nowej normalizacji tylko podczas inferencji
  i nie nazywać takiego porównania równoważnym treningiem.
- Jeśli E4 pokazuje odtwarzanie tła przy utracie szczegółów: obecne MSE
  kontra MSE z jednym dodatkowym składnikiem gradientowym. Wagę ustalić
  na train, bez wyboru po wyniku domen; kontrolować wzmacnianie szumu.
  Sam moduł FFT nie zastępuje przestrzennego celu tracącego wtedy fazę.
- Jeśli problem dotyczy użycia pozy: warunkowo dopasować zgodność
  reprezentacji dla znanych transformacji. Kontrolować niejednoznaczną
  symetrię, orientację molekuły i sieci osobno; nie zakładać symetrii M6.

Każda wybrana para ma tę samą architekturę, dane i regułę wyboru kroku:
**2 warianty × 3 ziarna = maksymalnie 6 pełnych fitów** na jeden wybrany
kontrast. Dokładny budżet kroków/czasu zapisać w protokole wykonawczym.
Lepsza rekonstrukcja jest wynikiem częściowym; kontynuację uzasadnia
korzyść na relacjach i domenach. Denoising oraz słabsze KL były już badane.
Jeśli celem staje się izolacja mechanizmu rVAE, przygotować osobny kontrast:
AE kontra zwykłe VAE z tym samym dekoderem, a następnie coordinate VAE
bez pozy kontra rVAE z identycznym dekoderem. Dawne AE–rVAE zmieniało
równocześnie dekoder, wariacyjność, KL i pozę; nie izoluje wpływu obrotu.

## E7 — mały uczony odczyt relacji i późniejsza krzywa ilości danych

Warunkowo, jeśli E2/E5 pokazuje sygnał przy granicy. Przy tym samym grafie
i algorytmie podziału porównać ten sam mały klasyfikator otrzymujący:
**geometrię**, **geometrię+AE**, **geometrię+rVAE**. Enkodery pozostają
zamrożone; złożoność klasyfikatora i dobór parametrów mają ten sam budżet.
Osobno porównać klasyfikator z dotychczasową regułą odległości.

To uczenie nadzorowane relacją, bez konieczności nazw klas domen. Dodatnie
pary pochodzą z zatwierdzonych wnętrz, ujemne z zatwierdzonych styków;
niepewne i nieprzejrzane obszary są pomijane. Możliwe źródła: małe ręczne
korekty albo osobna próba synthetic→real. Prawda generatora w treningu
oznacza nadzór syntetyczny; nie przedstawiać jej jako uczenia bez etykiet.

Na początek przygotować niewielki, rozdzielony zbiór przejrzanych ROI;
liczbę i udział granic ustalić na podstawie inwentaryzacji, nie arbitralnego
minimum par. Dawne 174 miejsca nie tworzą nowego niezależnego testu.
Większą pulę MPP/STP dołączać po sprawdzeniu odczytu, skali i grup pomiarów.
Porównanie 25/50/100% grup train przy stałej walidacji pozwoli oszacować,
czy kolejne pomiary pomagają. Test końcowy pozostaje poza doborem danych.
[Walidacja grupowa](https://scikit-learn.org/stable/modules/cross_validation.html#cross-validation-iterators-for-grouped-data),
[krzywe uczenia](https://scikit-learn.org/stable/modules/learning_curve.html#learning-curve).

## Wspólny protokół i sposób pokazania wyników

- Zachować wagi, dane i raporty 21/21a; nowe artefakty w osobnym katalogu.
  Przed próbą sprawdzić hashe, identyfikatory wejść i netcat; adaptery,
  normalizację i progi dopasowywać tylko do odpowiedniego train.
- Jednostka oceny to pole/akwizycja i rodzaj kontrolowanej granicy. Okna,
  pary, sąsiednie klatki i ziarna modeli nie są niezależnymi akwizycjami.
  Całe grupy pomiarowe rozdzielać przed wycinaniem okien. Obecne TTMAPP
  i widziane syntetyki pozostają materiałem rozwojowym.
- Porównania sparowane na tych samych wejściach. Raportować wszystkie
  warianty i ziarna; główne kontrasty określić przed obliczeniami. Kolejność
  fitów przeplatać, jeśli porównujemy też koszt. Nie wybierać najlepszego
  wyniku według znanej częściowej referencji i nie nazywać jej testem.
- Mierzyć scalenia, podziały, pokrycie i błędne przypisania oddzielnie.
  Ocena par na wspólnym zbiorze dostępnych miejsc; odmowy raportować
  osobno. Błąd liczony tylko na zachowanych łatwych parach nie wystarcza.
  Kontury oceniać liczbowo na syntetykach lub dokładnych maskach; obecne
  przybliżone ramki nie umożliwiają pełnego boundary F1/IoU na STM.
- Kandydat do dalszej pracy: poprawa podziału przy zachowaniu pokrycia lub
  lepsze pokrycie bez wzrostu błędów; bez pogorszenia wcześniej zaliczonych
  negatywnych kontroli. Wyniki mieszane pozostają kompromisem do oceny,
  nie automatycznym sukcesem. Przy 0 przypisań miary wymagające par są
  niedostępne. Progi praktycznej poprawy i tolerancję granicy doprecyzować
  w wybranym protokole przed jego uruchomieniem, nie po obejrzeniu wyniku.
- Przeglądarka: ta sama klatka, zoom i skala; domeny na obrazie, rzeczywiste
  molekuły z przypisaniami, nieprzypisane szare. Przełączniki wariantu oraz
  przed/po odmowach; kliknięcie pokazuje powód. Wyniki siatki mają jawny
  osobny tryb. Projekcji siatki na centra nie przedstawiać jako źródłowej
  predykcji molekuł; przed użyciem określić regułę i jej niepewność.
  Kolory porównywanych domen stabilizować w obrębie porównania.

## Sprawdzone źródła, granice przeglądu i pochodzenie propozycji

Przegląd ograniczony, 2026-11-10: raporty/kod projektu oraz źródła
pierwotne o rVAE, denoising i rozdzielaniu czynników zmienności. Zapytania:
„Vincent Larochelle Bengio Manzagol 2008 Extracting Composing Robust
Features Denoising Autoencoders pdf” i „Locatello Challenging Common
Assumptions Unsupervised Disentangled Representations 2019 pmlr”; dodatkowo
bezpośredni odczyt poniższych stron. Nie jest to przegląd systematyczny
ani ustalenie nowości metod. Nie przesyłano obrazów lub wag na zewnątrz.

- [Valleti i in., rVAE w STEM](https://arxiv.org/abs/2101.06892): precedens
  oddzielania orientacji w innym typie obrazowania. Nie potwierdza jakości
  kąta w naszych danych ani potrzeby stosowania tej samej architektury.
- [Ziatdinov i Kalinin, j-trVAE](https://arxiv.org/abs/2104.10180): uzasadnia
  sprawdzanie modelu niezmienniczego w mikroskopii; nie gwarantuje domen.
- [Locatello i in., ICML 2019](https://proceedings.mlr.press/v97/locatello19a.html):
  rozdzielenie czynników bez założeń nie jest identyfikowalne; wymagana jest
  ocena konkretnej korzyści w zadaniu. Motywacja do E2/E7, nie dowód, że
  obecny rVAE musi zawieść.
- [Vincent i in., ICML 2008](https://doi.org/10.1145/1390156.1390294): podstawa
  uczenia odszumiania; ten ogólny mechanizm już występuje w naszym treningu.

Zastosowano `scientific-brainstorming`, `hypothesis-generation`,
`experimental-design`, `scientific-critical-thinking`: niezależne propozycje
dwóch analiz, konfrontacja z kodem/źródłami i osobny przegląd krytyczny.
To wsparcie AI, nie konsensus niezależnych eksperymentów. Przygotowanie
wykorzystuje procedury opisane przez Kassis, Agarwal, He, Patel i Brueckner
(2026), [Scientific Agent Skills: A Library of Procedural Knowledge for Research Agents](https://doi.org/10.48550/arXiv.2609.00065).
Metadane zweryfikowano 2026-11-10. Skille nie stanowią dowodu skuteczności
proponowanych metod. Ostateczny wybór prób pozostaje po stronie użytkownika.
