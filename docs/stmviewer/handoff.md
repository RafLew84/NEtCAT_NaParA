# Przekazanie — gotowa specyfikacja STM Viewer

Data: 2026-10-19
Gałąź: `viewer/start`
Baza bieżącej zmiany: `7cfc154`
Commit zamykający: identyfikator w końcowej wiadomości sesji.

## Wynik i stan mapy

Rozstrzygnięto [Dane i kryteria odbioru pierwszej wersji](issues/06-acceptance.md#answer).
Wszystkie sześć ticketów i [mapa](map.md) są zamknięte. Gotowy jest kontrakt
pierwszej wersji, nie implementacja. Kod `stmviewer/` nadal jest szkieletem.
Nie pozostały decyzje produktowe blokujące rozpoczęcie implementacji;
prace techniczne i odbiór działającego programu są następnym etapem.

Uzgodniono Ubuntu 24.04 i Windows 11, start z repozytorium/Pythona,
16 GB **wolnego** RAM, SSD i NVIDIA/CUDA z minimum 8 GB VRAM. Rzeczywiste
pomiary uzupełnia seria 1000 × 512 × 512; wymagane 5 kl./s i reakcja na
wybór/Pause do 250 ms w co najmniej 95% prób. Przy większym obciążeniu Play
zwalnia bez pomijania klatek. Długie operacje mają postęp i anulowanie,
a ich czas jest raportowany bez sztywnego limitu.

MPP wymaga dokładnego ponownego odczytu wartości i metadanych. AVI MJPG/FFV1
trzeba odtworzyć w VLC na obu systemach. WSxM pozostaje dodatkową próbą,
która nie blokuje pierwszego odbioru; nie deklarujemy niezweryfikowanej zgodności.
Zaktualizowano odnośniki w kontrakcie MPP i podglądu oraz pojęcie zadanego
tempa odtwarzania w słowniku. Pełny ręczny scenariusz znajduje się w tickecie
odbioru; nie jest listą już zaliczonych sprawdzeń.

Zmiana obejmuje wyłącznie dokumentację. Nie wdrożono importerów, UI,
rejestracji ani eksporterów i nie zmieniono współdzielonych modułów.
Prototyp podglądu pozostaje osobno w wersji `efb7e50`; nie jest aplikacją.

## Wykonane sprawdzenia i ograniczenia

- Sprawdzono branch/status/worktree, instrukcje, mapę, zamknięte kontrakty
  i istniejące testy. Zachowano pierwotne pytanie ticketu.
- Przeprowadzono odczyt nagłówków, rozmiarów oraz krótkich próbek lokalnych
  pomiarów. [Inwentarz](acceptance-reconnaissance.md) opisuje 872 STP,
  370 S94 i 12 MPP oraz prawdopodobne kopie. Nie czytano całych dużych filmów
  i nie wykonywano pełnych hashy ani oceny kalibracji wszystkich plików.
- Sprawdzono lokalny system, CPU/RAM, dostępne programy oraz ścieżki GPU
  w kodzie. Lokalnie Ubuntu 24.04.4 i około 123,5 GiB RAM. Wykryto RTX 5090,
  ale `nvidia-smi` nie komunikował się ze sterownikiem; nie potwierdzono
  VRAM tej karty, działania CUDA ani wag. Nie diagnozowano przyczyny.
- Nie znaleziono zewnętrznego odtwarzacza/WSxM w sprawdzonych miejscach.
  Nie instalowano programów, nie pobierano wag i nie modyfikowano danych.
- Sprawdzono 154 lokalne odnośniki/kotwice, zamknięcie sześciu ticketów
  i mapy, brak cykli zależności oraz niezmienność wszystkich pytań względem
  `7cfc154`. `git diff --check` przeszedł; kod produkcyjny pozostaje bez zmian.

W tej sesji nie uruchamiano testów aplikacji, produkcyjnego GUI, Windows,
VLC/WSxM, dużych benchmarków ani modelu GPU. Nie można na tej podstawie
uznać implementacji za odebraną. Wcześniejsze małe próby są opisane osobno
w [rozpoznaniu kodu](reconnaissance.md), [raporcie MPP](wsxm-mpp-compatibility.md)
i [raporcie AVI](avi-export-reconnaissance.md). FFV1/MJPG potwierdzono tam
przez OpenCV/FFmpeg, bez odbioru w zewnętrznym odtwarzaczu.

## Podział pracy z sesją integracyjną

Własna implementacja należy do `stmviewer/` i `tests/stmviewer/`. Zmiany
`napara/`, `nanotrack/`, `moltrack/`, `stmbrowser/` oraz konfiguracji głównej
prowadzi sesja integracyjna. Poniższe punkty są wymaganiami wobec wspólnego
kodu lub granicy adaptera; nie oznaczają zgody na zmianę innych worktree
w trakcie ich pracy. Nie należy kopiować niezgodnego zachowania starych
aplikacji do Viewera tylko dlatego, że istnieje już helper.

| Obszar | Potrzeba do uzgodnienia lub wykonania przez integrację |
| --- | --- |
| Czytniki STP/S94 i jednostki | Rozpoznać rzeczywiste pola kanału/offsetów STP; zachować surowe liczby i jednostki sygnału niezależnie od skali X/Y. Zweryfikować kalibrację i kolejność bajtów S94, w tym nieznane wzmocnienie. Nie normalizować double według samego Z Amplitude. |
| MPP: orientacja i czasy | Ustalić jawną granicę obrotu między czytnikiem i loaderem, aby ścieżki STP/S94/MPP zachowały orientację po zapisie. Poprawić interpretację jednostek czasu i częściowych braków; nie tworzyć czasu z FPS. Sprawdzić dotychczasowych odbiorców. |
| MPP: duże nagłówki i metadane | Usunąć/dostosować ukryty limit 1000 linii, aby obsłużyć przyjęte duże serie. Zachować parametry per klatka i nieznane wartości; ustalić adapter wersjonowanego dodatku powiązanego z treścią filmu. Nie przypisywać metadanych pierwszej klatki całej serii. |
| Rejestracja i zadania w tle | Udostępnić kontrolowane anulowanie na bezpiecznych granicach, postęp i kompletne wyniki bez wiązania obliczeń z UI. Stary wynik musi przetrwać błąd nowego. Nie kopiować synchronicznego dialogu NanoTrack, który kasuje wynik po błędzie. |
| Deep Matcher | Zapewnić sprawdzenie lokalnych zależności/wag i ich wczytanie bez pobierania. Obecne LoFTR pretrained może pobrać brakujący plik. Jawnie sprawdzać dostępność urządzenia i raportować błędy; sam test FakeMatcher nie wystarcza. |
| Expanded aligned | Zachować pełny obszar, NaN, translacje i historyczne odniesienie oraz osobny prostokąt źródła i maskę ważności. Obecne wspólne metadane materializatora wymagają adaptera dla różnych kalibracji. Nie używać preview, który obcina obraz i powiela brzeg. |
| Zależności i platformy | Minimalny plik wymagań zawiera tylko PyQt6. Potrzebny sprawdzony zestaw NumPy/SciPy/scikit-image/pyqtgraph/OpenCV, a opcjonalnie Torch/Kornia/CUDA i lokalne wagi, z instrukcją obu systemów. Uruchomić rzeczywiste próby kodeków na obu platformach. |
| Testy odbiorców | Zmiana wspólnego modułu wymaga testów jego odbiorców. Istniejące loadery mockują czytniki, test MPP wymaga nieobecnego tutaj data/MOVIE_3.MPP, a testy MolTrack zakładają kasowanie rejestracji po usunięciu. Zachować ich odrębne kontrakty; dodać rzeczywiste próby wejścia/wyjścia. |

Źródła ograniczeń i odnośniki do kodu: [rozpoznanie](reconnaissance.md).
Wybranie miejsca adaptera i szczegółów API jest pracą implementacyjną;
nie trzeba otwierać kolejnej mapy, aby rozstrzygać rutynowe szczegóły kodu.
Jeżeli wspólna zmiana nie jest jeszcze dostępna, kontynuować niezależne
prace Viewera i zgłosić konkretną zależność w kolejnym przekazaniu.

## Własne moduły i odbiór do wykonania

- Model serii z trwałym powiązaniem klatek, pochodzenia, czasów i kalibracji;
  import wymienia stan dopiero po sukcesie. Usuwanie zachowuje gotowe aligned,
  jego obszar i historyczne odniesienie; brak odwracania kolejności.
- Podgląd wybranego układu B, Play/Pause, filmstrip, gamma/zoom i prezentacja
  maski. Oddzielić zadane tempo od rzeczywiście uzyskanego; podczas Play
  nie pomijać klatek. Nie generować wszystkich dużych rastrów filmu w pamięci
  wyłącznie na potrzeby miniatur lub odtwarzania.
- Stan zadań importu/rejestracji/eksportu, postęp i anulowanie; spójny zestaw
  klatek/parametrów dla eksportu oraz publikacja po sukcesie. Kontrolowane
  błędy muszą obejmować też etap budowy aligned i zapis dodatku MPP.
- MPP float64/NaN i powiązany dodatek: wartości niezależne od prezentacji,
  kompletna geometria i metadane, walidacja zgodności pary po odczycie.
  Dwa pliki nie są jedną atomową operacją; błędnego dodatku nie stosować.
- Renderer AVI pełnych klatek, kontrast tylko z ważnych próbek, gamma,
  proporcje, maska, tła i opisy; dopełniać nieparzyste wymiary zamiast obcinać.
  FFV1 zachowuje raster uint8, a nie wartości pomiarowe. Nie przechwytywać okna.
- Przeprowadzić pełny [odbiór](issues/06-acceptance.md#answer), z manifestem
  danych i osobnymi wynikami Ubuntu/Windows. Zanotować faktyczne zużycie
  zasobów oraz dostępność metod, a niewykonane próby oznaczyć jawnie.

Nie tworzono nowych ticketów decyzyjnych: pozostały zadania implementacji,
integracji i sprawdzenia gotowego programu, poza celem zakończonej mapy.
