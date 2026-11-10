# Jak zapis wejściowy odtwarza obrazy, oznaczenia i rejestrację?

ID: 01
Type: grilling
Labels: wayfinder:grilling
Mode: HITL
Status: resolved
Assignee: Codex — domains/import-contract
Parent: [STM Domains — etap 1: działający szkielet](../map.md)
Blocked by:

## Question

Jak zdefiniować kontrakt importu gotowego zapisu, tak aby obraz, oznaczenia
molekuł i zapisana rejestracja opisywały te same klatki i współrzędne?

Punktem odniesienia jest podany zapis MolTrack. Ustalmy:

- wymagane i opcjonalne dane: obrazy lub ich odnośniki, identyfikatory i kolejność
  klatek, centra/bboxy, opcjonalne maski, rozmiary, transformacje i ich jakość;
- minimalny zestaw obsługiwanych zapisów MolTrack i dane przekazywane do
  podglądu, bez projektowania teraz formatu własnych wyników;
- odtwarzanie ścieżek po przeniesieniu danych między komputerami, sprawdzanie
  zgodności źródła oraz zachowanie przy brakującym lub niezgodnym obrazie;
- rozróżnienie orientacji macierzy w pliku, obrazu po imporcie i obrazu wyrównanego;
  `original_bbox_xyxy` nie jest automatycznie bboxem raw;
- zachowanie zapisanych przesunięć i oryginalnego pola klatki oraz obsługę braków
  lub niskiej jakości zapisanej rejestracji; szkielet jej ponownie nie oblicza;
- reprezentację brakujących czasów i kalibracji, pustej listy oznaczeń oraz braku
  danych o oznaczeniach — brak rekordu nie musi oznaczać braku molekuł.

Jaka minimalna próba otwarcia istniejącego zapisu potwierdzi zgodność obrazu
z oznaczeniami, również po poprawieniu ścieżki i przy nawigacji między klatkami?
Rozstrzygnięciem jest kontrakt danych i zachowania przy niespójnościach.
Zapis własnych wyników pozostaje w drugim etapie i nie blokuje importu.

Kontekst: [audyt zapisu i orientacji importera](../research-molecular-orientation.md),
[odtwarzanie sesji](../../../moltrack/persistence/session_store.py),
[loader MPP](../../../nanotrack/io/mpp_loader.py).

## Discussion — 2026-10-19

Użytkownik potwierdził w pierwszej rundzie:

- Pierwszy importer otwiera zapis MolTrack powiązany z jednym MPP. Sesje
  oparte na wielu STP/S94 pozostają poza tym zakresem.
- Program szuka obrazu automatycznie, a następnie pozwala wskazać MPP ręcznie.
  Anulowanie lub niezgodny plik pozostawia dotychczasową serię bez zmian.

W drugiej rundzie użytkownik potwierdził:

- Odtwarzamy zapisaną rejestrację o niskiej pewności, pokazując jej jakość.
- Brak lub uszkodzenie rejestracji pozostawia dostępny podgląd oryginałów
  i tych oznaczeń, których położenie można poprawnie ustalić. Uszkodzona
  opcjonalna maska nie blokuje poprawnych bboxów; pokazujemy komunikat.
- Zgodny rozmiarem i geometrią MPP o innej dacie modyfikacji można przyjąć
  po potwierdzeniu przez użytkownika. Niezgodne wymiary lub brak wymaganych
  klatek nadal blokują import.

## Answer — 2026-10-19

Kontrakt poniżej wynika z obu rund odpowiedzi i
[audytu danych oraz istniejącego kodu](../import-geometry-audit.md).
Jest specyfikacją do implementacji szkieletu; zamknięcie ticketu nie oznacza
gotowego importera ani odbioru GUI.

### Zakres i dane wejściowe

Jedno otwarcie to jeden JSON MolTrack i wskazany w nim jeden MPP. Wczytujemy
zapisane oznaczenia, bez detektora, modeli, obliczania rejestracji ani wyników
analizy domen. Pojedyncza klatka i podzbiór klatek źródłowego MPP są dozwolone.
STP/S94, listy plików oraz samodzielne otwieranie MPP są poza tym kontraktem.

Adapter ma odczytywać wspólny podzbiór podstawowych sekcji MolTrack schema
1, 2 i 3. Nie odtwarza całego środowiska MolTrack: ignoruje stan analizy domen,
orientacje, cache pomiarów, ustawienia modeli i korekt, bez ich migracji.
Nieznana wersja główna daje czytelny błąd. Realnym wejściem zweryfikowanym
w tym zadaniu jest schema 1; zgodność podstawowych sekcji 2/3 wymaga osobnych
fixture'ów podczas implementacji, przed deklaracją gotowej obsługi.

| Element | Kontrakt |
| --- | --- |
| `source` | Opis jednego MPP: ścieżki oraz zapisane metadane zgodności. Brak dostępnej ścieżki można naprawić ręcznie. |
| `working_series.source_frame_indices` | Niepusta, uporządkowana lista unikalnych całkowitych ID klatek źródłowych; każde musi istnieć w MPP. |
| Obrazy | Rzeczywiste macierze wczytane z MPP, jeden zgodny rozmiar `(H,W)` i zachowany sygnał liczbowy. |
| Detekcje | Opcjonalna sekcja. Rekord wymaga indeksu roboczego, skończonego bboxa o dodatnim rozmiarze i rozpoznanego układu współrzędnych. |
| Tożsamość oznaczenia | Zachowujemy istniejące ID, pochodzenie, confidence, selected i historyczny bbox; brak dawnego ID można zastąpić identyfikatorem lokalnego rekordu, bez udawania powiązań z maskami. |
| Segmentacje | Opcjonalne maski lub polygony, ich układ, indeks klatki i zapisane powiązania z detekcjami. Brak maski nie usuwa bboxa. |
| Rejestracja | Opcjonalny kompletny zestaw globalnych translacji, ich metoda, referencja oraz jakość/status, odrębne od samej geometrii. |
| Czas i kalibracja | Wartości oraz informacja o ich dostępności i wiarygodności; brak nie zastępuje się zerem. |

Historyczny brak `source_view` w podstawowych rekordach oznacza `raw`, zgodnie
z konwencją starego formatu. Nieznana jawna wartość nie jest zamieniana na `raw`.
Brak `original_bbox_xyxy` oznacza bieżący bbox. Brak confidence lub informacji
o jakości pozostaje wartością nieznaną; nie nadajemy automatycznie statusu `ok`.

### Klatki i nawigacja

`source_frame_indices[i]` wskazuje klatkę źródłową pokazywaną jako robocza `i`.
`frame_index` oznaczeń i rejestracji odnosi się do `i`. Zachowujemy zapisaną
kolejność, także po usunięciu klatek lub odwróceniu serii; nie sortujemy jej
ponownie i nie stosujemy drugi raz `reverse_frame_order`.

Obraz, czas, oznaczenia i transformacja zawsze przechodzą przez tę samą mapę
indeksów. Przykład odbioru: zapis `[4,2]` pokazuje klatki źródłowe 4, potem 2,
z ich czasami, przy obu wartościach flagi reverse. W modelu indeksy są od zera;
numer prezentowany użytkownikowi nie może zmienić przypisania rekordów.
Poprawny `active_frame_index` można odtworzyć; niepoprawny lub brakujący
przenosi podgląd do pierwszej klatki z informacją diagnostyczną.

### Szukanie i zgodność MPP

Kolejność kandydatów: zapisana ścieżka, `path_relative_to_session` względem JSON,
plik o zapisanej nazwie obok JSON, następnie ręczne wskazanie MPP. Nazwę trzeba
rozpoznać także z windowsowej ścieżki. Nie przeszukujemy całego dysku. Samo
istnienie niezgodnego pliku w pierwszej lokalizacji nie kończy szukania.

Sprawdzamy odczytywalność, rozmiar w bajtach względem zapisu, dostępność
wymaganych klatek, zgodność rozmiarów obrazów i znanych danych o geometrii.
Rozbieżna długość bajtowa lub brak wymaganej klatki oznacza niezgodne źródło.
Zgodność samej nazwy, wymiarów albo `size+mtime` nie dowodzi tożsamości zawartości.
Niezgodny shape samej opcjonalnej maski jest błędem maski, a nie samodzielnym
dowodem niezgodności całego MPP.

Zmieniona data przy pozostałych zgodnych kontrolach wymaga potwierdzenia
użycia konkretnego MPP. Pokazujemy ścieżkę i przyczynę potwierdzenia; nie zmieniamy
daty pliku ani JSON. Przy brakujących dawnych metadanych też jawnie wskazujemy
niepełną weryfikację, zamiast ogłaszać pełną zgodność. Historyczny JSON nie ma
hasha: nowo obliczony skrót nie jest dowodem zgodności z nieznanym oryginałem.

Nowa seria zastępuje dotychczasową dopiero po walidacji źródła i mapy klatek.
Anulowanie wyboru/potwierdzenia lub błąd podstawowego wejścia pozostawia
dotychczasową serię bez zmian. Import nie zapisuje do plików źródłowych.

### Geometria obrazu i oznaczeń

Rozróżniamy macierz pliku MPP, obraz oryginalny po normalizacji loadera (`raw`)
oraz obraz wyrównany na powiększonym płótnie (`expanded_aligned`). Loader MPP
obraca macierz o 180°. Oznaczenia `raw` odnoszą się już do tego obróconego obrazu;
nie obracamy ich drugi raz. W tablicy używamy `(wiersz, kolumna)`, w geometrii
`(x,y)`, X w prawo, Y w dół. Bbox opisuje krawędzie pikseli, a jego centrum
to `((x1+x2)/2, (y1+y2)/2)`.

Zapisane `(dx_i,dy_i)` są już przesunięciami globalnymi. Padding odtwarzamy
z całego zestawu wyników należącego do zapisanej serii:

```text
L = ceil(max(0, -min(dx_i)))    R = ceil(max(0, max(dx_i)))
T = ceil(max(0, -min(dy_i)))    B = ceil(max(0, max(dy_i)))
expanded_shape = (H + T + B, W + L + R)
origin_i = (L + dx_i, T + dy_i)
point_expanded = point_raw + origin_i
point_raw = point_expanded - origin_i
```

Nie sumujemy przesunięć ponownie, nie zaokrąglamy położeń bboxów i nie wyliczamy
nowego paddingu tylko dla aktualnie oglądanej części serii. Oryginalne pole klatki
to prostokąt od `origin_i` do `origin_i+(W,H)` w przestrzeni krawędzi pikseli.
Dopełnienie nie jest pomiarem. Osobno zachowujemy ważność próbek obrazu:
przy ułamkowej translacji interpolacja może dawać NaN także na brzegu tego pola.
Jeżeli oznaczenie zawiera zapisany początek klatki, sprawdzamy jego zgodność
z odtworzonym; konflikt wyłącza to oznaczenie z nakładki zamiast je przesuwać
według arbitralnie wybranej wersji geometrii.

Sygnał obrazu wyrównujemy jak NanoTrack: interpolacja liniowa, dopełnienie NaN.
Maski przenosimy najbliższym sąsiadem z tłem False; polygon i bbox translacją.
Maska źródłowa pozostaje zachowana — przełączenie widoku nie przekształca
destrukcyjnie wyniku poprzedniego przełączenia. Gamma zmienia tylko podgląd.

`original_bbox_xyxy` oznacza bbox historyczny w tym samym `source_view`,
a nie bbox z macierzy pliku lub zawsze z `raw`. Podgląd używa bieżącego bboxa.
Zachowujemy oba. Bbox częściowo poza oryginalnym polem nie jest odrzucany:
przycinamy wyświetlanie/wycinek, nie zapisane współrzędne. Bbox całkowicie
poza polem oznaczamy jako położony poza pomiarem, bez udawania poprawnej detekcji
w obszarze danych. Samo `selected=false` również nie usuwa rekordu.

### Braki, błędy i jakość

| Przypadek | Zachowanie |
| --- | --- |
| Nieczytelny JSON, nieobsługiwana wersja, wadliwa mapa klatek lub niezgodny MPP | Brak aktywacji nowej serii; czytelna przyczyna, poprzednia seria pozostaje. |
| Pełne skończone translacje, `low_confidence` lub `manual_review` | Odtworzenie widoku z zachowaną informacją o jakości; możliwość oryginału. |
| Brak jakości przy poprawnych translacjach | Jakość nieznana, bez deklaracji poprawności dopasowania. |
| Rejestracja niepełna, niejednoznaczna, z NaN/nieskończonym przesunięciem lub oznaczona `failed` | Oryginały dostępne, widok wyrównany niedostępny z przyczyną; brak automatycznego zerowania czy ponownego liczenia przesunięć. |
| Oznaczenie `expanded_aligned` bez wiarygodnego odtworzenia całego płótna | Rekord zachowany diagnostycznie, lecz nie nakładany na oryginał. Poprawne oznaczenia `raw` pozostają widoczne. |
| Uszkodzona opcjonalna sekcja lub rekord oznaczeń | Niedostępny element i przyczyna są jawne; pozostałe pewne dane można pokazać. Niezgodny `frame_count` wyłącza daną sekcję. |
| Powtórzone ID oznaczenia lub wyniku rejestracji | Diagnoza konfliktu; brak cichego wyboru ostatniego rekordu. Konfliktujące oznaczenia niedostępne, konflikt rejestracji wyłącza odtworzenie wyrównania. |
| Uszkodzona lub nieobsługiwana maska | Niedostępna maska, zachowany poprawny bbox/polygon i komunikat. Nieprawidłowe powiązanie z detekcją nie jest odgadywane. |

W tym zakresie nie rekonstruujemy płótna z części przesunięć ani z metadanych
pojedynczych masek. Brakująca klatka z ekstremalnym przesunięciem mogłaby zmienić
padding wszystkich pozostałych i przesunąć wszystkie oznaczenia.

Detekcje i segmentacje mają niezależną dostępność. Rozróżniamy: dostępne rekordy,
dostępną pustą listę oraz brak/uszkodzenie danych. Brak rekordów konkretnej klatki
w płaskiej liście MolTrack oznacza „brak zapisanych oznaczeń”, a nie „0 molekuł”
ani potwierdzony brak analizy. Format nie pozwala odzyskać historii sprawdzania
pustych klatek. Nawigacja obejmuje także klatki bez oznaczeń.

Maski odczytujemy na potrzeby klatki, z ograniczonym cache. Kontrakt obejmuje
istniejące kodowania `rle`, `packbits-zlib-base64`, `bbox-packbits-zlib-base64`
oraz `same-as-mask` dla maski historycznej; sprawdzamy pełny shape względem
zadeklarowanego widoku, a nie tylko długość bajtów. Otwarcie JSON nie wymaga
dekodowania wszystkich masek ani podwójnego przechowywania identycznych rastrów.

Kalibracja i czas przykładowego TTMAPP są nieznane: 1000×1000 nm oraz tablica
268 zer czasu są wartościami zastępczymi. Podgląd używa px i numerów klatek.
Zachowujemy oryginalne metadane z informacją o niewiarygodności, bez zamiany
braku na fizyczne zero. Dla innych zapisów samo dodatnie pole w nagłówku nie
potwierdza kalibracji; nie dodajemy teraz edytora kalibracji.

### Kryteria odbioru implementacji

1. Otworzyć wskazany JSON TTMAPP z powiązanym MPP, także po przeniesieniu kopii
   do innego katalogu i ręcznym wskazaniu obrazu o zmienionym mtime. Anulowanie
   oraz niezgodny MPP nie zmieniają wcześniej otwartej serii.
2. Otrzymać 268 oryginałów 256×256 i płótno 480×408; klatka 0 ma początek
   `(224,139)`. Zachować 52 494 bboxy i dostępność 11 993 masek bez ich pełnej
   materializacji przy otwarciu. Oznaczyć 267 wyników o niskiej pewności.
3. Przejść przez klatki 0, 39, 40, 63–67, 68 i 267; sprawdzić obraz/oznaczenia
   w obu widokach, brak masek od 40 oraz brak zapisanych bboxów na 63–67.
   Nie przesuwać oznaczeń do sąsiednich klatek i nie wyświetlać fizycznego zera.
4. Sprawdzić bboxy na brzegu, ułamkowe przesunięcia, maski oraz wielokrotne
   przełączenie oryginał/wyrównany bez narastania błędu. Bbox roundtrip sprawdzać
   z tolerancją numeryczną; nie wymagać bezstratności rastra po dwóch resamplingach.
5. Małymi fixture'ami sprawdzić podstawowe sekcje wersji 1/2/3, jedną klatkę,
   podzbiór i odwrotną kolejność z czasami, null/pustą/brakującą listę,
   niepełną rejestrację, duplikaty, nieznany układ i uszkodzoną maskę.
6. Potwierdzić, że pliki wejściowe nie zostały zmienione, a podgląd nie potrzebuje
   checkpointów i nie uruchamia analizy domen ani ponownej rejestracji.

W tym zadaniu wykonano audyt wejścia, próbę istniejących funkcji i ogląd
statycznych nakładek oraz 6 istniejących testów loadera/geometrii. Powyższy odbiór
nowego importera i GUI pozostaje zadaniem implementacji. Szczegóły i ograniczenia
są w [raporcie audytu](../import-geometry-audit.md).
