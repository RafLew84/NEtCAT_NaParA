# E5 — zamrożony protokół lokalności, skali i centrowania

2026-11-11, `ml_domain`, baza `8168349`. Zlecenie użytkownika: „wykonaj e5”.
Środowisko `netcat`. Protokół ustalony przed obliczeniem nowych cech i oceną
referencją. Materiał rozwojowy był już oglądany: nie jest to ślepy test.

## Pytanie i zakres

Czy kod całego okna traci lokalną informację, czy okno miesza struktury,
czy wynik zależy od umieszczenia wycinka? Trzy oddzielne kontrasty, bez
łączenia ich zwycięskich ustawień po wyniku. Jedna akwizycja oraz syntetyki;
okna, krawędzie i ziarna modelu nie są niezależnymi akwizycjami.

105 obrazów E2/E3: 24 STM i 81 syntetyków, siatka i rzeczywiste centra.
Transfer i transdukcja, istniejące AE/rVAE z32, po trzy ziarna 20261101–03.
Wyłącznie wybrane wcześniej checkpointy issue21. Bez treningu enkoderów,
nowych etykiet, zmiany normalizacji obrazu lub produkcyjnej aplikacji.
Odczyty: AE z32, pełne rVAE, treść rVAE oraz FFT. Mapa przestrzenna tylko
dla AE. Nie testować pełnej macierzy architektur ani ponownie fotometrii E3.

Wnioski z dostarczonego `data/temp` są motywacją kontroli dostępności,
nie nową prawdą domenową. Pomocnicze A/B nie stają się zatwierdzonymi klasami.
E5 nie ustanawia fizycznej kalibracji kąta rVAE.

## Trzy kontrasty

1. **Mapa AE:** wejście 48 px, ten sam encoder-pass i całe pole widzenia.
   Dotychczasowe z32 kontra pełne spłaszczenie mapy 64×7×7 = 3136 cech.
   Bez wyboru kanałów, cropu lub poolingu. Oba odczyty przechodzą przez
   tę samą regułę adaptera, do maksymalnie 24 wymiarów. Jest to zmiana
   odczytu reprezentacji, nie nowe gęste etykietowanie pikseli.
2. **Skala:** 48 jako baza, osobno 32 i 64 oraz jedno połączenie trzech
   opisów. Każdy blok z32/full/content/FFT jest normalizowany do L2=1;
   konkatenacja dzielona przez sqrt(3), potem zwykły adapter. Brak bloku
   oznacza brak całego opisu wieloskalowego; bez imputacji i bez dobierania
   skali do referencji. Mapy przestrzennej nie łączyć z tym kontrastem.
3. **Centrowanie:** skala48, te same źródłowe węzły i krawędzie, wycinek
   wokół oryginalnego centrum albo najbliższego punktu siatki 8+16k.
   Kontrola fazy siatki: najbliższy punkt 16+16k. Remisy do mniejszej
   współrzędnej, bez przycinania do brzegu. Na samplerze grid pierwszy
   snap powinien być tożsamościowy, drugi jest kontrolą przesunięcia siatki.
   Centra wpadające w ten sam punkt siatki nadal są oddzielnymi węzłami.

Pole recepcyjne jednej komórki mapy wynosi 15 px wejścia64, skok 8,
środki 7.5+8j. Pełna mapa obejmuje [0,63] na każdej osi; przy skali S
to 63S/64 pikseli odniesienia (w raw dodatkowo podzielone przez spacing).
Ostatni rząd/kolumna wejścia64 nie uczestniczą
w tej mapie. Pełny wymagany kontekst ekstrakcji pozostaje S+6; pole recepcyjne,
próbkowanie biliniowe i konserwatywny margines są różnymi wielkościami.

## Wsparcie, graf i dane treningowe adapterów

Rozmiary 32/48/64, siatka16 i margines3 są w pikselach odniesienia.
W STM spacing=1, więc odpowiadają surowym pikselom. W technicznie
przeskalowanych kontrolach, np. spacing=0.5, okno48 ma 96 surowych pikseli,
skok siatki32 i margines6. Zachować tę konwencję historycznego cache;
kontury w przeglądarce i footprinty referencji przeliczać tak samo.

Ekstrakcja jak wcześniej: surowy raster, skalowanie do64, interpolacja
biliniowa, zamrożony normalizer reżimu, bazowe clip[0,1]. Native FFT ma
odpowiednio 32/48/64 px, nie powstaje przez zmniejszenie wejścia64.
Bez paddingu, usuwania tła i normalizacji każdego okna osobno. Margines 3 px.
Snap tworzy nowy opis ekstrakcji; nie korzysta z historycznej augmentacji
shift_xy, ograniczonej do ±2 px. Źródłowe współrzędne molekuł pozostają
nieruchome przy budowie grafu, odczycie prawdy i rysowaniu przypisań.

Stały graf pełnej klatki z zapisu transdukcyjnego s48 FFT, identyczny dla
wszystkich warunków i obu reżimów. W transferze ograniczany do dozwolonych
węzłów. Nie estymować promienia sąsiedztwa ponownie po usunięciu miejsc.
To różnica wobec dawnego transferowego grafu zbudowanego na podzbiorze;
nie deklarować dokładnego replay dawnych podziałów transferu. Efekt E5
dotyczy parowanych wariantów wewnątrz tej próby.

Dla każdego wycinka przeliczyć dostępność obrazu oraz geometryczną
przynależność do dawnych pasów czasowo-przestrzennych wraz z guardem.
Większy lub przesunięty wycinek nie może odziedziczyć train/test tylko
dlatego, że jego bazowy wycinek48 tam należał. Rejestracja nadal ma niską
ufność; zachowujemy historyczną konwencję, nie dowód niezależności.

Każdy kontrast ma dwa jawne zakresy:

- **common:** przecięcie geometrycznego wsparcia i właściwego zakresu
  wszystkich warunków danego kontrastu, osobno map/scale/center. Nie
  przecięcie wszystkich eksperymentów lub rodzin cech. To główna ocena
  porównawcza przy tych samych miejscach. Brak poprawnej cechy nadal
  jest widoczny i nie usuwa miejsca z mianownika jakości.
- **own:** własna dostępność/zakres każdego warunku; pokazuje koszt
  kontekstu. Nie przedstawiać różnicy jakości przy innych mianownikach
  jako czystego efektu reprezentacji. Tabela podaje osobno wszystkie
  miejsca, dostępne wejścia, poprawne cechy i przypisania.

Nowe adaptery są konieczne dla nowych cech. Dopasować je przed oceną prawdą,
osobno dla reżimu, samplera, rodziny/ziarna, kontrastu i warunku. Reguła
pozostaje L2 → PCA do min(24, wymiar, N−1), bez whitening → mediana dodatnich
odległości krawędzi treningowych → q25/q75. Wszystkie warianty kontrastu
korzystają z tego samego przecięcia poprawnych treningowych opisów.
Początek to dawne samplerowe fit ID banku E2, z dodatkowym sprawdzeniem
wsparcia/splitu każdego nowego wycinka. Filtrować i przemapować istniejące
krawędzie treningowe, nie budować nowego grafu na mniejszej puli.
Brak dostatecznego fitu daje jawną niedostępność, nie dobieranie reguły.
Zachować ID, maszynerię adaptera i hashe; stare adaptery pozostają nietknięte.

## Podział, odmowy i ocena

FH k=4 i MWS z regułą relacji q25/q75. Pokazać propozycje przed odmowami
oraz H_M1 i A_fixed_M1. **Obie bramki pochodzą z bazowego native48**;
H zawiera stare wymagania skończoności, energii i ważności pomiaru, A także
ACF/widmo. Minimum 4 na siatce, 8 na centrach. Zachować ponowne obliczenie
spójności po usunięciach. Nie dobierać progów i nie tworzyć nowej bramki E5.

Na own32 mogą być nowe poprawne wejścia bez pomiaru bramki48. Pokazać
je w dostępności i propozycjach; po stałej bramce są odrzucone z jawnym
powodem `no_baseline48_gate`, a nie uznane za brak uporządkowania.
Wniosek o ewentualnym odzyskaniu takich domen wymagałby osobnej zmiany bramki.

Zamrozić cechy, adaptery i predykcje przed otwarciem referencji w przebiegu.
Oceniać stare syntetyczne instancje i częściowe wnętrza STM. Nie traktować
nieoznaczonego STM jako tła negatywnego. Jakość: pokrycie znanych wnętrz,
warunkowe scalenia/podziały par, fałszywe przypisania kontroli zerowych,
cięcia lokalnych krawędzi. Jawne liczniki/mianowniki i wyniki per ziarno.
Kontury pikselowe tylko tam, gdzie istnieje pełna syntetyczna referencja
i zgodny raster siatki; na centrach ocena krawędzi grafu. Tolerancja granicy
8 referencyjnych px, dotychczasowa konwencja spacing. Bez wymyślania
rzeczywistych granic na podstawie konserwatywnych wnętrz.

Po zamrożeniu dodać audyt zawartości okna: nominalny footprint i margines,
udział instancji w syntetyku, zawieranie w znanym wnętrzu STM oraz osobno
w eksploracyjnym ROI. Nie utożsamiać braku zawierania w ROI z przekroczeniem
prawdziwej granicy. W kontroli resample pole i margines przeliczać na raw
przez zapisany spacing. Szczególnie kontrolować jedną sieć, niezależne rzędy,
zmianę orientacji, przesunięcia, brzeg i brakujące molekuły. Obrys pojedynczej
molekuły nie staje się automatycznie granicą domeny.

Pomocnicze prostokąty z paczki `data/temp`: A=[64,24,176,104],
B=[218,58,250,126] w raw xyxy, wyłącznie klatki259–266. Raportować
zawieranie z marginesem0 i3, bez dopisywania z tych prostokątów etykiet.

Wyniki opisowe: osobno rodzaj obrazu, sampler, reżim, ziarno i zakres.
Nie liczyć istotności z tysięcy skorelowanych okien, nie wybierać ziarna.
Nie łączyć najlepszego odczytu/skali/snapu w dodatkowy detektor po wyniku.

## Wykonanie i odbiór

CPU jeden wątek, posterior mean/eval float32, bez treningu. Budżet 60 min
CPU, 8 GiB RSS, 16 GiB artefaktów. Kolejność grup losowana seed20261112,
zapisana. Osobny katalog `.scratch/ml-e5-20261111`. Nowe moduły <1000 linii.
Zapisać snapshot kodu/protokołu, wersje, wejścia, adaptery i audyty.
Świeże z32/full/content/FFT exact48 porównać z E2 tolerancją rtol1e−4,
atol1e−5; przekroczenie zatrzymuje próbę. Brak zmian źródeł lub wag.

Przeglądarka: para obrazów z centrami i domenami, wybór kontrastu/warunku,
common/own, bramki i metody. Kliknięcie pokazuje źródłową pozycję, centrum
ekstrakcji i obrys wsparcia. Brak wejścia, brak bazowej bramki i odmowa
strukturalna są różnymi stanami. Domyślnie TTMAPP259, centra/transdukcja,
AE20261101, mapa kontra z32, FH/common/H_M1. Identity musi dawać zgodność.
Techniczny test galerii i ogląd zrzutów osobno od odbioru użytkownika.

E5 może wykazać korzyść lokalności lub ograniczenie zamrożonych reprezentacji.
Bez zatwierdzonej małej referencji mocne wnioski o realnych granicach
pozostają niedostępne. Mały E7 nadal zależy od referencji i audytu grup;
E4/E6 warunkowe. Nie uruchamiać kolejnego etapu automatycznie.
