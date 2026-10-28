# Jak poprawić rejestrację trudnych obrazów STM

Data przeglądu: 2026-10-28. Zakres: MOVIE_4 i MOVIE_8, bez wdrożenia nowej metody.
Wnioski z danych lokalnych: [rozpoznanie i reproduktory](registration-difficult-movies.md).
Poniżej rozdzielamy wyniki publikacji, lokalne obserwacje i propozycję dalszej pracy.
Nie zakładamy stałego kierunku ani monotonicznego przebiegu dryfu.

## Co wynika ze źródeł

1. **Sposób korelacji ma znaczenie przy silnym szumie.** Dokumentacja scikit-image
   wskazuje, że korelacja fazowa dobrze toleruje zmianę jasności, lecz przy dużym
   szumie korzystniejsza może być korelacja bez normalizacji fazowej. Wynik FFT
   jest niejednoznaczny modulo rozmiar obrazu; `disambiguate` ocenia kandydatów
   we wspólnym obszarze. Maski uruchamiają osobny wariant znormalizowanej korelacji,
   w którym `normalization` i `upsample_factor` nie są używane.
   [Dokumentacja phase_cross_correlation](https://scikit-image.org/docs/stable/api/skimage.registration.html#skimage.registration.phase_cross_correlation).

2. **Dopasowywanie deformacji może dopasować szum.** Zhang i współautorzy (2017)
   opisują STM z silnym szumem linii oraz oscylacjami przy szybkim skanowaniu.
   Zrezygnowali z wcześniejszej lokalnej rejestracji deformacyjnej, ponieważ
   dopasowywała się do szumu. Ich rozwiązanie łączy odpowiadające sobie linie
   forward/backward, korelację i dalsze filtrowanie. To wymaga takich skanów;
   nie możemy utożsamiać kolejnych klatek naszych filmów z trace/retrace.
   [Zhang et al., Scanning 2017](https://pmc.ncbi.nlm.nih.gov/articles/PMC5736918/).

3. **Korekcja uwzględniająca linie skanowania ma podstawy w SPM.** Ophus,
   Ciston i Nelson (2016) dopasowują początki linii na podstawie par skanowanych
   w kierunkach ortogonalnych. Repozytorium autora deklaruje także zastosowanie
   do większości szeregów czasowych, lecz nie obejmuje korekcji błędów wzdłuż
   kierunku szybkiego skanu. Autor wskazuje ryzyko dopasowania szumu przy zbyt
   małym uśrednianiu sąsiednich linii. To kandydat do zbadania, nie potwierdzona
   obsługa naszego tearingu przy nieznanym sposobie akwizycji.
   [Artykuł i abstrakt autora](https://escholarship.org/uc/item/58r1897p),
   [implementacja autora](https://github.com/cophus/scanning-drift-corr).

4. **Nowsza metoda STM wykorzystuje lokalną okresowość.** Jeon i współautorzy
   (2024) rekonstruują pole kierunków frontów falowych z lokalnych transformat
   Fouriera i prostują nieliniowe odkształcenia. Nie potrzebują wcześniejszej
   znajomości parametrów skanera ani pozycji poszczególnych atomów. Metoda dotyczy
   obrazów STM o rozdzielczości atomowej i strukturze opisywanej falami płaskimi.
   Nie jest dowodem, że dowolne domeny molekularne można bezstratnie „wyprostować”.
   [Jeon et al., Review of Scientific Instruments 2024 — ORNL](https://www.ornl.gov/publication/wavefront-distortion-correction-scanning-tunneling-microscope-image).

5. **Znana struktura może być wzorcem geometrycznym.** Yothers, Browder i Bumm
   (2017) wykorzystują wykryte atomy/molekuły i ich sąsiadów do dopasowania modelu
   dryfu, histerezy i pełzania piezoelementu. Punktem odniesienia jest znana
   struktura, a defekty i granice domen można wyłączyć maską. Dla naszego celu
   badania nieznanego uporządkowania jest to dodatkowe założenie wymagające
   uzasadnienia, a nie uniwersalny etap importu.
   [Yothers et al., Review of Scientific Instruments 2017](https://arxiv.org/abs/1611.00243).

To źródła STM/SPM. Wyników dla skaningowej transmisyjnej mikroskopii elektronowej
(STEM) nie traktujemy jako automatycznego potwierdzenia skuteczności w STM.

## Co wiemy o obecnym programie i danych

Wszystkie aktualne metody Viewera kończą obliczenie jednym XY na parę klatek.
Także Optical Flow redukuje pole ruchu do mediany. Jedno XY może przesunąć całą
klatkę, ale nie naprawi różnego przesunięcia jej górnej i dolnej części.
Źródło: [rejestracja Viewera](../../stmviewer/registration.py) i
[Optical Flow](../../nanotrack/registration/optical_flow.py).

Obecny [Tile+RANSAC](../../nanotrack/registration/tile_correlation.py) koreluje
wycinki w tych samych współrzędnych obu obrazów, domyślnie 32×32 px, bez
wstępnego globalnego XY. Rozszerzone poszukiwanie po zgrubnym dopasowaniu
byłoby zmianą tego podejścia. To potencjalne ograniczenie przy dużym
przemieszczeniu względem rozmiaru wycinka, nie dowiedziona przyczyna błędów.

Dla MOVIE_8 1→2 trzy niezależnie dopasowane fragmenty wskazują około (+14,0),
obecny Phase około (0,0), a wariant bez normalizacji (+13,55; +0,25).
Rozbieżność z lokalnym odniesieniem spada z 14,10 do 0,51 px. To jeden przypadek;
pełne przebiegi obu filmów nie stanowią niezależnej walidacji poprawności.
Proste testowane filtry nie pomogły w tej parze. Dane i zakres tych obserwacji
są opisane w [raporcie rozpoznania](registration-difficult-movies.md).

## Propozycja do sprawdzenia na obu filmach

Poniższe kroki są projektem eksperymentu, a nie sprawdzoną naprawą.

1. **Wyznaczyć obszary nadające się do dopasowania.** Zacząć od ręcznie wskazanych
   fragmentów stabilnych struktur i wykluczenia uszkodzonych pasów. Następnie
   zbadać automatyczne wykrywanie takich pasów. Nie maskować wszystkich silnych
   poziomych krawędzi: mogą należeć do próbki. Maska oznacza pominięcie danych
   w estymacji, bez wypełniania uszkodzeń sztucznym sygnałem.
2. **Oszacować globalne XY od dużych struktur do szczegółów.** Porównać korelację
   fazową, bez normalizacji i korelację z maskami. Wykorzystać piramidę skal,
   zweryfikować alternatywne maksima korelacji we wspólnym obszarze i dopiero
   potem doprecyzować przesunięcie. Na okresowym obrazie jeden wysoki pik może
   odpowiadać sąsiedniemu powtórzeniu wzoru, nie tej samej strukturze.
3. **Sprawdzić kilka oddzielnych fragmentów.** Szukać ich w rozszerzonym obszarze
   następnej klatki, z uwzględnieniem zgrubnego XY. Agregować zgodne dopasowania
   odpornie na odstające wyniki i wymagać przestrzennego pokrycia. Większość
   wycinków z tego samego uszkodzonego pasa nie jest niezależnym potwierdzeniem.
4. **Wykorzystać redundancję czasu.** Porównać A→B, B→C oraz A→C i zbadać
   zgodność ich złożeń. Dopuszczać zmienny kierunek dryfu; nie wymuszać gładkiej
   trajektorii jako kryterium poprawności. Niespójne dopasowania oznaczać jako
   niepewne. Test pętli również nie dowodzi poprawności: powtarzalna sieć może
   generować spójne, lecz przesunięte o okres dopasowania.
5. **Oddzielnie zbadać korekcję tearingu.** Jeśli po globalnym XY dobre fragmenty
   w różnych częściach klatki pozostają przesunięte względem siebie, rozważyć
   model pasów/linii skanu z ograniczoną liczbą stopni swobody. Swobodny warp
   całego obrazu może usunąć również rzeczywisty ruch molekuł i przemiany domen;
   to ryzyko projektowe, którego samo podobieństwo obrazów nie wyklucza.

Pierwszy prototyp powinien obejmować kroki 1–3 i ocenę na fragmentach innych niż
użyte do estymacji, w kilku trudnych i kilku łatwych parach obu filmów. Dodatkowo
warto użyć syntetycznych przesunięć znanego obrazu z dodanym szumem linii.
Porównywać błąd położenia struktur, liczbę niejednoznacznych par i czas pracy,
a nie wielkość aligned ani gładkość dryfu. Przetwarzanie pomocnicze służyłoby
wyłącznie estymacji; końcowy transform byłby nakładany na oryginalne dane.

Do modelu linii przydadzą się: kierunek szybkiego i wolnego skanu, czas linii,
czas klatki, dostępność trace/retrace oraz przykłady struktur uznanych za
nieruchome. Brak tych informacji nie blokuje prób globalnego XY w pikselach,
lecz ogranicza interpretację deformacji wewnątrz klatki.
