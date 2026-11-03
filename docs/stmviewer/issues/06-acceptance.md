# Dane i kryteria odbioru pierwszej wersji

Type: grilling
Label: wayfinder:grilling
Status: resolved
Assignee: rlew
Parent: [STM Viewer — mapa pierwszej wersji](../map.md)
Blocked by: 04, 05

Zależy od: [Zapis MPP z wartościami i metadanymi](04-mpp-export.md)
oraz [Opcje filmu AVI](05-avi-export.md).

## Question

Na jakich danych, platformach i mierzalnych kryteriach odbierzemy pierwszą wersję
przeglądarki, nie uzależniając jej od późniejszego strojenia rejestracji?

Do ustalenia: typowy i największy rozmiar serii, docelowe systemy grupy,
przykładowe STP/S94/MPP i odtwarzacz AVI, oczekiwana płynność, tolerancje
ponownego odczytu MPP oraz ręczny scenariusz GUI. Oddzielamy poprawne wykonanie
istniejącego algorytmu od jakości dopasowania nowych danych.

Po uzgodnieniu kontraktów należy wskazać pozostałe blokady implementacji,
w tym potrzebne zmiany wspólnych modułów do sesji integracyjnej.

## Comments

### 2026-10-14 — punkt wyjścia

Program będzie używany wewnętrznie przez kilka osób. Użytkownik dopuścił
lokalne środowisko conda netcat do rozwoju. Nie określił jeszcze systemów
docelowych ani wielkości serii. Lokalizacja środowiska i dostępne sprawdzenia:
[Rozpoznanie istniejącego kodu](../reconnaissance.md).

### 2026-10-19 — konsekwencje kontraktu MPP

[Zapis MPP z wartościami i metadanymi](04-mpp-export.md#answer) jest rozstrzygnięty.
Odbiór ma sprawdzić parę filmu i dodatku, zapis original/aligned, niezależność
od podglądu, liczby i orientację, NaN, geometrię, usuwanie klatek, czasy,
niejednorodną kalibrację oraz brakujący/niedopasowany dodatek. Zachowanie
liczb przy samej serializacji jest odrębne od dokładności wcześniejszej
interpolacji rejestracji.

Użytkownik wskazał WSxM jako program do późniejszego otwierania pliku;
nie tworzymy osobnego trybu eksportu i nie blokujemy z tej przyczyny
mieszanych serii. Potrzebna jest próba w docelowej wersji WSxM na małym
asymetrycznym filmie o znanych liczbach, skali i NaN. Należy oddzielić
otwarcie pliku od poprawnego wyświetlenia i interpretacji danych.
[Rozpoznanie](../wsxm-mpp-compatibility.md) nie potwierdza jeszcze NaN w WSxM.
Wynik próby nie może prowadzić do cichego zerowania lub kadrowania aligned.

Nie oceniono jeszcze docelowej wydajności, dużych serii ani właściwej wersji
WSxM. Obecny limit 1000 linii nagłówka nie może zostać ukrytym limitem liczby
klatek nowej aplikacji; zapis/odczyt ma go obsłużyć lub wykryć przed zapisem.

### 2026-10-19 — konsekwencje kontraktu AVI i pozostały odbiór mapy

[Opcje filmu AVI](05-avi-export.md#answer) są rozstrzygnięte. Odbiór obejmuje
pełny obraz, zakres od–do, niezależność od okna, FPS, oba tryby kontrastu,
gamma, trzy tła, opisy, anizotropię lub brak wspólnej skali oraz dopełnienie
nieparzystych wymiarów. Nie ma eksportu wycinka ani ręcznej rozdzielczości.

[Lokalna próba](../avi-export-reconnaissance.md) potwierdziła MJPG i FFV1
przez OpenCV/FFmpeg. Oba obcinały 65×49 do 64×48 bez jawnego dopełnienia;
po dopełnieniu 66×50 zachowano pełną geometrię. FFV1 zachował wszystkie
wyrenderowane piksele; MJPG jest stratny. Zachowano 7 klatek i 7,5 FPS.
To nie jest potwierdzenie zgodności z docelowym odtwarzaczem.

Pozostają do ustalenia konkretne dane, największe serie/filmy, systemy,
odtwarzacz i wersja WSxM oraz wymagania wydajności. Odbiór powinien też
objąć anulowanie/błąd zapisu bez utraty poprzedniego pliku, pojedynczą klatkę,
stałe i całkowicie brakujące dane, czytelność opisów oraz eksport po usuwaniu
klatek i zmianie wyniku rejestracji.

Po domknięciu tych kryteriów należy skonfrontować potrzeby wspólnych zmian
z [przekazaniem](../handoff.md), ustalić zakres integracji i sprawdzić, czy
pozostała osobna decyzja blokująca implementację. Samo rozstrzygnięcie mapy
nie oznacza, że aplikacja jest już zaimplementowana.

### 2026-10-19 — platformy i sposób uruchamiania

Użytkownik wymaga pierwszej wersji dla **Linuksa i Windows**. Uruchamianie
z kodu repozytorium w opisanym środowisku Python; przygotowanie instalatora
lub samodzielnego pliku wykonywalnego nie należy do odbioru tej wersji.
Wynik lokalnej próby na Linuksie nie zastępuje sprawdzenia na Windows.
Konkretne środowiska odbioru, wielkości danych i progi płynności pozostają
do uzgodnienia.

### 2026-10-19 — dostępne fakty do decyzji

Zapisano [inwentarz danych, środowiska i istniejących testów](../acceptance-reconnaissance.md).
Największa lokalna liczba klatek to 364 przy 256 × 256; jest też film
84 × 512 × 512 i wskazany przez użytkownika TTMAPP 268 × 256 × 256.
Rozpoznanie nagłówków nie jest pełnym odbiorem tych plików. Brak lokalnego
odtwarzacza/WSxM oraz środowiska Windows pozostaje ograniczeniem wykonanych
sprawdzeń, nie powodem do uznania przyszłego odbioru za zaliczony.

### 2026-10-19 — komplet odpowiedzi i granica odbioru

Użytkownik potwierdził Ubuntu 24.04 i Windows 11, uruchamianie z repozytorium
w środowisku Python oraz pomiary lokalne i test 1000 × 512 × 512. Doprecyzował
sprzęt: **16 GB wolnego RAM**, SSD i NVIDIA z CUDA oraz co najmniej 8 GB VRAM.
Nie chodzi o komputer mający łącznie 16 GB pamięci.

Potwierdzono 5 kl./s po wczytaniu, reakcję na wybór klatki/Pause do 250 ms
w co najmniej 95% prób, wyższe tempa według możliwości sprzętu i zwalnianie
bez pomijania klatek. Długie operacje mają postęp i anulowanie, bez sztywnego
limitu całkowitego czasu. AVI sprawdzamy w VLC na obu systemach. Obowiązkowy
odbiór MPP obejmuje Viewer i czytniki repozytorium; **WSxM jest sprawdzeniem
dodatkowym, które nie blokuje pierwszej wersji**. Ta ostatnia odpowiedź
rozstrzyga wcześniejsze niejasności co do roli WSxM.

## Answer

Rozstrzygnięto 2026-10-19 na podstawie odpowiedzi użytkownika. To kryteria
przyszłego odbioru implementacji. Nie oznaczają zaliczonych testów aplikacji.
Mapa decyzji jest kompletna; nie pozostała decyzja produktowa blokująca
rozpoczęcie implementacji. Potrzeby wspólnego kodu są w [przekazaniu](../handoff.md).

### Środowiska odbioru

- Ubuntu 24.04 i Windows 11, oba x86_64. Uruchomienie z repozytorium
  w opisanym środowisku Python; instalator i samodzielny plik wykonywalny
  nie należą do tej wersji. Sprawdzenie wyłącznie na Linuksie nie wystarcza.
- Stanowisko ma przed uruchomieniem około 16 GB lub więcej **wolnego RAM**,
  SSD i NVIDIA z CUDA, minimum 8 GB VRAM. Raport podaje rzeczywiste CPU,
  dostępny RAM, model/VRAM GPU, sterownik, system, Python i zależności.
  Wynik na mocniejszym komputerze wymaga podania zużycia zasobów;
  sama obecność dużej pamięci nie dowodzi działania w przyjętym budżecie.
- Wspólny punkt wyjścia to Python 3.12; konkretne sprawdzone zależności,
  w tym OpenCV/FFmpeg i opcjonalny stos GPU, trzeba zapisać dla obu systemów.
  Zmiany konfiguracji głównej koordynuje sesja integracyjna.
- Phase oraz zapis/odczyt MPP i obu kodeków AVI muszą działać w środowisku
  odbioru. Dostępność pozostałych metod podlega [kontraktowi rejestracji](03-registration.md#answer).
  Metoda oznaczona jako dostępna wymaga rzeczywistej próby; metoda niedostępna
  podaje przyczynę, bez automatycznego pobierania wag lub zamiany metody.
- GPU dotyczy obecnie Deep Matcher. Pozostałe backendy i materializator
  aligned pracują na CPU; nie dodajemy tu zadania przenoszenia ich na GPU.
  Test z atrapą matchera nie dowodzi działania CUDA ani rzeczywistych wag.
- VLC jest odbiornikiem AVI na obu systemach. Zapisać jego wersję i sprawdzić
  oba kodeki; nie wystarcza odczyt tym samym backendem, który zapisał film.
  WSxM jest próbą dodatkową, bez wymogu konkretnej wersji do zamknięcia
  pierwszego odbioru. Nie deklarować zgodności, zanim próba faktycznie się odbędzie.

### Zestaw danych

Ścieżki i rozmiary pomiarów: [inwentarz](../acceptance-reconnaissance.md).
Dane pomiarowe i duże wyniki pozostają poza Git. Małe syntetyczne przypadki
oraz generatory przyszłych testów mogą należeć do testów repozytorium.
Przed odbiorem zapisać manifest wybranych plików, ich rozmiary i SHA-256,
aby oba systemy sprawdzały te same dane; nie haszowano ich w tej sesji.

| Zestaw | Rola w odbiorze |
| --- | --- |
| Pary `17851` i `17544` STP/S94 oraz seria STP `TTMAPP/TTMAPP_AU111/movie2/` | Rzeczywiste dekodowanie obu formatów, naturalna kolejność, mieszana seria, jednostki i orientacja. |
| `MOVIE_3.MPP`, 17 × 256 × 256, Current | Mały film, kanał prądu i pełny ręczny przebieg. |
| `TTMAPP/MOVIE_23raw_TTMAPP_I_AU111.MPP`, 268 × 256 × 256 | Główna seria typowa. Jej zastępcze 1000 nm i zera nie stanowią wzorca kalibracji/czasu. |
| `nanotrack_registration/trudne/MOVIE_4.mpp`, 364 × 256 × 256 | Dłuższy rzeczywisty film oraz obserwacja zachowania rejestracji na trudnych danych. |
| `nanotrack_registration/trudne/MOVIE_8.mpp`, 84 × 512 × 512 | Rzeczywiste dane o większej rozdzielczości. |
| `MOVIE_1.MPP`, 36 × 301 × 268, oraz mały asymetryczny wzorzec | Prostokątny obraz, nieparzyste wymiary, kontrola orientacji i zachowania ostatnich krawędzi. |
| Seria syntetyczna 1000 × 512 × 512 | Test dużej serii: około 2,10 GB samych wartości float64 original, bez kopii roboczych i aligned. |
| Małe syntetyczne przypadki brzegowe | Znane wartości, skale, czasy i przesunięcia; brakujące metadane, NaN, stałe obrazy, pojedyncza klatka, błąd/anulowanie. |

Typowy zakres to do około 400 klatek 256 × 256 oraz znaleziony film 512 × 512.
Test 1000 × 512 × 512 jest celem odbioru, **nie limitem importu**. Większa
seria może działać, ale ten odbiór tego nie potwierdza. Duży test obejmuje
wczytanie, podgląd, usuwanie, rejestrację Phase, MPP i oba kodeki AVI.
Wzorzec z kontrolowanymi przesunięciami powinien obejmować również powiększony
obszar aligned (np. 640 × 640 przy rozpiętości przesunięć 128 px).
Raport musi podawać faktyczne wymiary wyniku; sama liczba klatek nie określa
zapotrzebowania na pamięć. Test eksportu nie może ograniczać się do pierwszych
kilku klatek dużej serii.

Brak lokalnych danych oznacza niewykonany odbiór pomiarów, nie zaliczenie.
Małe testy automatyczne mają działać bez katalogu pomiarowego. Osobno uruchamia
się próby wymagające jawnie wskazanego katalogu danych. Prawdopodobnych kopii
tego samego filmu nie liczymy jako niezależnych przypadków jakościowych.

### Płynność i pomiar zasobów

- Po zakończeniu wczytywania wymagane jest płynne zadane 5 kl./s zarówno
  dla original, jak i gotowego aligned, na seriach typowych i dużej.
  Mierzyć faktyczne zmiany obrazu, nie same wywołania timera. Raportować
  średnie tempo i rozkład odstępów między klatkami, z oczekiwanym odstępem
  około 200 ms; nie uznawać serii długich zatrzymań nadrobionych skokiem za płynność.
- Wyższe tempa 10–30 kl./s są zależne od możliwości komputera. Gdy program
  nie nadąża, zwalnia i pokazuje kolejne klatki bez pomijania ani nadrabiania
  zaległości przez skok. Ta zasada dotyczy Play; AVI zawsze zawiera każdą
  wybraną klatkę raz i zachowuje zadane FPS pliku.
- Wybór klatki i Pause: czas od działania użytkownika do widocznego efektu
  nie przekracza 250 ms w co najmniej 95% prób. W każdym środowisku zebrać
  przynajmniej 100 prób, obejmujących obie czynności, oba widoki oraz typową
  i dużą serię; podać rozkład wyników osobno dla tych przypadków.
- Próbę Play wykonać przez co najmniej 30 s bez innych długich operacji,
  po przygotowaniu widoku; stosować pętlę, gdy wymaga tego długość serii.
  Raportować zachowanie zimnego otwarcia osobno od odtwarzania po wczytaniu.
- Import, rejestracja i eksport mogą trwać dłużej. Wymagane są działające
  okno, postęp i przyjęcie anulowania. Zakończenie obliczeń następuje w
  najbliższym bezpiecznym punkcie, także po długim kroku backendu; UI pokazuje
  oczekiwanie na przerwanie i zachowuje poprzedni kompletny wynik.
  Nie wymagamy 5 kl./s jednocześnie z pracą długiej operacji.
- Całkowite czasy importu/rejestracji/eksportu mierzymy i zapisujemy bez
  sztywnego limitu. Rejestrować szczytowe użycie RAM całej aplikacji wraz
  z workerami oraz VRAM przy metodzie GPU. Wielokrotne otwarcie, eksport
  i ponowna rejestracja nie mogą stale zatrzymywać starych stosów danych.
  Błąd zasobów nie może publikować częściowego wyniku lub uszkodzić wcześniejszego pliku.

### Wartości i tolerancje

**MPP:** dla wartości skończonych ponowny odczyt ma zachować dokładnie liczby
przekazane do zapisu (`rtol = 0`, `atol = 0`). Porównujemy oryginał w pamięci
lub już obliczone aligned, bez ponownej interpolacji. Wymagana jest identyczna
maska NaN, wymiary, kolejność i orientacja. Nie wymagamy identyczności bajtów
całego pliku/nagłówka ani wewnętrznego kodu bitowego NaN. Promocja float32
z S94/aligned do float64 nie poprawia wcześniejszej precyzji.

Dla pary MPP i metadanych wymagamy zachowania znaczenia wszystkich pól
[kontraktu MPP](04-mpp-export.md#answer): jednostek, kalibracji per klatka,
czasów z przerwami i brakami, pochodzenia oraz geometrii. Pole oryginalnej
klatki pozostaje osobne od maski ważności. Liczby zapisane w metadanych nie
mogą być obcinane do precyzji etykiety GUI. Test obejmuje obie wersje,
ścieżki STP → MPP, S94 → MPP, MPP → MPP oraz odczyt w Viewer i dotychczasowych
czytnikach NaPara/NanoTrack/MolTrack. Dla odbiorców nieznających dodatku oceniać
ich rzeczywisty zakres: obrazy, orientację, liczby i wspólne metadane, bez
wymagania odtworzenia informacji dostępnej wyłącznie w dodatku Viewera.

**Rejestracja:** sprawdzamy poprawne wywołanie istniejących backendów oraz
kontrakt aplikacji. Wzorce z kontrolowanym wynikiem wymagają prawidłowego
znaku XY, kumulacji, obszaru, prostokątów i maski. Dla interpolacji sprawdzamy
wynik względem ustalonego próbkowania liniowego z dokładnością wynikającą
z float32, a nie przez tolerancję serializacji MPP. Istniejące syntetyczne
testy backendów zachowują własne progi; nie dodajemy uniwersalnej tolerancji
błędu dopasowania rzeczywistych pomiarów. Jakość na trudnych filmach opisujemy
osobno. Niska pewność ma być widoczna, a błąd/anulowanie nie usuwa starego
wyniku. Strojenie metod pozostaje poza tą mapą.

**AVI:** wymagamy dokładnej liczby i kolejności klatek, rozmiaru, pełnych
krawędzi oraz zadanego FPS zgodnie z rozdzielczością zapisu tempa w kontenerze.
Testować m.in. 1, 5, 7,5 i 30 FPS oraz jedną klatkę. FFV1 musi odtworzyć
każdy piksel uint8 przygotowany dla kodeka, a MJPG podlega ocenie stratnej
prezentacji: rozpoznawalny obraz i czytelne wybrane opisy, bez błędnego kadru
lub znikających klatek. Oba należy rzeczywiście otworzyć i odtworzyć w VLC
na obu systemach; czas filmu wynika z liczby klatek/FPS.

### Przypadki obowiązkowe i ręczny scenariusz

Scenariusz wykonać na obu systemach. Szczegóły zachowania pozostają
w odpowiednich decyzjach; poniżej ich wspólny przebieg odbioru.

1. Uruchomić czyste środowisko według instrukcji. Otworzyć serię STP/S94
   w nieuporządkowanym wyborze nazw. Sprawdzić kolejność, wymiary, pochodzenie
   i metadane; następnie zastąpić ją małym MPP i filmem typowym.
2. Sprawdzić filmstrip, Play/Pause, koniec/pętlę, ręczny wybór klatki, gamma
   i zoom. Zapisać pomiary płynności. Nieudany import z plikiem uszkodzonym
   lub innym wymiarem ma zachować poprzednią serię i podgląd.
3. Uruchomić Phase. Sprawdzić postęp, dostępny podgląd i blokadę zmiany serii;
   po sukcesie aligned tej samej klatki, gamma, dopasowanie pełnego obszaru,
   szachownicę i obrys. Original musi zachować wartości i własny zoom.
4. Usunąć klatkę środkową, skrajną i historyczne odniesienie. Sprawdzić
   następną/poprzednią klatkę, czasy i pochodzenie. Pozostałe aligned oraz
   ich wspólny obszar nie mogą się zmienić. Powtórzyć rejestrację i sprawdzić
   publikację nowego wyniku dopiero po pełnym sukcesie.
5. Sprawdzić niską pewność, brak bibliotek/wag, odrzucenie wejścia z NaN
   przez obecne backendy oraz kontrolowany błąd i anulowanie nowej próby.
   Stary wynik pozostaje. Przy dostępnych wagach wykonać rzeczywistą próbę
   Deep Matcher/CUDA, bez pobierania z aplikacji, z informacją o urządzeniu.
6. Zapisać original i aligned do MPP, zamknąć i otworzyć każdy wynik.
   Wykonać powyższe porównania liczb/metadanych oraz próby z brakującym,
   zmienionym i niezgodnym dodatkiem. Nie stosować błędnego dodatku do filmu.
   Sprawdzić także serię o różnych skalach/kanałach, brakujące czasy i długi
   nagłówek, aby dawny limit 1000 linii nie ukrył limitu dużej serii.
7. Zapisać AVI: pełną serię i zakres, original/aligned, oba kodeki, oba tryby
   kontrastu i gamma, każde tło oraz wybrane opisy. Sprawdzić nieparzyste
   wymiary, anizotropię i brak wspólnej skali. Zmiana zoomu/rozmiaru okna
   nie zmienia wyjściowej geometrii. Odtworzyć wyniki w VLC.
8. W małych wzorcach sprawdzić klatkę stałą, całkowicie brakujące próbki,
   nieznane czasy i obraz za mały na wybrane opisy. Seria/zakres z jedną
   klatką pozwala na zapis, pusta seria nie. Usunięcie ostatniej klatki
   zostawia pusty program i nie zmienia źródeł na dysku.
9. Wymusić błąd i anulowanie importu, rejestracji oraz obu eksportów,
   także przy istniejącym pliku docelowym. Sprawdzić zachowanie poprzednich
   danych i brak fałszywego sukcesu. Dla pary MPP+JSON sprawdzić również
   wykrywanie niedopasowania po przerwaniu publikacji między plikami.
10. Powtórzyć główny przebieg z dużą serią: otwarcie, oba widoki, usuwanie,
    ponowna rejestracja oraz pełny eksport MPP/MJPG/FFV1. Zapisać czasy,
    rozmiary, szczytowe zużycie zasobów i porównać wynik po odczycie.

Testy automatyczne mają obejmować kontrakty i kontrolowane awarie; ręczna
próba GUI sprawdza przebieg widoczny dla użytkownika. Nie trzeba uruchamiać
wszystkich kombinacji opcji na każdym dużym pomiarze: przypadki brzegowe
sprawdzamy na małych wzorcach, a skalę na wskazanym dużym zestawie.

### Kiedy implementacja jest odebrana

Wymagane są wyniki dla obu systemów, testy kontraktów i ręczny scenariusz,
MPP odczytany bez utraty liczb/metadanych, oba AVI odtworzone w VLC oraz
spełnione kryteria danych i płynności. Raport podaje commit aplikacji,
środowisko, manifest danych, metodę rejestracji/urządzenie, parametry eksportu,
wyniki, czasy i zużycie zasobów. Rozróżnia `zaliczone`, `niezaliczone`,
`niewykonane` i `nie dotyczy`; brak środowiska lub danych nie jest sukcesem.

Nie blokują odbioru: brak dodatkowej próby WSxM oraz potrzeba późniejszego
strojenia skuteczności rejestracji na trudnych pomiarach. Blokują go błędy
kontraktu aplikacji, utrata danych, niepoprawna geometria, niedziałające
wymagane eksporty lub brak wymaganego sprawdzenia jednego z systemów.

Obecnie aplikacja pozostaje szkieletem. W tej sesji wykonano rozpoznanie
opisane w [inwentarzu](../acceptance-reconnaissance.md) i kontrolę dokumentacji;
nie wykonano powyższego odbioru. Nie uruchamiano produkcyjnego GUI, Windows,
VLC, WSxM, dużych benchmarków ani modelu GPU.
