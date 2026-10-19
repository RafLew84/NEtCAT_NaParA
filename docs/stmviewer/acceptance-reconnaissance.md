# Dane i środowisko do odbioru STM Viewer

Rozpoznanie: 2026-10-19, baza Viewer `7cfc154`. To sprawdzone lokalnie fakty,
nie wynik odbioru aplikacji ani zatwierdzony zakres jej wydajności.
Decyzje: [Dane i kryteria odbioru pierwszej wersji](issues/06-acceptance.md).

## Dostępne pomiary

Katalog danych: `/home/rlew/projekty/NEtCAT-domains/data/`.
Worktree Viewer nie ma własnego `data/`. Dane pozostają lokalne, poza Git;
przyszłe uruchomienie odbioru powinno wskazywać katalog danych jawnie.
Poniższe ścieżki są względne wobec tego katalogu, wymiary to szerokość × wysokość.

| Plik | Klatki | Wymiary [px] | Rozmiar [MiB] |
| --- | ---: | ---: | ---: |
| `nanotrack_registration/trudne/MOVIE_4.mpp` | 364 | 256 × 256 | 182,01 |
| `nanotrack_registration/trudne/MOVIE_8.mpp` | 84 | 512 × 512 | 168,00 |
| `TTMAPP/MOVIE_23raw_TTMAPP_I_AU111.MPP` | 268 | 256 × 256 | 134,01 |
| `TTMAPP/TTMAPP_AU111/movie2/MOVIE_2.MPP` | 196 | 256 × 256 | 98,01 |
| `TTMAPP/TTMAPP_AU111/movie3/MOVIE_3.MPP` | 162 | 256 × 256 | 81,01 |
| `MOVIE_3.MPP` — kanał Current | 17 | 256 × 256 | 8,50 |
| `MOVIE_1.MPP` | 36 | 301 × 268 | 22,16 |
| `MOVIE_3_magma_drift.MPP` | 21 | 305 × 307 | 15,01 |
| `MOVIE_3_drift_corr__flatten_calibrated_magma_removed_2_first frames.MPP` | 137 | 277 × 279 | 80,78 |
| poprzedni plik z końcówką `_0_71frames.MPP` | 72 | 277 × 279 | 42,46 |

W całym katalogu znaleziono 872 STP, 370 S94 i 12 MPP: łącznie
1 621 825 972 bajtów, 1254 osobne inode i ścieżki rzeczywiste. Wszystkie
STP/S94 mają według nagłówków 256 × 256 px. Serie STP: korzeń — 371 plików,
`TTMAPP/TTMAPP_AU111/movie2/` — 196, `movie3/` — 162; pozostałe katalogi
`m1`, `m2`, `m3` obejmują odpowiednio 42, 41 i 60 plików.
Korzeń zawiera także alternatywny `converted_85291r.stp` obok `85291r.STP`;
liczba plików nie oznacza liczby niezależnych pomiarów.

Dwa filmy TTMAPP (268 klatek i `movie2/MOVIE_2.MPP`) mają prawdopodobne kopie
w `nanotrack_registration/dobre/`. Zgodne są rozmiary i trzy próbki po
4096 bajtów z początku, środka i końca. Nie wykonywano pełnych hashy;
nie potwierdzono identyczności wszystkich bajtów i nie traktujemy tych
par jako dodatkowych niezależnych przypadków.

Odczytano nagłówki, rozmiary i krótkie próbki. Nie wczytywano całych filmów,
nie sprawdzono wszystkich wartości/NaN ani poprawności kalibracji. Znane
z wcześniejszego rozpoznania pary `17851.STP`/`17851.S94` oraz
`17544.STP`/`17544.S94` nadają się do porównania ścieżek odczytu.
Parametry 1000 nm i zera w eksporcie TTMAPP są według użytkownika zastępcze;
nie służą jako wzorzec kalibracji ani rzeczywistych czasów pomiaru.

## Komputer i programy

- Ubuntu 24.04.4 LTS x86_64, kernel `7.0.0-38-generic`.
- Zgłoszony CPU: `AMD Ryzen 9 9950X3D2 16-Core Processor`, 32 logiczne CPU.
- RAM: 129498124 kB (`MemTotal`), około 123,50 GiB; swap około 8 GiB.
- Dostępne środowisko conda `netcat` opisano w [rozpoznaniu kodu](reconnaissance.md).
  To mocny komputer rozwojowy, nie potwierdzone minimum sprzętowe.

Nie znaleziono VLC, mpv, ffplay/ffmpeg/ffprobe, Totem, Celluloid, Parole,
SMPlayer, MPlayer, Haruna, Wine ani WSxM w PATH ani odpowiadających pakietów
`dpkg`. Sprawdzono też `netcat/bin`, brak `~/.wine`, zawartość `/opt`
i pusty `~/.local/share/applications`. Flatpak niedostępny; `snap list`
nie zakończył się w 5 s, więc instalacji Snap nie ustalono. To opis zakresu
poszukiwań, a nie dowód braku wszelkich możliwych instalacji.

Nie uruchamiano zewnętrznego odtwarzacza, WSxM ani Windows. OpenCV może
korzystać z własnego FFmpeg pomimo braku polecenia `ffmpeg` w PATH;
wcześniejsza [próba AVI](avi-export-reconnaissance.md) dotyczyła takiego zapisu.
Oficjalna [lista funkcji VLC](https://images.videolan.org/vlc/features.html)
wymienia AVI i MJPEG, a [kod VideoLAN](https://github.com/videolan/vlc/blob/master/src/misc/fourcc_list.h)
zawiera również FFV1. Uzasadnia to wybór kandydata do próby; nie potwierdza
jeszcze odtworzenia naszego pliku w konkretnej wersji na obu systemach.

## GPU i zakres obliczeń

`/proc/driver/nvidia/gpus/0000:01:00.0/information` identyfikuje NVIDIA GeForce
RTX 5090, a `lspci` potwierdza urządzenie NVIDIA `2b85`. Nie potwierdzono
VRAM tej karty ani dostępności CUDA: `nvidia-smi` zakończył się kodem 9
z informacją o braku komunikacji ze sterownikiem. Wynik dotyczy tego
środowiska; nie ustalono przyczyny. Dodatkowy GPU AMD raportuje w sysfs
2147483648 bajtów (2 GiB).

[Deep Matcher](../../nanotrack/registration/deep_matcher.py) obsługuje `auto`,
`cpu` i `cuda`. `auto` wybiera CUDA wyłącznie przy pozytywnym
`torch.cuda.is_available()`. Pozostałe backendy Phase, Tile+RANSAC, ECC
i Optical Flow oraz materializator aligned korzystają z operacji na CPU.
Sama obecność GPU nie przyspiesza ich obecnych implementacji. Nie uruchamiano
modeli, nie sprawdzano rzeczywistych wag ani nie pobierano plików.

## Istniejące testy i ich granice

- [Składanie serii](../../tests/nanotrack/test_sequence_loader.py): 11 testów
  z mockowanymi czytnikami; nie dowodzą dekodowania prawdziwych STP/S94.
- [Loader MPP](../../tests/nanotrack/test_mpp_loader.py): 4 testy. Jeden wymaga
  `data/MOVIE_3.MPP` i nie pomija się przy jego braku. W tym worktree pliku
  nie ma; trzeba świadomie udostępnić dane podczas odbioru lokalnego.
- Backendy Phase, Tile+RANSAC, ECC, Optical Flow i Deep Matcher: 22 testy
  syntetyczne. Deep Matcher korzysta z `FakeMatcher`, a nie rzeczywistych
  wag; ECC pomija testy bez OpenCV.
- [Batch](../../tests/nanotrack/test_registration_batch.py),
  [expanded aligned](../../tests/nanotrack/test_registration_aligned.py),
  [view](../../tests/nanotrack/test_registration_view.py) i
  [preview](../../tests/nanotrack/test_registration_preview.py): 27 testów
  syntetycznych znaku/sumowania przesunięć, paddingu, geometrii i niemutowania
  oryginałów. Nie wszystkie używane w starym preview zachowania są kontraktem Viewera.
- [Dialog wyników](../../tests/nanotrack/test_registration_results_dialog.py):
  3 testy Qt z `QT_QPA_PLATFORM=offscreen`; nie zastępują ręcznej próby GUI.
- [Rejestracja MolTrack](../../tests/moltrack/test_registration.py) i
  [współrzędne](../../tests/moltrack/test_registered_coordinates.py) pomagają
  sprawdzać odbiorców wspólnego kodu. MolTrack obecnie kasuje wynik po usunięciu
  klatki; Viewer ma zachowywać gotowe dopasowanie pozostałych obrazów.

`tests/stmviewer/` nie zawiera jeszcze testów. Nie znaleziono bezpośrednich
testów czytników STP/S94 ani odbioru ponownego odczytu eksportowanego MPP/AVI.
Nie ma katalogu `tests/napara/`. W tej sesji testów nie uruchamiano.
Spis nie stanowi raportu przejścia testów ani potwierdzenia działania Viewera.
