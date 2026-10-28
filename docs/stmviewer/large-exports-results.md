# Ticket 19 — raport dużych eksportów

Data: 2026-10-28. Baza kodu: `6b43765f71f28f77d1b8bf74cf2643f67e0dba15`.
Próba obejmuje poprawkę `mpp_missing.py`/`mpp_metadata.py` z commitu `6888cff`.
[Instrukcja ręcznej próby i odtworzenia pomiarów](large-exports-manual.md).
Do `done` pozostają ręczny odbiór oraz opisana niżej poprawka czytnika w integracji.
Ręczny odbiór użytkownika jest jeszcze niewykonany; opisane GUI/X11 i VLC
były sterowane skryptami, a wybrane zrzuty oceniono wizualnie.

## Znaleziona i poprawiona usterka

Pełny zapis original działał, ale aligned 1000 × 640 × 640 kończył się błędem
limitu 500 000 przedziałów braków. Ten wzorzec potrzebuje **512 998 przedziałów**.
Po zwiększeniu limitu ujawnił się drugi problem: wcięcia JSON powiększały
powtarzane nagłówki źródłowe ponad istniejący limit 64 MiB.

Poprawka podnosi limit przedziałów do **1 000 000** i zapisuje kompaktowy JSON.
Zachowuje limit 64 MiB, wersje schematu, wartości MPP, dokładne odtworzenie
braków, powiązanie SHA-256 oraz transakcyjny zapis pary. Nie dodaje nowej
opcji GUI. Szybki test publicznego zapisu/odczytu odtwarza oba błędy na 1000
wąskich klatek, bez wielogigabajtowego wzorca. Sekwencja TDD: błąd limitu
przedziałów → błąd rozmiaru dodatku → zgodność wszystkich danych i metadanych.

## Stanowisko i dane

To samo stanowisko co w [tickecie 18](large-series-results.md): Ubuntu 24.04.4,
Python 3.12.12 (`netcat`), Ryzen 9 9950X3D2, 132,61 GB RAM. NVIDIA RTX 5090
nie uczestniczyła w Phase ani eksporcie. NumPy 2.2.5, SciPy 1.15.2,
scikit-image 0.25.2, PyQt6 6.9.1 / Qt 6.9.0, OpenCV 4.11.0, psutil 7.1.3.
Dane leżą na HDD ST4000VN006 (`/dev/sda4`), z aktywnym cache systemowym.
Nie jest to pomiar zimnego SSD ani komputera ograniczonego do 16 GB RAM.

Wejście `data/large-ticket18-v2/large.mpp`: **1000 × 512 × 512 float64**,
2 097 172 569 bajtów; SHA-256:
`e8fca3386352f32e3807e3b710d2a29f3de74975615f951a071cb6059201f7eb`.
Generator v2/seed 1801, dryf 0–128 px. Skala 1 nm/px, czasy co 1,5 s.
Phase: **640 × 640**, 21,911 s; po usunięciu pierwszej i ostatniej klatki
**998 × 640 × 640**, 21,566 s. Zachowano source indices 1…998 (liczone od 0).
Stare aligned utrzymało odniesienie do pierwszej źródłowej klatki;
ponowne Phase przyjęło drugą, z nowym przesunięciem 0,0 dla odniesienia.

## Pełne eksporty przez GUI

Żaden wiersz nie jest krótkim wycinkiem. Rozmiary są w dziesiętnych MB;
czas obejmuje cały zapis (dla AVI także wewnętrzne dekodowanie kontrolne).
RSS obejmuje aplikację wraz z dziećmi, próbkowanie co 50 ms; krótsze szczyty
mogą być niedoszacowane. Pełne identyfikatory plików i indeksy są w lokalnym
`data/large-export-ticket19/report.json`.

| Plik | Klatki | Plik MB | JSON MB | Zapis s | RSS szczyt GB |
| --- | ---: | ---: | ---: | ---: | ---: |
| `full-original.mpp` | 1000 | 2097.178 | 24.034 | 21.427 | 6.071 |
| `full-original-MJPG.avi` | 1000 | 26.398 | 0.000 | 4.320 | 6.072 |
| `full-original-FFV1.avi` | 1000 | 76.498 | 0.000 | 8.894 | 6.099 |
| `full-aligned.mpp` | 1000 | 3276.826 | 40.882 | 35.760 | 6.219 |
| `full-aligned-MJPG.avi` | 1000 | 32.556 | 0.000 | 6.271 | 6.242 |
| `full-aligned-FFV1.avi` | 1000 | 76.720 | 0.000 | 11.388 | 6.324 |
| `deleted-original.mpp` | 998 | 2092.983 | 23.986 | 15.343 | 6.292 |
| `deleted-aligned.mpp` | 998 | 3270.272 | 40.800 | 35.497 | 6.336 |
| `deleted-aligned-MJPG.avi` | 998 | 31.310 | 0.000 | 5.844 | 6.352 |
| `deleted-aligned-FFV1.avi` | 998 | 75.846 | 0.000 | 11.346 | 6.440 |
| `reregistered-aligned.mpp` | 998 | 3270.272 | 40.800 | 35.852 | 10.057 |
| `reregistered-aligned-MJPG.avi` | 998 | 30.298 | 0.000 | 6.014 | 10.048 |
| `reregistered-aligned-FFV1.avi` | 998 | 76.617 | 0.000 | 12.063 | 10.112 |

AVI: 30 kl./s, wszystkie trzy opisy włączone. `full-original`: gamma 1,
kontrast osobny; `full-aligned`: gamma 2, wspólny kontrast, białe tło.
`deleted-aligned-MJPG`: gamma 1 / osobny / czarne; FFV1: gamma 2 / wspólny /
szare. `reregistered-aligned-MJPG`: gamma 2 / osobny / szare; FFV1:
gamma 2 / wspólny / białe. Podziałka 100 nm, źródłowe czasy pomiaru.
Zmiany gamma, zoomu, widoku i wybranej klatki podczas eksportu nie zmieniły
rozpoczętego filmu; porównano go z opcjami z chwili uruchomienia.

Szczyt całego przebiegu: **10,112 GB**. P95 odstępu 25-ms timera GUI we
wszystkich eksportach/próbach awarii najwyżej 66,07 ms; zaobserwowano pojedyncze
przerwy do **1,164 s**. To pomiar obsługi zdarzeń, nie czasu wyboru/Pause
z ticketu 18. Nawigacja i zmiany podglądu działały podczas każdego eksportu.

## Odczyt, wartości i odtwarzanie

- Pięć MPP: **4994 klatki**, wszystkie próbki porównane bit po bicie,
  również NaN. Pełna zgodność metadanych, czasów, pochodzenia, geometrii
  i historii rejestracji. SHA-256 każdego filmu i dodatku odpowiada raportowi.
- Osiem AVI: **7992 zdekodowane klatki**, bez braków/dodatkowych obrazów,
  właściwe wymiary i 30 kl./s. **3996 rastrów FFV1 identycznych** z publicznym
  rendererem użytym jako wzorzec zapisu (nie jest to ponowna walidacja projektu
  renderera). Dla 3996 klatek MJPG największy średni błąd wyniósł 1,244/255,
  największy p99: 7/255. Dodatkowa lokalna kontrola bloków 4 × 4 w numerze klatki
  dała maksymalnie 12/255, przy progu 20, aby średnia całego obrazu nie ukrywała
  niewłaściwego numeru. MJPG nie wymaga bezstratnej zgodności.
- Pięć MPP ponownie otwarto **przez GUI**. Rozpoczęto od pełnego aligned przy
  już załadowanej dużej serii original + aligned. Importy trwały 1,93–10,15 s,
  wszystkie pokazały przyjęty dodatek i właściwy licznik. Szczyt całego
  przebiegu ponownych otwarć: **14,120 GB**; poniżej przyjętych 16 GB, z małym
  zapasem na większe obszary/inne metadane. RSS może zawierać wolne bloki
  alokatora. Piki w osobnych procesach walidacji do 12,748 GB.
- **VLC 3.0.24 na Ubuntu** odtworzył wszystkie osiem AVI do końca, zakończył
  procesy kodem 0. Typowo 33,73–33,84 s na film 33,27–33,33 s; dwa pierwsze
  uruchomienia trwały 48,14 i 36,33 s wraz ze startem VLC. Próba używała
  programowego dekodowania i X11/Xvfb; ocenione zrzuty pokazują poprawny obraz,
  opisy, podziałkę i tła. Zrzuty są liczone od startu procesu i pierwsze dwa
  „late” nie przedstawiają samej końcówki. To nie jest potwierdzenie działania
  na fizycznym monitorze ani ręczny odbiór Windows. Równolegle do VLC działał
  pełny zestaw pytest i osobny pomiar alokacji; właściwy benchmark eksportów
  był wcześniej zakończony.

## Anulowanie, awarie i zwalnianie pamięci

Anulowanie MPP podczas zapisu: 26,7 ms od kliknięcia do zakończenia.
AVI podczas liczenia wspólnego kontrastu: 5,3 ms; podczas dekodowania
kontrolnego: 41,3 ms. SHA-256 wcześniej zapisanych filmów oraz obu plików
pary MPP pozostały identyczne. Postęp i komunikaty końcowe odpowiadały operacji.

Kontrolowane `OSError` przy publikacji dodatku **po zastąpieniu MPP** odtworzyło
poprzednią parę. Kontrolowane `MemoryError` w zewnętrznym kodeku po około
ćwierci dużego filmu zachowało poprzedni AVI. Program pokazał błąd, umożliwiał
nawigację i usunął katalogi tymczasowe. Wstrzyknięcia dotyczą granic systemu
plików/OpenCV; nie modyfikują prywatnych metod aplikacji.

Osobny `tracemalloc` rozpoczęto po wczytaniu i rejestracji, aby mierzyć **nowe**
alokacje eksportu. Dwa pełne aligned FFV1 i dwa aligned MPP po 1000 klatek:

| Format | Żywe nowe bufory NumPy po zakończeniu | Szczyt NumPy na punktach postępu | Szczyt wszystkich śledzonych alokacji |
| --- | ---: | ---: | ---: |
| FFV1, próba 1 / 2 | 0 / 0 B | 3 686 400 / 3 686 400 B | 7,828 / 7,979 MB |
| MPP, próba 1 / 2 | 0 / 0 B | 3 276 800 / 3 276 800 B | 209,070 / 209,080 MB |

Wyrenderowanie całego aligned AVI naraz wymagałoby 1 228 800 000 B samych
rastrów. Wyniki potwierdzają strumieniowy eksport i zwolnienie jego tablic.
Tracemalloc nie obejmuje wszystkich alokacji natywnych kodeka; uzupełnia go
RSS całej aplikacji. Nie wymuszano GC ani oddawania bloków alokatora systemowi.
Czasy tej instrumentowanej próby nie służą jako benchmark wydajności.

## Testy, ograniczenia i przekazanie

- Test regresji metadanych + dotychczasowe testy WSxM/bezpieczeństwa MPP:
  **34 passed**. Mypy strict: **33 pliki, bez błędów**. Nowe skrypty przeszły
  smoke na małym wzorcu i opisane pełne przebiegi; Ruff: bez uwag.
- Pełny zestaw repo raz: **2156 passed, 14 failed, 16 skipped**, 276,77 s.
  Wszystkie niepowodzenia są poza Viewerem. Te same 14 na czystym archiwum
  bazy ticketu: **13 failed, 1 passed**. Niestabilny
  `NanoTrackMainWindowTests.test_edge_correction_and_resume_replace_suffix`
  przeszedł również osobno na bieżącym kodzie. Powtarzalne problemy
  MolTrack/SAM2 i sesji NanoTrack należą do integracji; cały zestaw nie jest zielony.
- **Wspólny czytnik MPP wymaga zmiany w sesji integracyjnej.**
  `napara/io/mpp_reader.py::read_mpp_file`, używany także przez NanoTrack,
  ma `MAX_HEADER_LINES = 1000`. Pełny eksport ma 1029 wierszy nagłówka
  (1000 czasów + parametry); original i aligned zwracają tam
  `ValueError: Missing [Header end] in MPP.`. Viewer przyjmuje oba pliki.
  Potrzebna jest bezpieczna obsługa dłuższych nagłówków i testy odbiorców,
  bez usuwania czasów ani dowolnego podnoszenia limitów bez walidacji.
  Zgodnie z zasadami worktree nie zmieniano wspólnego czytnika. Jego odbiór
  dużej serii pozostaje otwarty; własny roundtrip nie dowodzi zgodności innych aplikacji.
- WSxM nie sprawdzano ponownie dla dużej serii; jest to odbiór dodatkowy.
  Windows 11/VLC i końcowe odbiory platform należą do ticketów 20/21.

Artefakty lokalne: `data/large-export-ticket19/` (filmy, pary, raport,
`verification-*.json`, `gui-reopen.json`, zrzuty oraz `vlc/playback.json`),
`data/large-export-ticket19-allocations/allocations.json`;
logi `/tmp/stmviewer19-{full-suite,baseline-failures,transient-recheck}.log`.
Nie wersjonujemy danych, filmów ani dużych wyników. Pilot sprzed poprawki
pozostaje w `data/large-export-ticket19-pilot/`, oddzielnie od wyników końcowych.

[Przegląd dwóch osi](implementation/review-19-large-exports.md): brak nowych
usterek produkcji. Po uwadze o duplikacji uproszczono skrypt powtórzeń i
ponowiono cały smoke GUI; zakres i wyniki dużego pomiaru pozostają aktualne.
