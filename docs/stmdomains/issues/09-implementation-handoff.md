# Jak przekazać szkielet do implementacji i go odebrać?

ID: 09
Type: grilling
Labels: wayfinder:grilling
Mode: HITL
Status: resolved
Assignee: Codex — domains/implementation-handoff
Parent: [STM Domains — etap 1: działający szkielet](../map.md)
Blocked by: 01, 07

## Question

Czy ustalony import i podstawowy podgląd wystarczają, aby rozpisać i zbudować
działający szkielet na rzeczywistym zapisie MolTrack?

Ustalmy lokalne moduły importu, modelu serii i widoku oraz zakres użycia
istniejących czytników, geometrii i widgetów. Wskażmy potrzebne zmiany wspólne
do sesji integracyjnej. Pozostawmy prosty punkt do późniejszego podłączenia
analizy, bez projektowania teraz ogólnego systemu metod lub schematu wyników.

Kryteria odbioru mają obejmować otwarcie rzeczywistego zapisu, odnalezienie
obrazów po poprawieniu ścieżki, nawigację, zoom/gamma oraz sprawdzenie zgodności
oznaczeń w original/aligned. Uwzględnijmy serię jednoklatkową, brak danych
i wyraźne oddzielenie dopełnienia od pola pomiarowego. Określmy osobno testy
automatyczne geometrii/importu oraz kontrolę wymagającą lokalnych danych i GUI.

Rozstrzygnięcie przekazuje zakres i kryteria do zadań implementacyjnych etapu 1.
Po ich wykonaniu i odbiorze można rozpocząć drugą mapę. Wybór metody detekcji,
walidacja naukowa, statystyki i zapis wyników nie są warunkami gotowości szkieletu.
Zamknięcie tego ticketu oznacza gotowość specyfikacji, nie wykonanie programu.

## Dependencies

- [Jak zapis wejściowy odtwarza obrazy, oznaczenia i rejestrację?](01-import-and-geometry.md)
- [Jak przeglądać obrazy i oznaczenia w szkielecie?](07-browsing-and-comparison.md)

## Answer — 2026-10-19

Specyfikacja szkieletu jest gotowa do implementacji. Obejmuje import i podgląd
z wcześniej zamkniętych pytań oraz dwa doprecyzowania przyjęte przez użytkownika:

1. Odtwarzanie pokazuje każdą klatkę z jej oznaczeniami. Jeśli przygotowanie
   obrazu trwa dłużej niż zadany interwał, tempo zwalnia; nie pomijamy klatek.
2. Automatyczny kontrast jest dobierany osobno dla każdej klatki, jak
   w prototypie. Jej oryginał i wyrównanie korzystają z tej samej skali.
   Ten sam odcień na różnych klatkach nie oznacza tej samej wartości pomiaru.

Zakres implementacji i kryteria podzielono na
[trzy zadania wykonawcze](../implementation/README.md). Nie są kolejnymi
pytaniami mapy. Zamknięcie tej decyzji i pierwszej mapy oznacza gotową
specyfikację, nie zbudowany lub odebrany program. Nie uruchamiamy w tym
zadaniu implementacji analizy ani zapisu pracy.

### Zakres wersji do odbioru

Natywna aplikacja PyQt6 uruchamiana przez `python -m stmdomains.main`:
MolTrack z jednym MPP, naprawa ścieżki, zachowanie poprzedniej serii przy
błędzie/anulowaniu, wariant C z jednym obrazem i paskiem miniatur, nawigacja,
play/pauza, zoom/gamma, wejściowe ramki/maski i zapisane wyrównanie.
Pole pomiarowe i dopełnienie pozostają rozróżnialne; nieznana kalibracja/czas
są jawne. Pełne wymagania pozostają w
[kontrakcie importu](01-import-and-geometry.md#answer--2026-10-19) i
[kontrakcie podglądu](07-browsing-and-comparison.md#answer).

Nie dodajemy obliczania rejestracji, wykrywania/edycji oznaczeń, analizy domen,
statystyk, edytora kalibracji, usuwania klatek, własnego zapisu ani eksportu.
Kontrakt `.stmdomains` jest uzgodniony w etapie 2, ale zapis przed analizą
również należy do tej późniejszej funkcji. Program STM Viewer ma osobny zakres.

### Moduły i ich interfejsy

Podane ścieżki są planem lokalnych modułów do utworzenia, nie istniejącym kodem.
Nazwy pomocników wewnątrz modułu można dobrać przy implementacji.

| Moduł | Mały interfejs i ukryta odpowiedzialność |
| --- | --- |
| `stmdomains/core/series.py` | Odczyt opisu serii oraz danych klatki według indeksu roboczego. Wewnątrz obrazy, mapa źródłowa, oznaczenia i ich dostępność, zakodowane maski, rejestracja, metadane jakości i diagnostyka. Zachowuje braki jako braki; bez zależności od Qt. |
| `stmdomains/io/moltrack_import.py` | Przygotowanie wejścia, wskazanie/ocena źródła i zwrócenie zwalidowanego kandydata serii. Wyniki wymagające ścieżki albo potwierdzenia są danymi dla kontrolera, nie dialogami wywoływanymi w importerze. JSON, wersje 1/2/3, mapowanie klatek i błędy rekordów pozostają za tym interfejsem. |
| `stmdomains/io/mask_codec.py` | Odczyt pojedynczej maski i jej diagnostyki z kontrolą kodowania, shape oraz powiązania. Współpracuje z cache ograniczonym liczbą klatek/bajtów; nie dekoduje wszystkich masek przy otwarciu. |
| `stmdomains/core/geometry.py` | Odczyt geometrii całej serii oraz przygotowanie obrazu i nakładek jednej klatki dla raw/aligned. Jedno płótno z całej rejestracji, wspólne transformacje, jawne pole i dopełnienie. Nie liczy rejestracji. |
| `stmdomains/ui/image_view.py` | Przyjmuje kompletny opis widoku jednej klatki; pokazuje obraz, ramki, maski i pole, obsługuje zoom/pan oraz wybór ramki. Numery klatek i geometria nie są odgadywane z pozycji elementu UI. |
| `stmdomains/ui/filmstrip.py` | Prezentuje miniatury i bieżący wybór, zgłasza wybór indeksu roboczego. Miniatury są odtwarzalnym cache podglądu, bez własnej kopii modelu analizy. |
| `stmdomains/ui/session_controller.py` | Koordynuje import, dialogi, aktywną serię, zadania w tle i odtwarzanie. Zatwierdza gotowy import jednym przełączeniem; odrzuca spóźnione odpowiedzi nieaktualnych zadań. |
| `stmdomains/ui/main_window.py` | Składa wariant C i łączy działania użytkownika z kontrolerem. Nie parsuje MolTrack, nie przelicza przesunięć i nie dekoduje masek. |

Wspólny opis klatki do pokazania zawiera tożsamość serii/klatki, tryb,
obraz, geometrię, nakładki i ich dostępność. Ten komplet stanowi prosty
interfejs także do przyszłego podłączenia analizy. Na tym etapie nie tworzymy
rejestru algorytmów, pluginów ani ogólnego modelu wyników domen.

### Ponowne użycie i ograniczenia istniejącego kodu

- [Czytnik MPP](../../../nanotrack/io/mpp_loader.py): używamy publicznego
  `load_mpp_sequence(..., reverse_frame_order=False)` za lokalnym adapterem.
  Wykonuje obrót macierzy MPP o 180°. Następnie jedna mapa `source_frame_indices`
  wybiera obrazy i odpowiadające im czasy, bez drugiego odwracania serii.
  Czytnik materializuje MPP; nie przedstawiamy go jako strumieniowego.
- Nie używamy pełnego [loadera sesji MolTrack](../../../moltrack/persistence/session_store.py)
  jako importera Domains. Wciąga analizę M6, dekoduje wszystkie maski,
  wymusza mtime i ma inne domyślne stany jakości. Prywatne dekodery nie stają
  się publicznym interfejsem aplikacji; lokalny wąski kodek realizuje uzgodnione
  kodowania i waliduje pełną geometrię. Jego zgodność sprawdzają małe fixture'y.
- Modele MolTrack z wymaganym confidence, domyślną jakością `ok` lub obowiązkową
  zdekodowaną maską nie są kanonicznym modelem Domains. Lokalne rekordy
  przechowują wartości nieznane i kodowane maski bez fałszowania dostępności.
- [Geometria MolTrack](../../../moltrack/core/registered_coordinates.py) jest
  wzorcem translacji bbox/polygon/mask. Funkcje konwersji promptu przycinają
  bboxy i nie nadają się do wiernego importu. Niewielka lokalna geometria
  używa NumPy/SciPy; w testach porównujemy ją z publicznymi funkcjami,
  ale kod produkcyjny nie potrzebuje szerokiego grafu importów rejestracji.
- [Wyrównanie NanoTrack](../../../nanotrack/registration/aligned.py) jest wzorcem
  interpolacji liniowej i paddingu. Funkcja budująca cały stos nie służy
  renderowaniu pojedynczej klatki: liczy płótno z przekazanego zestawu.
  Renderer lokalny dostaje ustalone płótno całej serii i translację klatki.
- Lokalny widok PyQt6, np. `QGraphicsView` + `QImage`, jest mniejszy niż
  adaptowanie całego [ViewerWidget](../../../napara/gui/widgets/viewer_widget.py)
  lub widoków MolTrack/NanoTrack. Nie zależy od globalnych ustawień pyqtgraph,
  osi zawsze w nm, zastępowania NaN medianą ani edytorów/analizy starych aplikacji.
  Przejmujemy sprawdzone zachowania zoomu, pan i gamma, nie całe okno.
- Prototyp HTML jest materiałem do zachowania wariantu C, a nie źródłem do
  scalenia. Aplikacja nie wymaga QtWebEngine ani osadzonej strony WWW.

### Kontrast i poprawność prezentacji

Domyślna skala: percentyle 2 i 98 **skończonych próbek oryginalnej klatki**,
zgodnie z wybranym zachowaniem prototypu. Granice liczymy raz na klatkę,
bez paddingu i bez ograniczania do wycinka zoomu. Ten sam zakres stosujemy
do raw i aligned danej klatki. Obraz wyrównany powstaje z danych pomiarowych,
a nie z już zgammowanego PNG. Intensywność przed gamma to
`u = clip((value - low)/(high - low), 0, 1)`; gamma to `u**(1/gamma)`.
Gamma 1 nie zmienia znormalizowanej jasności, a większa gamma ją rozjaśnia.
Dane pomiarowe, confidence oraz kolory/krycie nakładek pozostają niezmienione.

Gdy `high == low`, skończone próbki dostają stały środkowy odcień przed gamma;
nie dzielimy przez zero. Brak skończonych próbek daje jawny brak obrazu
pomiarowego w danej klatce. NaN/dopełnienie mają osobne tło, nie wartość mediany.
Nie utożsamiamy granicy geometrycznego pola z maską skończonych próbek po
interpolacji. Informacja „auto kontrast klatki” wyjaśnia różnicę skal między
klatkami. Nie dodajemy teraz kontroli wspólnego zakresu intensywności serii.

Scena ma osie X w prawo, Y w dół; piksel `[r,c]` zajmuje prostokąt
`[c,c+1] × [r,r+1]`, jego środek to `(c+0.5,r+0.5)`. Bboxy są współrzędnymi
krawędzi i nie dostają kolejnego przesunięcia o pół piksela. Maski używają
tej samej geometrii obrazu. To należy sprawdzić na niekwadratowym,
niesymetrycznym wzorcu z pojedynczymi pikselami oraz ułamkowymi translacjami.

Miniatury pokazują oryginalną klatkę, z jej automatycznym kontrastem i gamma 1,
bez nakładek, jak w prototypie. Numer i oznaczenie bieżącej klatki są czytelne.
Zmiana gamma dużego podglądu nie wymaga przeliczenia wszystkich miniaturek.

### Import, zadania w tle i odtwarzanie

Podczas otwierania poprzednia seria i podgląd pozostają aktywne, a odtwarzanie
jest zatrzymane. Dialog wyboru źródła oraz potwierdzenia mtime działa w wątku
GUI. Odczyt JSON/MPP, przygotowanie klatki i masek mogą działać w lokalnym
workerze; widgety i `QPixmap` pozostają w wątku GUI. Postęp, błędy i anulowanie
przechodzą przez kontroler. Nie używamy wymuszonego zakończenia wątku.
Anulowanie oznacza rezygnację z kandydata; trwający nieprzerywalny odczyt może
się zakończyć, ale jego wynik nie może później zastąpić aktywnej serii.

Każde otwarcie i żądanie podglądu ma tożsamość. Spóźniona odpowiedź po nowym
imporcie, zmianie klatki/widoku albo pauzie nie podmienia aktualnego obrazu.
GUI zawsze otrzymuje zgodne obraz + oznaczenia + numer + status, bez nakładek
z poprzedniej klatki. Przy ręcznym szybkim przewijaniu można porzucić nieaktualne
żądania i przygotować ostatnio wybraną klatkę; to odrębne od odtwarzania.

Play przechodzi do kolejnego obrazu po gotowości kompletnego widoku. Zadane
1/2/5/10/20 kl./s jest maksymalnym tempem, nie nakazem przeskakiwania klatek.
Nie gromadzimy kolejki timerów do późniejszego nadrabiania. Pauza zatrzymuje
na aktualnie pokazanej klatce i unieważnia oczekujący krok odtwarzania;
nie następuje dodatkowy przeskok po pauzie. Koniec zatrzymuje, a „Od początku”
rozpoczyna od pierwszej klatki. Jednoklatkowość i ręczna nawigacja zachowują
reguły z kontraktu podglądu.

Maski i obrazy wyrównane powstają na potrzeby klatki, z jawnym ograniczeniem
cache. Nie utrwalamy całego stosu masek ani obrazów wyrównanych w pamięci.
Miniatury można przygotowywać stopniowo; ich ładowanie nie blokuje pierwszego
obrazu. Przy odbiorze zapisujemy rzeczywiste koszty otwarcia, przejścia klatki
z maskami i bez, RSS oraz reakcję na pauzę/anulowanie. Koszt generatora HTML
nie stanowi pomiaru aplikacji. Nie ustalamy arbitralnego SLA dla tego lokalnego
narzędzia; poprawność, responsywność i możliwość przerwania są warunkami odbioru.

### Testy, dane i odbiór

Kanoniczna lista sprawdzeń jest w
[odbiorze szkieletu](../implementation/03-acceptance.md). Rozdziela:

- automatyczne testy małych fixture'ów i interfejsów importu/geometrii;
- integrację Qt w trybie offscreen, w tym cykl żądań i stan UI;
- sprawdzenia pełnych lokalnych danych TTMAPP i rzeczywistego GUI.

Przyszły odbiór wymaga wszystkich trzech warstw. Brak lokalnych danych/GUI
musi być zapisany jako niewykonane sprawdzenie, nie jako sukces. Po testach
technicznych użytkownik ocenia działającą aplikację według scenariusza;
przykłady i pomiary dokumentujemy w raporcie odbioru. Dopiero zakończenie
zadań wykonawczych oraz odbiór programu otwierają zwykły tok etapu 2.

### Zależności i przekazanie integracyjne

Wybrany kierunek wymaga PyQt6, NumPy i SciPy; testy korzystają z pytest
oraz pytest-qt. Brak potrzeby Torch, modeli, OpenCV, pyqtgraph, Pillow,
Matplotlib ani skimage w samej ścieżce produkcyjnej szkieletu. Publiczne
funkcje dawnych modułów mogą być dodatkowymi wzorcami testowymi w `netcat`.
Nie należy sprowadzać ich szerokich pakietów tylko po jeden prywatny pomocnik.

Lokalne środowisko `netcat` wystarcza do rozwoju. Główny
[plik zależności szkieletów](../../../requirements/stm-apps.txt) zawiera obecnie
sam PyQt6; dopisanie NumPy/SciPy i włączenie nowych testów do CI należy do
sesji integracyjnej. Nie deklarujemy gotowej instalacji z tego starego pliku.
Opcjonalne wydzielenie lekkiego dekodera masek lub renderera wspólnego jest
możliwością integracji, a nie warunkiem rozpoczęcia implementacji lokalnej.
Nie zmieniamy teraz wspólnych modeli, czytników ani konfiguracji głównej.

### Wykonane sprawdzenia tego zadania

Audyt tylko do odczytu potwierdził zakres startowego okna oraz opisane
ograniczenia loaderów, modeli, widgetów i importów. Mała próba Qt/offscreen
pokazała, że wspólny ViewerWidget bez ustawienia row-major zamienia wymiary
niekwadratowego obrazu, opisuje osie nm bez kalibracji i wypełnia NaN medianą.
Próba importów modułów bez danych wykazała m.in. 171 załadowanych modułów
`moltrack.analysis` przy imporcie pełnego `session_store`. To uzasadnia lokalne
moduły, nie jest testem przyszłego szkieletu ani pomiarem jego wydajności.

Nie uruchamiano ponownie dawnych testów loadera ani pełnej pary TTMAPP.
Sześć wcześniejszych testów z audytu importu i ogląd prototypu HTML dotyczą
poprzednich zadań. Nowe zadania wykonawcze zaczynają ze statusem `todo`.

## Comments

### 2026-10-16 — podział zakresu zatwierdzony przez użytkownika

Usunięto zależność przekazania szkieletu od wyboru metod, referencji jakości
i eksportu. Pytania o koszt analizy, jej anulowanie i ponowne użycie wyników
pozostają częścią [Jak porównać metody wykrywania wysp i domen w serii?](05-stable-types-across-frames.md)
i [Co zapisujemy i eksportujemy po próbach metod?](08-save-and-export.md) w drugim etapie.

Kontekst: [instrukcje współpracy](../../PARALLEL_DEVELOPMENT.md).

### 2026-10-19 — przygotowanie przekazania

Import i podgląd są uzgodnione. Sprawdzamy lokalne punkty ponownego użycia,
ustalamy brakujące zachowania prezentacji i przygotowujemy zadania budowy
oraz odbioru szkieletu. Zamknięcie pytania zakończy specyfikację pierwszej mapy,
nie będzie deklaracją zaimplementowanej ani odebranej aplikacji.

### 2026-10-19 — odpowiedzi użytkownika i zamknięcie specyfikacji

Użytkownik przyjął pokazywanie każdej klatki z możliwością zwolnienia tempa
oraz automatyczny kontrast każdej klatki. Import i układ C pozostają zgodne
z wcześniejszymi decyzjami. Wskazano lokalne moduły i trzy zadania wykonawcze;
pierwsza mapa kończy się gotową specyfikacją, przed implementacją i odbiorem GUI.
