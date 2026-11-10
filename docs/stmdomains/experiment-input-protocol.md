# Wspólny protokół wejścia i wyników eksperymentów

Wersja 1, 2026-10-23. Realizacja [issue 14](issues/14-unsupervised-input-and-controls.md).
Kod przygotowania: `stmdomains.experiments`; to narzędzia badawcze, bez
zmian produkcyjnego importera lub wyboru algorytmu. Wynik wykonania i lokalne
artefakty opisuje [raport przygotowania](unsupervised-input-preparation.md).

## Rozdzielenie analizy od oceny

Generator publikuje nowy katalog dopiero po zakończeniu wszystkich etapów.
Istniejącego wyniku nie nadpisuje; kolejną próbę należy zapisać pod nową nazwą.

| Część pakietu | Zawartość i odbiorca |
| --- | --- |
| `analysis/manifest.json` i `analysis/samples/*.npz` | Jedyny pakiet przekazywany metodzie; obrazy, pole pomiarowe, bieżące oznaczenia i geometria |
| `evaluation/manifest.json`, `controls/`, `references/` | Osobny katalog oceny; nazwy kontroli, ziarna, prawda syntetyczna i częściowe referencje |
| `audit.json` | Pochodzenie, hashe wejścia/kodu, środowisko, zakres i ograniczenia |
| `index.html`, `preview/` | Lokalny podgląd pełnych pól, centrów i osobno włączanej prawdy odniesienia; nie jest wejściem metody |

Metoda używa `load_sample(analysis_dir, sample_id)` z modułu `bundle`.
Loader weryfikuje hashe, typy tablic i geometrię; odrzuca dodatkowe pola
takie jak etykiety domen. Nie przyjmuje ścieżki referencji. To rozdzielenie
interfejsu i plików, nie system uprawnień blokujący dowolny kod z dostępem
do całego dysku. Uruchamiający metodę przekazuje wyłącznie katalog analizy.

Referencje i mapę kontroli odsłaniamy po zapisie konfiguracji i predykcji.
Dotychczasowe ramki były już oglądane; nie stają się niezależnym testem
przez samo oddzielenie plików. Zmiany parametrów po ocenie tworzą nową
wersję rozwojową. Nie uczymy z ramek klas ani wymaganej liczby grup.

## Schemat wejścia `stmdomains-input-v1`

Każdy rekord ma stabilny `sample_id`, ścieżkę NPZ, SHA-256 pliku i hash
zawartości tablic. Hash zawartości obejmuje nazwy, dtype, shape i dane,
nie zależy od metadanych kompresji. NPZ odczytujemy bez pickle.

| Tablica | Znaczenie |
| --- | --- |
| `image[H,W]` | Wartości czytnika MPP z jego obrotem 180°, bez gamma i kontrastu podglądu; w kontroli obraz generatora |
| `measured[H,W]`, bool | Pole rzeczywistego pomiaru; w eksportowanych obrazach raw jest całe prawdziwe, bez płótna rejestracji |
| `centers_xy[N,2]` | Środki bieżących bboxów w polu pomiarowym |
| `boxes_xyxy[N,4]` | Bieżące bboxy po przeliczeniu do raw, bez przycinania przy brzegu |
| `object_ids[N]` | Identyfikatory oznaczeń; nie oznaczają śledzonych molekuł ani domen |

Pozycje opisują krawędzie pikseli: środek piksela `(row, column)` ma
`(x,y)=(column+0.5,row+0.5)`. Pole to `[0,W) × [0,H)`. Oznaczenie wchodzi
do analizy, gdy jego środek leży w polu; część bboxa może wychodzić poza nie.
Nie używamy historycznych bboxów, masek SAM ani dawnych wyników domen.

Dla TTMAPP rekord zawiera numer klatki od 1, indeks od 0, źródłowy indeks,
początek pola na płótnie wyrównanym oraz zapisany status/jakość rejestracji.
Przekształcenie to `expanded_xy = raw_xy + origin_in_expanded_xy`.
Własności fizyczne i czas wejścia są zastępcze: raportujemy px i numery
klatek, bez interpretowania zera czasu jako poprawnego interwału.

Kontrole mają anonimowe identyfikatory. Jednostką jest `reference_px`,
z jawnym `pixel_spacing_xy`: po technicznym powiększeniu ×2 wynosi 0.5.
Zmiana rzeczywistego rozstawu ma oddzielny przypadek. Powiązania kontroli
podstawowej z wariantami i przesunięcie przycięcia znajdują się wyłącznie
w pakiecie oceny.

## Zakres i kontrole

Pilot: 24 pełne klatki, numery 1, 50, 100, 150, 200 oraz 250–268.
Nie dobierano ich po obejrzeniu wyników metody. Numer 255 ma obraz i
oznaczenia, mimo braku ręcznej referencji. Braki detekcji w innych klatkach
nie stanowią prawdy o podłożu lub nieporządku.

Generator obejmuje 22 przypadki × 6 ziaren = 132 kontrole. Trzy ziarna
rozwojowe: 1701–1703; trzy do późniejszej oceny: 2701–2703. Ziarna oceny
zmieniają realizację losową, nie ustanawiają niezależnej akwizycji ani
nowej rodziny struktur. Można stroić na części rozwojowej, następnie zamrozić
konfigurację i osobno raportować wyniki na ziarnach oceny.

- Losowe punkty: jednorodne, z minimalnym odstępem i gradientem gęstości.
- Szum oraz pasy skanowania bez sieci molekularnej.
- Jedna regularna sieć, dwie orientacje wspólnego typu, dwa rozstawy,
  sieć skośna i większy rozstaw jednej sieci.
- Dwa rozłączne płaty, granica przesunięcia przy tym samym typie/kącie,
  pojedynczy defekt i pas nieuporządkowany.
- Ubytki 10/30/50% centrów oraz lokalna luka detekcji: obraz i prawda
  struktury pozostają identyczne jak w kontroli pełnych centrów.
- Zmienny/odwrócony kontrast, przycięcie pola oraz techniczne powiększenie ×2.

Obrazy syntetyczne powstają ze splatów centrów, gaussowskiego PSF i szumu.
To kontrolowane przykłady zachowania, nie symulacja fizyki STM. Nie
przypisujemy maski materiału na podstawie mapy domen. Ślady nieporządku
i brak molekuł mają ten sam brak domen, lecz różne obrazy/oznaczenia.
Rzeczywiste niepewne obrazy nadal mogą wymagać odmowy zamiast „nieporządku”.

Prawda syntetyczna zawiera mapy domen i typów, kąt/rozstaw tam, gdzie je
określono, oraz wyłączenie pasa 3 px wokół narzuconych granic. Na siatce ×2
pas ma 6 px. To jawna konwencja generatora, nie tolerancja realnych granic.
Sieć skośna ma zapisaną bazę; jej kąt i rozstaw skalarny pozostają nieokreślone.

Referencja TTMAPP zawiera `orientation_groups`, `region_instances`,
`evaluation_valid` i `boundary_unscored`. Zero oznacza brak etykiety,
nigdy pewne podłoże. Kolory oznaczają głównie orientacje tej samej sieci;
nie dają skalibrowanych kątów ani pełnej prawdy typów. Maski zachowują
algorytm i margines 3 px z wcześniejszego audytu; margines nie jest
zmierzoną niepewnością fizycznej granicy.

## Kontrakt wyniku `stmdomains-result-v1`

Każda próbka ma osobny plik JSON: `schema`, `sample_id`,
`input_content_sha256`, `run_id`, `catalogue_id`, `assignments`.
Katalog jest wspólny dla jawnie wybranego zakresu, nie nadawany od nowa
osobno każdej klatce. Identyfikator domeny dotyczy obszaru w klatce;
nie sugeruje śledzenia jej tożsamości w czasie.

Wiersz przypisania obejmuje:

- `element_id`: ID oznaczenia albo stabilny ID okna regularnej siatki;
- `xy`, `support_xyxy`: pozycja i rzeczywisty zakres obrazu użyty do cechy;
- `state`: `recognized`, `ordered_untyped`, `disordered`, `ambiguous`,
  `insufficient_data` lub `not_evaluated`;
- `reason`: jawny powód odmowy/niepewności; przy rozpoznaniu może być null;
- `type_id`, `domain_id`, `orientation_deg`: osobne wyniki; nieznane są null.

Zwracamy także elementy z odmową; usuwanie ich z tabeli zawyżyłoby jakość.
Wynik `recognized` wymaga typu i domeny. `ordered_untyped` zachowuje brak
typu. Nieporządek i stany niepewne nie dostają arbitralnego typu/domeny.
Walidator modułu `results` sprawdza podstawowy kontrakt i unikalność wierszy;
adapter metody dodatkowo sprawdza kompletność względem swoich elementów,
zgodność z polem pomiaru i poprawne oznaczenie niepełnego wsparcia przy brzegu.

Manifest uruchomienia musi zawierać: konfigurację i jej hash, źródło/wersję
kodu, zależności, ziarna, zakres, definicję katalogu, preprocessing, skale,
grupowanie, ocenę porządku, regułę łączenia oraz czas etapów, szczytowy RSS
i, jeśli użyto GPU, szczytowy VRAM. Zapisać metodę pomiaru; null oznacza
niezmierzone lub nieużywane, nie zero. Dla ML dochodzą źródło i hash wag,
architektura, warstwy/tokeny; dla treningu późniejszy manifest z kroku 20.
Wagi, dane i duże cechy pozostają poza Git.

Raster domen/stanów, jeśli powstaje, ma geometrię jawnie powiązaną z raw.
Otoczka centrów lub interpolacja cech nie staje się automatycznie konturem
płata. Konflikty i niepełne wsparcie należy zapisać, a nie rozstrzygać
przypadkową kolejnością etykiet. Produkcyjny zapis i statystyki zachowują
własne kontrakty; ten format służy porównaniu eksperymentów.

## Miary i podglądy porównania

1. **Kontrole:** liczba rozpoznanych domen, fałszywie przypisany porządek
   na znanym obszarze bez domen, błędy połączeń/podziałów oraz odsetek
   elementów dla każdego stanu. Mianowniki i wyłączone pasy podać jawnie.
   Liczbę domen pokazać wraz z odmowami; „0, bo odrzucono wszystko” nie
   przechodzi kontroli jednej regularnej sieci.
2. **Pary:** `pair_scores` liczy podziały par należących do tej samej
   referencji i scalenia par należących do różnych referencji. Stopy błędów
   są warunkowe względem przypisania obu elementów, dlatego obok zawsze
   jest udział przypisanych elementów we wszystkich ocenianych. Brak par
   daje null, nie wynik 0. Numery etykiet nie mają znaczenia.
3. **TTMAPP:** liczyć osobno relacje regionów przestrzennych i grup orientacji.
   W obrębie jednego regionu badać nadmierne dzielenie; sam ten sam kolor
   nie dowodzi jednej domeny w rozłączonych obszarach. Ocena wspólnego typu
   przy różnych orientacjach pozostaje hipotezą do omówienia. Nie liczyć
   dokładnych błędów kątów, globalnego IoU, całkowitej liczby domen ani
   fałszywych wykryć poza referencją.
4. **Stabilność:** porównywać relacje par i reprezentantów na wspólnych
   ID/pozycjach po zmianie zakresu, rozdzielczości i ubytkach centrów.
   Raportować także elementy bez odpowiednika; sama stabilność nie dowodzi
   uporządkowania. Dla braku detekcji obrazowa siatka pozostaje niezależna.
5. **Widoki:** pełna klatka bez nakładki, centra, wynik typu/orientacji,
   domeny, odmowy i osobno przełączana referencja. Wspólna tabela zawiera
   miary, pokrycie wynikiem, koszt i ograniczenia; nie tylko wybrane łatwe
   regiony lub projekcję cech do dwóch wymiarów.

Pierwsza próba kandydata obejmuje pilot i kontrole. Brak wariantu zdolnego
zachować jedną sieć bez uznawania szumu za porządek jest jawnym wynikiem
negatywnym. Dopiero zakwalifikowani kandydaci przechodzą do rozszerzenia
zakresu i pomiaru kosztu 268 klatek; polecenie `--full-series` przygotowuje
to wejście. Progi przyjęcia do programu ustalamy w 04/13. W issue 14 nie
powstał wynik żadnego detektora ani ranking metod.
