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
