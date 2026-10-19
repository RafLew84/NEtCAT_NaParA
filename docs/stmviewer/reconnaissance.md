# Rozpoznanie istniejącego kodu

Stan: 2026-10-14, baza `0e8bc53`, worktree `NEtCAT-viewer`.
To fakty z kodu i lokalnych sprawdzeń, nie przyjęta specyfikacja STM Viewer.

## Wczytywanie i metadane

- [`load_stm_sequence`](../../nanotrack/io/sequence_loader.py) przyjmuje jeden MPP
  albo wiele STP/S94, także mieszanych. Zachowuje kolejność przekazanych ścieżek,
  opcjonalnie ją odwraca. Wymaga jednakowych wymiarów obrazów.
- Loader nie waliduje zgodności skali fizycznej i kanału. Główne metadane bierze
  z pierwszej klatki, a surowe nagłówki wszystkich plików zachowuje osobno.
  Czasy serii STP/S94 pozostają nieznane; MPP ma obsługę Frames Synchronization.
- [`read_stp_file`](../../napara/io/stp_reader.py) obraca dane o 180 stopni.
  [`read_mpp_file`](../../napara/io/mpp_reader.py) nie obraca danych; obrót dodaje
  [`load_mpp_sequence`](../../nanotrack/io/mpp_loader.py). Eksport wymaga jawnego
  kontraktu orientacji i sprawdzenia ponownego odczytu.
- Czytniki STP/MPP używają float64. [`read_s94_file`](../../napara/io/s94_reader.py)
  przelicza int16 na float32, dla znanych kanałów odpowiednio na nm lub nA.
  Nie ma jednego jednoznacznego pola jednostki wartości we wszystkich modelach.
- Odczyt fixture `tests/moltrack/fixtures/ttmapp_domain_analysis_sources/movie2/34855.STP`
  daje offset `(0, 0)` i kanał `Unknown`, mimo obecnych w surowym nagłówku
  `X-Offset`, `Y-Offset` i `Acquisition channel`. Czytnik rozpoznaje inne nazwy
  pól. Przed oparciem eksportu na tych metadanych potrzebne jest ustalenie
  kontraktu i ewentualna poprawka w sesji integracyjnej.

## Podgląd

- [`ViewerWidget`](../../napara/gui/widgets/viewer_widget.py) oferuje zoom/pan,
  osie, histogram, poziomy i gamma. `set_image` pozwala zachowywać zoom;
  `set_gamma` zmienia LUT, nie dane pomiarowe.
- NaN są zastępowane medianą wyłącznie w kopii do wyświetlenia. Obecny widget
  nie pokazuje więc pustych obszarów jako czarnych z samego faktu użycia NaN.
- [`SequenceViewerWidget`](../../nanotrack/ui/widgets/sequence_viewer_widget.py)
  dodaje do wspólnego viewera obsługę ROI i trackingu. STM Viewer nie potrzebuje
  całego tego zakresu. W przejrzanym UI NanoTrack nie znaleziono Play/Pause/FPS.

## Rejestracja

- [`NanoTrackMainWindow`](../../nanotrack/ui/main_window.py) uruchamia jeden
  wybrany backend: Phase (domyślny), Tile+RANSAC, ECC, Optical Flow lub Deep Matcher.
  Ustawienia UI to `raw` i `adjacent`. Wynikiem jest globalna translacja XY.
- [`run_adjacent_phase_registration`](../../nanotrack/registration/batch.py)
  obsługuje różne backendy mimo nazwy. Przyjmuje stos `(N, H, W)` ze skończonymi
  wartościami. Sumuje przesunięcia sąsiednich uwzględnionych klatek względem
  pierwszej uwzględnionej klatki.
- [`build_expanded_aligned_frames`](../../nanotrack/registration/aligned.py)
  tworzy osobny stos float32 z domyślną interpolacją liniową i NaN poza pomiarem.
  Zwraca także padding, przesunięcie płótna i przeliczone metadane. Zachowuje
  rozmiar piksela, powiększa obszar fizyczny i aktualizuje offset.
- W NanoTrack oryginały pozostają osobno, aligned jest wyliczanym widokiem.
  Ponowna rejestracja korzysta z oryginałów. Obecny runner nie przyjmie
  wyeksportowanego aligned z NaN bez dodatkowej obsługi brakujących danych.
- ECC wymaga OpenCV; Deep Matcher używa LoFTR i wymaga torch, kornia i wag.
  Istnieją także masked phase oraz optymalizator grafu, ale nie są uruchamiane
  przez wymieniony przycisk/listę w NanoTrack.

## Eksport i środowisko

- W przejrzanym repo nie znaleziono eksportera obrazów/serii MPP ani AVI.
  Eksport wyników analiz i przesunięć jest odrębną funkcją.
- Dostępny interpreter conda netcat:
  `/home/rlew/projekty/conda-migration-ubuntu-20261008/envs/netcat/bin/python`.
- Potwierdzone importy: Python 3.12.12, NumPy 2.2.5, SciPy 1.15.2,
  PyQt6 6.9.1, pyqtgraph 0.13.7, OpenCV 4.11.0.86, pytest 8.3.5.
  OpenCV deklaruje FFmpeg. Nie sprawdzono zapisu konkretnym kodekiem AVI
  ani dostępności wag Deep Matcher.
- Minimalne `.venv` worktree zawiera PyQt6 dla szkieletu; plik zależności
  `requirements/stm-apps.txt` nie obejmuje pełnego zestawu zależności rejestracji.

## Sprawdzenia i ograniczenia

Przeczytano kod i istniejące testy, wykonano importy w netcat oraz odczyt
wskazanej fixture STP. Nie uruchamiano zestawu testów, GUI ani rejestracji.

Istnieją testy [loadera](../../tests/nanotrack/test_sequence_loader.py),
[MPP](../../tests/nanotrack/test_mpp_loader.py),
[rejestracji serii](../../tests/nanotrack/test_registration_batch.py),
[powiększonego obszaru](../../tests/nanotrack/test_registration_aligned.py)
i [okna NanoTrack](../../tests/nanotrack/test_main_window.py).
Test z rzeczywistym `data/MOVIE_3.MPP` wymaga lokalnego pliku, którego nie ma
w tym worktree. Ocena skuteczności rejestracji wymaga danych i odrębnych kryteriów.

## Uzupełnienie: seria i usuwanie klatek

Sprawdzenie z 2026-10-16, baza `1f28b63`. Przeczytano implementacje i testy;
wykonano trzy próby w pamięci. Nie zmieniano kodu istniejących aplikacji.

- [`MolTrackImageSeries.remove_frame`](../../moltrack/core/data_models.py)
  usuwa obraz i jego indeks źródłowy, wybiera następną klatkę albo poprzednią
  po usunięciu ostatniej. Odrzuca usunięcie jedynej klatki. Nowy kontrakt
  STM Viewer wymaga również obsługi pustego programu po takim usunięciu.
- Usunięcie nie aktualizuje czasów w metadanych. Próba: obrazy `[0, 1, 2]`
  z czasami `[10, 20, 30]` po usunięciu środka dają obrazy `[0, 2]`, lecz nadal
  trzy czasy. [Odtworzenie sesji MolTrack](../../moltrack/persistence/session_store.py)
  również wybiera podzbiór obrazów z pełnymi metadanymi źródła. Obecne
  [testy modelu](../../tests/moltrack/test_data_models.py) nie sprawdzają czasów.
- [Sesja NanoTrack](../../nanotrack/persistence/session_store.py) zapisuje dla
  odwróconej serii STP/S94 zarówno odwrócone ścieżki, jak i znacznik odwrócenia.
  Odtworzenie ponownie odwraca kolejność: próba `[b, a]` daje `[a, b]`.
  [Testy sesji](../../tests/nanotrack/test_session_store.py) nie obejmują tego
  przypadku z rzeczywistym loaderem. Nie jest to wymaganie dodania zapisu sesji
  do STM Viewer, lecz ograniczenie ponownego użycia istniejącego kodu.
- Próba importu obrazów o tych samych wymiarach, różnych skalach 10/100
  i kanałach Topography/Current potwierdza akceptację oraz wspólne metadane
  z pierwszej klatki. Nie istnieje tolerancja zgodności skali. Nagłówki źródłowe
  pozostają osobno; metadanych pierwszej klatki nie można utożsamiać
  z metadanymi każdej klatki takiej serii.
- `load_stm_sequence` przerywa import przy błędzie źródła. Inny helper,
  [`load_from_paths`](../../napara/io/factory.py), pomija błędne pliki;
  nie spełnia więc przyjętego kontraktu odrzucenia całego importu.

Rozstrzygnięcie zachowania nowej aplikacji:
[Seria wejściowa i usuwanie klatek](issues/01-frame-series.md).

## Uzupełnienie: rejestracja i geometria wyniku

Sprawdzenie z 2026-10-19, baza `db4cc7c`. Przegląd kodu i testów oraz dwie
małe próby w pamięci, bez uruchamiania modeli, pobierania wag i zmian w kodzie.

- [`run_adjacent_phase_registration`](../../nanotrack/registration/batch.py)
  obsługuje wyłącznie pary sąsiednie w bieżącej kolejności. Pierwsza klatka
  ma przesunięcie `(0, 0)`, pozostałe sumę przesunięć par względem niej.
  Inna strategia odniesienia jest odrzucana. Wyjątek backendu przerywa batch.
- Status `low_confidence` może towarzyszyć pełnym, skończonym przesunięciom.
  Statusy problemów propagują się przez łańcuch dopasowań na dalsze klatki;
  jakość globalna jest minimum jakości dotychczasowych par. Wstrzyknięty
  backend zwracający kolejno `low_confidence` i `ok` dał statusy
  `[ok, low_confidence, low_confidence]` przy skończonych przesunięciach.
- [UI NanoTrack](../../nanotrack/ui/main_window.py) usuwa poprzedni wynik
  przy błędzie nowej próby. Dostępny callback postępu jest wywoływany po
  klatkach, lecz batch nie ma API anulowania, a dialog NanoTrack nie udostępnia
  Anuluj. Obliczenia UI są synchroniczne z przetwarzaniem zdarzeń w callbacku.
- Globalne przesunięcia można zachować po usunięciu lub odwróceniu klatek,
  wiążąc je z ich pochodzeniem i dotychczasowym układem odniesienia. Wybranie
  podzbioru/przestawienie gotowych aligned w niezmienionym obszarze nie wymaga
  ponownej interpolacji. [MolTrack](../../moltrack/core/data_models.py) obecnie
  unieważnia rejestrację po usunięciu; [model wyników](../../nanotrack/core/data_models.py)
  używa bieżących indeksów i nie udostępnia gotowej operacji usuwania/odwracania.

### Geometria i wartości

[`build_expanded_aligned_frames`](../../nanotrack/registration/aligned.py)
zwraca rozszerzony obszar, padding i położenia oryginalnych klatek. Domyślne
próbkowanie jest liniowe, wynik float32, a brakujące próbki mają wartość NaN.
`shift_xy = (dx, dy)` oznacza przesunięcie nanoszone na obraz ruchomy:
dodatnie X w prawo, dodatnie Y w dół. Nie jest to zaobserwowany dryf obrazu
(patrz [kontrakt phase correlation](../../nanotrack/registration/phase_correlation.py)).
Pozycja klatki w rozszerzonym obszarze to `(left + dx, top + dy)`.
Padding obejmuje skrajne przesunięcia z zaokrągleniem na zewnątrz.

**Pole oryginalnej klatki i ważne próbki aligned to różne informacje.**
Próba z obrazem o wymiarach 3 wiersze × 4 kolumny i nanoszonym przesunięciem
`(dx=0,25; dy=0,5)` px dała rozszerzony obszar 4 × 5. Prostokąt pomiaru nadal miał
3 × 4, lecz skończone próbki występowały jedynie w `y=1,2`, `x=1,2,3`.
Interpolacja z NaN poza danymi nie ekstrapoluje pomiaru na brzegu.
Obrys wynika z wymiarów i przesunięcia; maska ważności opisuje próbki wyniku.
Nie należy wyznaczać pola oryginalnej klatki przez liczenie skończonych próbek.

Uproszczone [`build_aligned_frames`](../../nanotrack/registration/preview.py)
nie rozszerza obszaru i powiela wartości na brzegu (`mode="nearest"`), więc
nie spełnia wymagań pełnego obszaru i brakujących pikseli dla STM Viewer.
Materializator expanded przyjmuje jedne metadane serii; przelicza rozmiar
fizyczny i offset według jednej skali. Samo dopasowanie działa w pikselach.
Nie zapewnia to kontraktu różnych metadanych dla każdej klatki.

### Dostępność metod

[`Deep Matcher`](../../nanotrack/registration/deep_matcher.py) tłumaczy brak
`torch`/`kornia` na czytelny wyjątek, ale nie ma sprawdzenia dostępności przed
startem. Inicjalizuje LoFTR z `pretrained="outdoor"`. Sprawdzenie lokalnych
źródeł Kornia (`feature/loftr/loftr.py`) i Torch (`hub.py`) w środowisku netcat
potwierdziło wywołanie `load_state_dict_from_url`: przy braku pliku w cache
może nastąpić pobranie wag. Nie uruchamiano tej ścieżki. Obecność pliku cache
jest tylko wstępnym sprawdzeniem i nie dowodzi, że model da się załadować.

### Zakres potwierdzenia

Przeczytano, ale nie uruchamiano testów
[batch](../../tests/nanotrack/test_registration_batch.py),
[expanded aligned](../../tests/nanotrack/test_registration_aligned.py)
i [rejestracji MolTrack](../../tests/moltrack/test_registration.py).
Obejmują m.in. kumulację i znak przesunięć, postęp, propagowanie jakości,
padding, geometrię, niemutowanie oryginałów i unieważnianie po usunięciu.
Dwie własne próby dotyczyły maski próbek po przesunięciu subpikselowym oraz
propagowania `low_confidence`. Nie oceniano jakości dopasowania danych
pomiarowych ani działania GUI.


Rozstrzygnięcie: [Rejestracja i życie wyniku aligned](issues/03-registration.md#answer).
Po rozpoznaniu użytkownik wycofał odwracanie kolejności z STM Viewer;
powyższe fakty o tej funkcji dotyczą istniejącego kodu i wcześniejszej analizy,
nie aktualnych wymagań nowej aplikacji.

## Uzupełnienie: kontrakt odczytu MPP

Sprawdzenie z 2026-10-19, baza `5412dbb`. Fakty stanowią podstawę otwartego
[Zapisu MPP z wartościami i metadanymi](issues/04-mpp-export.md);
nie są jeszcze uzgodnionym kontraktem eksportu.

### Nagłówek, wartości i metadane

- [Czytnik MPP](../../napara/io/mpp_reader.py) czyta sekcje z parami
  `Key: Value` do `[Header end]`, maksymalnie przez 1000 linii. Nie korzysta
  z deklarowanego rozmiaru nagłówka w bajtach. Wymiary i liczba klatek
  pochodzą z `General Info`; kolejne klatki to macierze float64 little endian,
  wierszami. Deklaracja `Image Data Type` nie zmienia obecnego odczytu.
- Nieznane sekcje i pola trafiają do `raw_header`. Próba potwierdziła
  zachowanie jednoliniowego JSON w dodatkowym polu. To techniczna możliwość
  rozszerzenia, a nie dowód zgodności z programami zewnętrznymi.
- Rozmiar fizyczny, offset, kanał, kąt, bias i setpoint są wspólne dla filmu.
  Czytnik nie interpretuje metadanych per klatka, pochodzenia, jednostki
  wartości, rejestracji ani pola oryginalnej klatki. Wersjonowane rozszerzenie
  wymagałoby nowego adaptera lub wspólnej zmiany czytnika.
- NaN przechodzi przez odczyt bez zastępowania zerem. Maska skończonych próbek
  nie wystarcza do odzyskania oryginalnego pola klatki ani wartości oryginału
  sprzed interpolacji. Zapis float64 nie odzyska precyzji wcześniej utraconej
  podczas obliczeń aligned lub odczytu S94 do float32.
- Sam czytnik MPP zachowuje kolejność elementów macierzy;
  [loader NanoTrack](../../nanotrack/io/mpp_loader.py) obraca każdą o 180 stopni.
  Oba punkty startowe NaPara i NanoTrack ustawiają wyświetlanie row-major.
  Ponowny odczyt wymaga kontroli orientacji na asymetrycznym obrazie;
  w tej próbie nie sprawdzano końcowego obrazu w GUI.

### Czasy i usunięte klatki

[Parser czasu](../../nanotrack/io/mpp_loader.py) oczekuje kluczy
`Frame 0000` do `Frame N-1`. Próba eksportowego podzbioru z kluczami 0 i 2
przy dwóch klatkach dała `KeyError`; konieczne jest rozdzielenie pozycji
wyjściowej od numeru źródłowego. Wartości czasów można zachować z przerwami.

Brak jednego czasu powoduje utratę całej tablicy czasów w modelu.
Parser odczytuje samą liczbę: napis `10 ms` interpretuje jako 10 sekund;
zerowe czasy wszystkich klatek akceptuje. Nie należy wyznaczać czasu pomiaru
z tempa odtwarzania ani uznawać zera automatycznie za potwierdzony pomiar.
Standardowe wpisy czasów również zużywają limit 1000 linii nagłówka.

### Jednostki wejścia

Lokalne próbki STP/MPP mają nagłówki WSxM (Nanotec Electronica/UAM), mimo
określenia „Omicron” w docstringach czytników. Dokumentacja
[SPM Images UAM](https://spmimages.ftmc.uam.es/file-specifications/)
opisuje STP z typem danych i jednostką wartości w nagłówku; nie stanowi
pełnej specyfikacji filmu MPP ani gwarancji odbioru NaN.

[Czytnik STP](../../napara/io/stp_reader.py) zachowuje wartości float64 i obraca
macierz o 180 stopni, lecz nie modeluje jednostki wartości. W próbkach
`17851.STP` i `17544.STP` zakres danych wynosi odpowiednio 4,619140625 oraz
1,697265625, mimo `Z Amplitude` 4 nm i 1 nm. Minima i maksima są takie same
jak w odpowiadających S94 po kalibracji do nm. Dla tych próbek normalizacja
wartości do liczby z `Z Amplitude` zmieniłaby pomiar. Rozbieżność nazw pól
`Acquisition channel`/`Channel` i `X-Offset`/`X Offset` potwierdza wcześniejszą
potrzebę poprawienia metadanych czytnika STP.

[Czytnik S94](../../napara/io/s94_reader.py) daje nm dla topografii ze znanym
wzmocnieniem i nA dla prądu. Przy nieznanym wzmocnieniu lub trybie zachowuje
surowe liczby; oznaczenie ich jako nm byłoby błędne. Obecne modele nie mają
jednoznacznego pola jednostki wartości ani pewności metadanych.

### Zakres sprawdzenia

Wykonano małą próbę dwóch klatek 2 × 3: wartości i NaN, obrót w loaderze,
rozmiar fizyczny i offset, dodatkowe pole nagłówka, kompletne/niekompletne
czasy, nieciągłe indeksy czasu, jednostkę ms, zerowe czasy i limit nagłówka.
Przeczytano też nagłówki i wybrane wartości lokalnych STP/S94/MPP z
`/home/rlew/projekty/NEtCAT-domains/data/`: `MOVIE_3.MPP`,
`TTMAPP/MOVIE_23raw_TTMAPP_I_AU111.MPP` oraz pary `17851` i `17544` STP/S94.
Kod importowano z worktree Viewer w środowisku conda netcat. Syntetyczny
probe wykonano inline; jego katalog tymczasowy został automatycznie usunięty.
Nie uruchamiano pełnego zestawu testów, GUI ani zewnętrznego WSxM;
nie napisano eksportera i nie potwierdzono interoperacyjności.

### Wymagany odbiorca WSxM

Po wskazaniu WSxM przez użytkownika przejrzano źródła zewnętrzne.
[Osobna notatka](wsxm-mpp-compatibility.md) zawiera odnośniki do specyfikacji
UAM, pierwotnych prób autorów/zgłaszającego Gwyddion i wersjonowanego kodu
SciFiReaders. Różnice interpretacji wartości potwierdzają, że odczyt przez
inny parser nie zastępuje testu w docelowym WSxM. Obsługa NaN i własnych
metadanych pozostaje niezweryfikowana. Nie znaleziono lokalnego programu
WSxM ani Wine w PATH i sprawdzonych typowych katalogach; nie instalowano ich.

## Uzupełnienie: film AVI

2026-10-19, baza `08c9ca6`: [rozpoznanie AVI](avi-export-reconnaissance.md)
opisuje kontrast/gamma, proporcje i sposób wyświetlania NaN w istniejącym
widgetcie oraz sześć małych prób zapisu/odczytu przez OpenCV/FFmpeg.
MJPG i FFV1 działają lokalnie, lecz cicho obcinają nieparzyste wymiary.
Jawne dopełnienie zachowuje krawędzie. Nie sprawdzono odtwarzacza docelowego,
wielkich filmów ani eksportera aplikacji. [Skrypt](experiments/avi_codec_probe.py)
generuje wyłącznie małe syntetyczne dane do katalogu tymczasowego.
