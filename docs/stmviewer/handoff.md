# Przekazanie — STM Viewer

## 07: Usuwanie klatek z zachowaniem czasu i pochodzenia — 2026-10-23

Gałąź: `viewer/start`. Baza implementacji i przeglądu:
`e8102e9d21924c8d661e72df223a46343e0183ff`.
Ticket: [07-frame-deletion](implementation/issues/07-frame-deletion.md).
Status: `ready-for-review`, do ręcznej próby użytkownika.
Commit implementacji: `bfffd83`; commit końcowego raportu podany w wiadomości sesji.

### Wynik i kontrakt

Przycisk Usuń klatkę jest pod obrazem. Zatrzymuje Play, usuwa tylko bieżący
obraz z pamięci serii i pokazuje następną klatkę (dla ostatniej poprzednią).
Usunięcie jedynej czyści obraz, źródło, metadane, zaznaczenie i miniatury;
numer pokazuje 0 z 0, a kontrolki obrazu/nawigacji/Play/usuwania są nieaktywne.
Nowe poprawne otwarcie po opróżnieniu przywraca normalne działanie.

Pozostałe obiekty ImageFrame zachowują dane, pochodzenie, parametry i czasy.
Usuwamy odpowiadającą parę obraz/miniatura; pozycje są ponownie numerowane,
cache ikon odświeżany, a źródłowy indeks MPP oraz czas nie są przeliczane.
Gamma, zoom, przesunięcie i Proporcje pikselowe są zachowane dla następnego
obrazu. Źródła pozostają bez zmian; nie dodano cofania ani odwracania.

Podczas importu w tle można edytować starą serię. Błąd i anulowanie zachowują
jej aktualny, skrócony lub pusty stan. Sukces zastępuje ją nową kompletną serią.
Wynik aligned należy do ticketu 08; usuwanie trzeba z nim połączyć zgodnie
z mapą, zachowując geometrię pozostałych klatek.

### Sprawdzenia i odbiór

- TDD: red → green przez publiczne kontrolki dla usunięcia podczas Play,
  wyboru następnej/poprzedniej i opróżnienia programu. Dalsze testy sprawdzają
  czasy 10/20/35 s i częściowe braki, metadane mieszanych STP/S94, ustawienia
  podglądu, niezmienność źródeł i współpracę z importem.
- **103 testy Viewera zaliczone** w Qt offscreen, w tym 10 nowych przypadków.
- Mypy strict: **15 plików bez błędów**.
- Automatyczna próba rzeczywistego okna Qt xcb przeszła z dialogiem, nowym
  wzorcem known-times.mpp i lokalnym data/MOVIE_3.MPP (17 klatek).
  Sprawdzono usunięcie środka/ostatniej/jedynej, Pause, czas, źródło, ponowne
  otwarcie i niezmienność zawartości źródeł (porównanie bajtów/hash SHA-256).
  Skrypt: `/tmp/stmviewer-deletion-smoke.py`; zrzuty:
  `/tmp/stmviewer-deletion-{middle,empty,measurement}-xcb.png`.
  Oceniono wizualnie. To próba automatyczna; odbiór użytkownika i Windows czekają.
- Pełny zestaw repo w `netcat`:
  `PYTHONPATH=.:tests/moltrack:tests/stmviewer QT_QPA_PLATFORM=offscreen python -m pytest -q --import-mode=importlib --continue-on-collection-errors`:
  **1888 passed, 15 failed, 14 skipped**, 241.66 s, bez błędów zbierania.
  Wszystkie niepowodzenia dotyczą MolTrack/NanoTrack. Log:
  `/tmp/stmviewer-deletion-full-suite.log`. Obecne lokalne `data/` usuwa
  wcześniejszy brak pomiarów; nie przypisujemy zmniejszenia liczby błędów
  implementacji usuwania klatek.
- Sprawdzenie niepowodzeń na czystym archiwum bazy `e8102e9` z dowiązanym
  tym samym `data/`, tym samym Pythonem i opcjami pytest: **13 failed,
  2 passed**, 10.03 s. Wszystkie 13 identyfikatorów i rodzaje błędów pokrywają
  się z pełną próbą: starsze ścieżki Windows/SAM2 i stan GUI MolTrack/NanoTrack.
  Log: `/tmp/stmviewer-deletion-baseline.log`; checkout:
  `/tmp/stmviewer-deletion-baseline-u84rcczz`.
  Dwa pozostałe testy NanoTrack —
  `test_edge_correction_and_resume_replace_suffix` (niewymieniona polilinia)
  i `test_real_worker_cli_roundtrips_batch_contract_with_injected_sam2_repo`
  (timeout 10 s) — przeszły również osobno na bieżącym kodzie: **2 passed**,
  1.33 s, log `/tmp/stmviewer-deletion-recheck.log`.
  Ich przyczyny w pełnym zestawie nie ustalono; brak powtarzalnej regresji
  nie oznacza zielonego odbioru całego repo. Nie zmieniano starszych aplikacji.
- [Przegląd Standards/Spec](implementation/review-07-frame-deletion.md):
  **0 uwag w obu osiach**. Największy zmieniony plik kodu:
  `stmviewer/ui/main_window.py`, **424 linie** (limit 1500).
  `git diff --check` i lokalne odnośniki zmienionej dokumentacji poprawne.
- [Instrukcja ręczna i wzorce](frame-deletion-manual.md). Nowy mały film
  known-times.mpp jest odtwarzany przez istniejący generator MPP.

Nie zmieniono wspólnych modułów, zależności ani głównej konfiguracji.
Nie ma nowego wymagania integracyjnego blokującego tę funkcję.

## Lokalny katalog danych — 2026-10-21

Użytkownik udostępnił `/home/rlew/projekty/NEtCAT-viewer/data/` do testów.
W kolejnych zadaniach korzystać przede wszystkim z tej lokalizacji.
Sprawdzono obecność 515 STP, 370 S94 i 10 MPP oraz ignorowanie `data/` przez Git.
Bieżący spis: [aktualizacja inwentarza](acceptance-reconnaissance.md).
Nie zmieniano plików pomiarowych ani nie ponawiano testów przy aktualizacji
lokalizacji. Starsze raporty zachowują faktycznie użyte ścieżki i wyniki.
Obecność `data/MOVIE_3.MPP` może usunąć wcześniejszy brak danych w testach
repozytorium; kolejny wynik porównać z bazą, uwzględniając tę zmianę środowiska.

## 06: Play, Pause i tempo odtwarzania — 2026-10-21

Gałąź: `viewer/start`. Baza implementacji i przeglądu:
`0d57200d4d606292f95fe56cca831c78e437673f`.
Ticket: [06-playback](implementation/issues/06-playback.md).
Status: `done` po potwierdzeniu ręcznego odbioru użytkownika 2026-10-21.
Commit implementacji: `83c20a9`; końcowy raport: `0f3229d`.
Commit potwierdzenia ręcznego odbioru podany w wiadomości sesji.

### Wynik i kontrakt

Sterowanie pod obrazem: Play/Pause, domyślnie 5 kl./s, wybór 1/2/5/10/20/30,
pętla domyślnie wyłączona. Pause pozostawia bieżący obraz. Bez pętli film
kończy się na ostatniej; Play na końcu pokazuje pierwszą od razu.
W pozostałych pozycjach wznawia od bieżącej. Pusta i pojedyncza seria mają
nieaktywne Play. Zamknięcie okna zatrzymuje odtwarzanie.

Ręczny wybór miniaturą, suwakiem, numerem i przyciskami zatrzymuje Play.
Kliknięcie bieżącej miniatury lub uchwytu suwaka także zatrzymuje film;
wpisywanie numeru zatrzymuje go przed zatwierdzeniem. Synchronizacja miniatur
przez odtwarzanie nie udaje ręcznej nawigacji. Gamma, zoom i przesuwanie
pozostają aktywne, a zmiana FPS od razu przestawia czas następnej klatki.

Planowanie używa pojedynczego timera: jedna następna klatka i synchroniczne
malowanie przed ponownym uruchomieniem timera. Czas przygotowania i malowania
odejmujemy od okresu. Przy przeciążeniu kolejny termin jest liczony od tej
klatki, bez nadrabiania zaległości skokiem i bez pomijania indeksów.

Import w tle pozostawia stare Play dostępne. Błąd lub anulowanie nie zmienia
jego stanu; w międzyczasie film może naturalnie dojść do końca. Sukces pokazuje
pierwszą klatkę w pauzie i resetuje widok według ticketu 05. Wybrane FPS
oraz pętla pozostają preferencjami okna. Czasy pomiaru nie są modyfikowane.

### Sprawdzenia i odbiór

- TDD przez publiczne kontrolki: red → green dla kolejnych klatek, końca/pętli,
  ręcznej nawigacji (także bieżący wybór), zmiany FPS oraz cyklu życia importu.
- **93 testy Viewera zaliczone** w Qt offscreen. W tym wymuszone przeciążenie
  Paint z odczytem kolejnych obrazów, anulowanie na granicy I/O i zamknięcie.
- Mypy strict: **15 plików bez błędów**; cache w `/tmp/stmviewer-playback-mypy`.
- Pełny zestaw repo w `netcat`:
  `PYTHONPATH=.:tests/moltrack:tests/stmviewer QT_QPA_PLATFORM=offscreen python -m pytest -q --import-mode=importlib --continue-on-collection-errors`:
  **1832 passed, 63 failed, 12 skipped**, 220.35 s. Porównano wszystkie
  identyfikatory błędów z `/tmp/stmviewer-preview-full-suite.log`: identyczne
  63 wcześniejsze niepowodzenia MolTrack/NanoTrack, bez nowych i bez błędów
  zbierania. Nie jest to zielony odbiór całego repo.
  Log: `/tmp/stmviewer-playback-full-suite.log`.
- Osobny pomiar po zakończeniu testów: `PYTHONPATH=. QT_QPA_PLATFORM=offscreen
  python tests/stmviewer/measure_playback.py
  /home/rlew/projekty/NEtCAT-domains/data/nanotrack_registration/trudne/MOVIE_8.mpp
  --output /tmp/stmviewer-playback-offscreen-512.json`.
  **84 klatki 512 × 512**, 30 s; 148 zmian obrazu, **4,956 kl./s**.
  Odstępy min/mediana/p95/max: **199,63 / 201,61 / 204,34 / 207,36 ms**.
  Każda zmiana odpowiada następnej referencji obrazu; brak pominięć.
  Po 50 prób obu czynności: Pause min/mediana/p95/max
  **5,18 / 5,26 / 5,40 / 5,55 ms**; wybór numerem
  **8,97 / 9,66 / 10,70 / 10,85 ms**. **100% prób poniżej 250 ms**.
  Otwarcie z automatycznym dialogiem: 0,217 s; nie jest częścią pomiaru Play.
  Skrypt odczytuje już pomalowany bufor przez QScreen.grabWindow, bez
  wymuszania malowania przez QWidget.grab. To potok Qt offscreen, bez
  kompozytora/monitora. Zrzut `/tmp/stmviewer-playback-offscreen-512.png`
  oceniono wizualnie; log `/tmp/stmviewer-playback-measurement.log`.
- Automatyczna próba na pulpicie Qt xcb otworzyła rzeczywisty MPP i pokazała
  kontrolki. Pomiar został przerwany po zasłonięciu okna i nie jest zaliczony
  jako liczbowy pomiar płynności monitora. Późniejsze potwierdzenie ręczne
  użytkownika zamyka próbę tego etapu; nie dostarcza nowych liczb ani
  potwierdzenia systemu. Wynik offscreen pozostaje opisany osobno.
- [Przegląd Standards/Spec](implementation/review-06-playback.md): brak naruszeń
  standardów i usterek implementacji. Warunek ręcznej płynności zamknięto
  potwierdzeniem użytkownika. Największy zmieniony plik kodu ma **396 linii**.
  `git diff --check` i lokalne odnośniki dokumentacji poprawne.
- [Instrukcja ręczna i pomiar](playback-manual.md) korzysta z istniejących
  wzorców MPP/STP oraz lokalnego filmu. Użytkownik potwierdził ręczny odbiór
  2026-10-21: „testy manualne ok”. Nie wskazano systemu; odrębne odbiory
  platform, dużej serii i aligned pozostają w późniejszych etapach.
  Aktualizacja odbioru dotyczy tylko dokumentacji; testów nie powtarzano.

Nie zmieniono wspólnych modułów, zależności ani głównej konfiguracji.
Nie ma nowej zmiany integracyjnej wymaganej do działania Play.

## 05: Zoom, gamma i brakujące próbki — 2026-10-21

Gałąź: `viewer/start`. Baza implementacji i przeglądu:
`4b4f6d478b5c734a196821106e984a6ade865536`.
Ticket: [05-preview-controls](implementation/issues/05-preview-controls.md).
Status: `done` po potwierdzeniu ręcznego odbioru użytkownika 2026-10-21.
Commit implementacji: `b2903b8`; końcowy raport: `253f806`.
Commit potwierdzenia ręcznego odbioru podany w wiadomości sesji.

### Wynik i kontrakt

Główny podgląd ma gamma 0,1–4 (domyślnie 1), reset gamma, +/− wokół środka,
Dopasuj oraz dotychczasowy zoom pod kursorem i przesuwanie bez zmiany skali.
Gamma używa `u ** (1 / gamma)` po normalizacji skończonych próbek; stała
klatka ma `u = 0,5`. Miniatury pozostają original z gamma 1. Braki są
przezroczyste w rastrze; pod nimi rysowana jest niezależna od gamma szachownica
(8 px na pole, poziomy 96/144). NaN/±Inf nie stają się zerami pomiaru.

Użytkownik zatwierdził opcję Proporcje pikselowe: pomija skalę nagłówka
w podglądzie i miniaturach, zachowując dane źródłowe. Ustawienie jest wspólne
dla serii. Bez niego dodatnia skończona skala X/Y określa proporcje, a jej
brak/nieprawidłowy stosunek daje proporcje pikselowe. Etykieta „Parametry z pliku”
nie potwierdza rzeczywistej kalibracji; nie wykrywamy zastępczych 1000 nm
po nazwie ani wartości. Miniatury dla wymuszonych proporcji są liczone na żądanie.

Zmiana klatki zachowuje gamma/zoom/przesunięcie/proporcje. Nowa poprawna seria
resetuje gamma do 1, opcję proporcji do domyślnej i dopasowuje obraz. Błąd
lub anulowanie zachowują ustawienia. Ustawienia są nieaktywne w pustej aplikacji.
Prawy panel otrzymał przewijanie: dodatkowe kontrolki i postęp nie mogą
powiększać okna, co zmieniałoby kadr po nieudanym imporcie.

### Sprawdzenia

- TDD przez publiczne kontrolki i podgląd: wartości szarości dla znanej gamma,
  neutralne miniatury, maska braków, przyciski zoomu, proporcje, dostępność
  kontrolek oraz reset/zachowanie ustawień. Gesty z wcześniejszych ticketów
  pozostają sprawdzane. Test przekazuje dane tylko do odczytu do publicznego
  podglądu i potwierdza niezmienność macierzy, NaN oraz metadanych.
- **77 testów Viewera zaliczonych** w Qt offscreen. Rozszerzony rzeczywisty
  import MPP potwierdza zachowanie gamma/proporcji/zoomu po anulowaniu.
- Mypy strict: **15 plików bez błędów**. Największy zmieniony plik kodu:
  `stmviewer/ui/main_window.py`, **314 linii**.
- Automatyczna próba rzeczywistego okna Qt xcb: dialog, gamma/reset, przyciski
  zoomu, puste próbki, proporcje oraz nawigacja lokalnego MOVIE_3.MPP.
  Zrzuty: `/tmp/stmviewer-preview-{gamma,missing,pixels,measurement}-xcb.png`.
  Oceniono wizualnie wygląd podglądu i ustawień. To próba automatyczna.
- Pełny zestaw repo w `netcat`:
  `PYTHONPATH=.:tests/moltrack:tests/stmviewer QT_QPA_PLATFORM=offscreen python -m pytest -q --import-mode=importlib --continue-on-collection-errors`:
  **1816 passed, 63 failed, 12 skipped**, 208.14 s. Porównanie identyfikatorów
  wszystkich niepowodzeń z `/tmp/stmviewer-mpp-full-suite.log` potwierdza
  identyczny zestaw 63 wcześniejszych błędów MolTrack/NanoTrack. Brak nowych
  niepowodzeń i błędów zbierania; nie jest to zielony odbiór całego repo.
  Log: `/tmp/stmviewer-preview-full-suite.log`.
- [Niezależny przegląd Standards/Spec](implementation/review-05-preview-controls.md):
  0 naruszeń zasad, 0 istotnych uwag projektowych, 0 usterek specyfikacji.
- Generator odtwarza wzorce bajtowo bez zmian w Git. `git diff --check`
  i lokalne odnośniki zmienionej dokumentacji sprawdzono bez błędów.

### Odbiór i integracja

[Instrukcja ręczna](preview-controls-manual.md) zawiera start, wzorce STP,
generator, kroki i oczekiwane wyniki. Użytkownik potwierdził ręczny odbiór
2026-10-21: „testy manualne ok”. Nie wskazano systemu; potwierdzenie nie zamyka
odrębnych ticketów odbioru platform. Aktualizacja odbioru dotyczy wyłącznie
dokumentacji; testów automatycznych nie powtarzano.
Play i original/aligned są w kolejnych ticketach; gamma i pamięć widoku
muszą zostać z nimi połączone zgodnie z mapą.

Nie zmieniono wspólnych modułów, zależności ani głównej konfiguracji.
Nie ma wymaganej zmiany integracyjnej blokującej tę funkcję.

## 04: Otwarcie filmu MPP z czasami i pochodzeniem — 2026-10-21

Gałąź: `viewer/start`. Baza implementacji i przeglądu:
`8aa12416d6225d63d1378b535e140b2063b65bf6`.
Ticket: [04-mpp-series](implementation/issues/04-mpp-series.md),
status `done` po potwierdzeniu ręcznego odbioru użytkownika 2026-10-21.
Commit implementacji: `03f4917`; końcowy raport: `2f18b67`.
Commit potwierdzenia ręcznego odbioru podany w wiadomości sesji.

### Wynik i kontrakt

Jeden MPP przechodzi przez istniejący import w tle: klatki, miniatury, postęp,
anulowanie i podmiana całej serii po sukcesie. Nie można łączyć kilku MPP
ani MPP z STP/S94. GUI pokazuje pierwotny numer klatki, czas pomiaru w sekundach
i oryginalny zapis czasu. Nawigacja, zoom i przesuwanie pozostają dostępne.

Lokalny adapter `stmviewer/mpp.py` dekoduje double little-endian, obraca 180°
raz na wejściu (zgodnie z STP i loaderem NanoTrack), zachowuje float64/NaN oraz
nagłówki z sekcjami. Amplituda Z określa jednostkę, bez przeskalowania wartości.
Wspólne dla STP/MPP parsowanie wielkości z jednostkami jest w lokalnym
`stmviewer/quantities.py`. Nieznane dane nie są zastępowane zerami.

`ImageFrame` przechowuje `source_frame_index` (indeks MPP od 0),
`measurement_time_s` oraz `measurement_time_raw`. W GUI numer źródłowy
jest liczony od 1, oddzielnie od pozycji w bieżącej serii. Brak/nieznana
jednostka czasu dotyczy tylko jednej klatki; FPS nie tworzy czasu.
Nagłówek nie ma limitu liczby linii (limit pojedynczej linii: 64 KiB).
Wymiary i długość danych są sprawdzane przed alokacją; przerwanie jest
sprawdzane w trakcie nagłówka, między klatkami i przed publikacją wyniku.

### Sprawdzenia

- TDD przez publiczny import i GUI: realne dekodowanie/wartości/orientacja,
  czasy z jednostkami i częściowymi brakami, długi nagłówek, 1000 klatek,
  postęp/anulowanie, wadliwy typ/długość oraz niedozwolony wybór.
- **68 testów Viewera zaliczonych** w Qt offscreen; mypy strict:
  **15 plików bez błędów**. Testy prawdziwych plików nie zastępują adaptera
  atrapą; kontrolowane opóźnienie oraz brak uprawnień są na granicy systemu plików.
- **12 lokalnych filmów MPP**: wszystkie klatki zgodne element po elemencie
  (także NaN) z `read_mpp_file` po obrocie 180°. Obejmuje prostokątne filmy,
  364 × 256 × 256 oraz 84 × 512 × 512; część plików to kopie tego samego pomiaru.
  Nie traktujemy ich jako 12 niezależnych wzorców. Pomiary pozostają poza Git.
- Automatyczna próba Qt xcb: prawdziwy dialog, częściowe czasy, wybór klatki
  1000 oraz klatek 1/9/17 lokalnego `MOVIE_3.MPP`. Zrzuty w
  `/tmp/stmviewer-mpp-{timed,third,1000,measurement}-xcb.png`.
- Pełne repo w netcat:
  `PYTHONPATH=.:tests/moltrack:tests/stmviewer QT_QPA_PLATFORM=offscreen python -m pytest -q --import-mode=importlib --continue-on-collection-errors`
  — **1807 passed, 63 failed, 12 skipped**, 207,50 s. Zestaw niepowodzeń
  jest identyczny z poprzednią próbą S94: starsze MolTrack/NanoTrack,
  m.in. brak MOVIE_3.MPP, ścieżki Windows i SAM2. **Brak nowych niepowodzeń
  i błędów zbierania**. To nie jest zielony odbiór całego repo.
  Log: `/tmp/stmviewer-mpp-full-suite.log`. Dodatkowa ścieżka testów udostępnia
  generator binarnych wzorców przy używanym w repo trybie pytest importlib.
- [Przegląd Standards/Spec](implementation/review-04-mpp-series.md): brak
  naruszeń zasad, jedna drobna sugestia formatowania pochodzenia; Spec bez uwag.
  Sugestię pozostawiono jako możliwość późniejszego uproszczenia trzech
  powtórzonych linii, bez usterki zachowania.
- Generator odtwarza wzorce bajtowo bez zmian. Sprawdzono 44 lokalne odnośniki
  dokumentacji przed dodaniem raportu. Największy zmieniony plik kodu:
  `stmviewer/ui/main_window.py`, **263 linie**. `git diff --check` poprawne.

### Odbiór i integracja

[Instrukcja GUI](mpp-series-manual.md) zawiera uruchomienie, wersjonowane małe
wzorce, generator, lokalne pomiary oraz oczekiwane wyniki. Użytkownik
potwierdził pozytywny wynik testów manualnych 2026-10-21: „testy manualne ok”.
Nie wskazano systemu; potwierdzenie nie zamyka odrębnych ticketów odbioru
platform, w tym Windows. Test 1000 × 1 × 1 sprawdza liczbę klatek i nagłówek;
nie zastępuje testu 1000 × 512 × 512 z ticketu 18. Aktualizacja statusu zmienia
wyłącznie dokumentację; nie ponawiano testów kodu.

Nie zmieniono modułów wspólnych ani konfiguracji głównej/zależności.
Dla przyszłych zmian integracyjnych wspólny czytnik/loader wymaga:
zniesienia limitu 1000 linii, kontroli deklarowanego typu, wydajnego odczytu
float64, poprawnych jednostek i częściowych czasów oraz uzgodnionej orientacji.
Wspólny kontrakt musi być sprawdzony u dotychczasowych odbiorców. Lokalny
adapter pozwala kontynuować Viewer niezależnie; dodatkowe metadane MPP
i eksport należą do kolejnych ticketów.

## 03: S94 i mieszane serie STP/S94 — 2026-10-21

Gałąź: `viewer/start`. Baza implementacji i przeglądu:
`b904045e7626e97cd924920d9fbb0e52fbdb3bcc`.
Commit implementacji: `d6fbb7d`; końcowy raport: `18d6ca9`.
Commit potwierdzenia ręcznego odbioru podany w wiadomości sesji.
Ticket: [03-s94-series](implementation/issues/03-s94-series.md),
status `done` po potwierdzeniu ręcznego odbioru użytkownika 2026-10-21.

### Wynik i kontrakt danych

Dialog, menu i Ctrl+O otwierają jeden lub wiele STP/S94, także mieszanych.
Importer `open_frame_series` zastępuje nazwę ograniczoną wcześniej do STP.
Kolejność nazw, zgodność wymiarów, postęp, anulowanie, zachowanie stanu przy
błędach i nawigacja korzystają z dotychczasowego przebiegu. Wymiary są porównywane
po transformacji każdego wejścia. Zoom i pojedyncze podświetlenie miniatur pozostają.

Adapter `stmviewer/s94.py` korzysta z układu nagłówka i zakresów wzmocnienia
wspólnego czytnika. Sam odczytuje jawnie little-endian int16 i przechowuje float64;
waliduje nagłówek, dodatnie wymiary, flagę Swapped oraz długość danych przed
alokowaniem macierzy. Dla trybu 0: gain 1/2/3 odpowiada 5,5/22/88 nm na 65536
jednostek surowych; tryb 1: 20 nA na 65536 jednostek. Nieznany gain topografii
lub tryb zachowuje liczby surowe, brak jednostki i opis przyczyny w panelu.
Pole `ImageFrame.calibration_note` przekazuje tę informację do podglądu.

Swapped=1 transponuje macierz i zamienia osie rozmiarów oraz offsetów.
Oryginalny nagłówek, w tym Image_Number, Swapped i wszystkie pozostałe pola,
pozostaje zachowany. Kąt skanowania jest źródłowym ustawieniem pomiaru,
nie kątem wyliczonym dla przekształconego rastra. Brak wiarygodnej dodatniej
skali lub niefinitywny parametr jest reprezentowany przez None. Rzeczywiste zera
pozostają zerami. Bias mV jest przeliczany na V. Pole It nie ma potwierdzonej
jednostki w istniejącym kontrakcie czytnika, więc nie jest zgadywane jako setpoint.

### Sprawdzenia

- TDD red → green: znana kalibracja i para S94/STP, nieznana kalibracja,
  prostokątny obraz Swapped, walidacja, wspólna seria i kontrolki GUI.
  Testy nie zastępują wewnętrznych komponentów atrapami.
- **54 testy Viewera zaliczone** w offscreen. Nowe przypadki obejmują
  signed little-endian, dane fizyczne/surowe, metadane po transpozycji,
  zachowanie stanu po błędnym S94 i anulowanie podczas jego odczytu w mieszanej serii.
- Mypy strict: **13 plików bez błędów**. Największy zmieniony plik kodu:
  `tests/stmviewer/test_series_window.py`, **264 linie**.
- Rzeczywiste lokalne pary 17851, 17544 i 85291r: macierze nowego odczytu
  S94 są identyczne element po elemencie z STP (256 × 256). Pierwsze dwie
  pary mają nm; eksport 85291r.STP podaje nm mimo prądowego trybu S94/nA.
  Wartości nie są nadpisywane na podstawie innego pliku; różnica jest opisana
  w instrukcji ręcznej. Pomiary pozostają lokalne poza Git.
- Automatyczne GUI xcb na Linuksie: prawdziwy dialog obu formatów, nawigacja,
  opis surowych wartości oraz identyczny podgląd pary 17851. Zrzuty oceniono
  wizualnie: `/tmp/stmviewer-s94-mixed-xcb.png`, `/tmp/stmviewer-s94-raw-xcb.png`,
  `/tmp/stmviewer-s94-measurement-xcb.png`.
- Pełny zestaw repo w netcat:
  `PYTHONPATH=.:tests/moltrack QT_QPA_PLATFORM=offscreen python -m pytest -q --import-mode=importlib --continue-on-collection-errors`
  — **1793 passed, 63 failed, 12 skipped**, 204.61 s. Zestaw 63 niepowodzeń
  jest identyczny z bazą `/tmp/stmviewer-series-full-suite.log` (starsze
  MolTrack/NanoTrack, m.in. brak MOVIE_3.MPP, ścieżki Windows i SAM2).
  Brak nowych niepowodzeń i błędów zbierania. To nie jest zielony odbiór całego repo.
  Log: `/tmp/stmviewer-s94-full-suite.log`.
- [Przegląd Standards/Spec](implementation/review-03-s94-series.md): obie osie
  bez uwag. Generator odtwarza wzorce bajtowo bez zmian; sprawdzono 37 lokalnych
  odnośników dokumentacji przed dopisaniem raportu. `git diff --check` poprawne.

### Odbiór i integracja

[Ręczna próba S94](s94-series-manual.md) zawiera uruchomienie w netcat,
wersjonowane wzorce i generator, lokalne pary pomiarów oraz oczekiwane wyniki.
Użytkownik potwierdził pozytywny wynik testów manualnych 2026-10-21:
„testy manualne ok”. Nie wskazano systemu; potwierdzenie nie zamyka
odrębnych ticketów odbioru platform, w tym Windows.
Aktualizacja statusu zmienia wyłącznie dokumentację; nie ponawiano testów kodu.

Nie zmieniono modułów wspólnych, konfiguracji głównej ani zależności.
Do wykorzystania przez integrację przy przyszłej poprawce wspólnego czytnika:
explicit `<i2` zamiast natywnego int16, jawna jednostka i informacja o danych
surowych, walidacja parametrów oraz spójna zamiana offsetów wraz z osiami.
Taka wspólna zmiana wymaga testów odbiorców; nie blokuje działającego adaptera
Viewera. Testy z `tests/stmviewer/test_s94_import.py` opisują jego obecny kontrakt.

## Poprawka ticketu 02: podświetlenie miniatur — 2026-10-21

Baza: `89614aa`, gałąź `viewer/start`. Commit poprawki: `cb40891`. Użytkownik zgłosił pozostawanie podświetlenia poprzednich
miniatur przy użyciu Następna/Poprzednia. Odtworzono to dwukrotnie na xcb:
model zaznaczał tylko aktualną klatkę, ale poprzednie podświetlenie znikało
z ekranu dopiero po wymuszonym przemalowaniu.

Przyczyną był `QSignalBlocker` na modelu zaznaczenia: blokował również
powiadomienia potrzebne widokowi Qt do odświeżenia poprzedniej miniatury.
Usunięto blokadę tych sygnałów. Obsługa wyboru ignoruje już aktywny indeks,
co zapobiega ponownemu wykonywaniu tej samej zmiany podczas synchronizacji.

Test regresji poprzez publiczne przyciski sprawdza pojedyncze zaznaczenie
oraz zdarzenia malowania starej i nowej miniatury (dwa kroki w przód i dwa
wstecz). Przed poprawką nie otrzymywał przemalowania starej miniatury;
po poprawce przechodzi w offscreen i xcb. Niezależna automatyczna próba xcb
porównuje obraz z ekranu przed i po wymuszonym odświeżeniu — po poprawce
obrazy są identyczne. Lokalny skrypt diagnostyczny i zrzuty:
`/tmp/stmviewer-selection-debug/`.

Sprawdzenia: **34 testy Viewera zaliczone**, test regresji na xcb zaliczony,
mypy strict bez błędów, `git diff --check` poprawne. Największy zmieniony plik
kodu ma 263 linie. Nie powtarzano pełnego zestawu repo dla tej lokalnej
poprawki GUI; poprzedni wynik i 63 istniejące błędy są opisane niżej.
Nie zmieniono wspólnych modułów ani zależności. Powyższe próby są automatyczne.
Użytkownik następnie potwierdził ręczny odbiór po poprawce 2026-10-21:
„testy manualne ok”. Ticket 02 ma status `done`. Nie wskazano systemu;
potwierdzenie nie zamyka odrębnych ticketów odbioru platform.

## 02: Otwarcie i przeglądanie serii STP — 2026-10-21

Gałąź: `viewer/start`. Baza implementacji i code-review:
`3f2e92b59d29dc0ecf74751807e26f530167af7d`.
Commit implementacji: `e054738`. Finalny zakres tego etapu: `3f2e92b..HEAD`;
commit raportu podany w końcowej wiadomości sesji.
Ticket: [02-stp-series](implementation/issues/02-stp-series.md),
status `done` po potwierdzeniu ręcznego odbioru użytkownika 2026-10-21.

### Wynik

Otwieranie jednego lub wielu STP sortuje nazwy naturalnie i wymaga jedynie
zgodnych wymiarów pikselowych. Odczyt wykorzystuje sprawdzony adapter;
każda klatka zachowuje własne wartości, orientację, skalę, kanał i pozostałe
metadane. Miniatury oryginałów są na dole, ustawienia po prawej.
Przyciski, suwak, edytowalny numer, zaznaczenie miniatury, główny obraz i panel
źródła wskazują tę samą klatkę. Pasek przewija się do wybranej miniatury.

Odczyt i przygotowanie miniatur wykonuje zadanie w tle. Postęp obejmuje obie
fazy. Błąd lub anulowanie nie zastępują poprzedniego zestawu i wyboru.
Podczas importu działają podgląd i nawigacja starej serii; nowy import jest
zablokowany. Anulowanie czeka na ukończenie bieżącego odczytu pojedynczego
pliku; okno nadal obsługuje zdarzenia. Zamknięcie podczas importu anuluje
zadanie i zamyka okno po zakończeniu wątku.

Zmiana klatki zachowuje zoom i przesunięcie. Sukces nowego importu pokazuje
pierwszą klatkę dopasowaną do okna. Pusta i pojedyncza seria mają odpowiednio
nieaktywne kontrolki. To realizuje również część przyszłego ticketu 05;
gamma i szachownica pozostają do wykonania.

### Sprawdzenia

- TDD: red → green dla naturalnego sortowania/odczytu, kontroli wymiarów,
  anulowania, nawigacji GUI oraz responsywności przy opóźnionym I/O.
  Testy korzystają z uzgodnionych publicznych granic. Zastępowane są jedynie
  dialog systemowy i czas odczytu pliku, bez atrap wewnętrznych komponentów.
- **33 testy Viewera zaliczone** w Qt offscreen. Obejmują regresje pojedynczego
  STP i gestów, dane liczbowe/metadane, odmienne znane kanały i skale,
  orientację miniatur, synchronizację, anulowanie, błędy oraz zamykanie w trakcie pracy.
- Mypy strict: **12 plików bez błędów**. Największy zmieniony plik kodu:
  `stmviewer/ui/main_window.py`, **252 linie**; wszystkie poniżej 1500.
- Pełne repo w `netcat`:
  `PYTHONPATH=.:tests/moltrack QT_QPA_PLATFORM=offscreen python -m pytest -q --import-mode=importlib --continue-on-collection-errors`:
  **1772 passed, 63 failed, 12 skipped**, 205.54 s. Zestaw 63 niepowodzeń
  jest identyczny z poprzednią próbą (`/tmp/stmviewer-navigation-full-suite.log`):
  starsze testy MolTrack/NanoTrack, m.in. brak MOVIE_3.MPP, ścieżki Windows,
  SAM2. **Brak nowych niepowodzeń i błędów zbierania**. To nie jest zielony odbiór
  całego repo. Log: `/tmp/stmviewer-series-full-suite.log`.
- Automatyczna próba rzeczywistego okna Qt xcb na Linuksie: dialog wielu STP,
  kolejność 1–2–10, przyciski i miniatury, następnie rzeczywisty pomiar 34855.STP.
  Zrzuty oceniono wizualnie: `/tmp/stmviewer-series-xcb.png`,
  `/tmp/stmviewer-series-current-xcb.png`, `/tmp/stmviewer-series-measurement-xcb.png`.
- Generator większych danych sprawdzono na trzech STP 64 × 64 z ponownym
  odczytem. Duża próba wydajności z ticketu 18 nie została tu wykonana.

- [Przegląd Standards/Spec](implementation/review-02-stp-series.md): obie
  niezależne osie bez ustaleń wymagających poprawki. Generatory odtworzyły
  wzorce bajtowo bez zmian; 38 odnośników dokumentacji było poprawnych,
  `git diff --check` bez błędów.

### Odbiór i integracja

[Instrukcja GUI i wzorce](stp-series-manual.md) obejmują ręczny scenariusz,
łącznie z generowaniem większego zestawu do anulowania. Użytkownik potwierdził
ręczny odbiór serii po poprawce miniatur 2026-10-21. To nowe potwierdzenie
ticketu 02, niezależne od wcześniejszego odbioru ticketu 01. Systemu nie podano;
odbiór Windows pozostaje odrębnym etapem.

Zmiany dotyczą wyłącznie aplikacji Viewera, jej testów i dokumentacji.
Nie zmieniono konfiguracji głównej, zależności ani współdzielonych loaderów;
nie potrzeba nowej poprawki integracyjnej. Uruchomienie pozostaje
`python -m stmviewer.main` w `netcat`. Nie publikowano ani nie scalano gałęzi.

## Uzupełnienie: zoom i przesuwanie — 2026-10-21

Baza dodatku: `7a43715`, gałąź `viewer/start`. Commit kodu: `75f419d`.
Commit raportu testów i przeglądu: `df4bbc5`.
Użytkownik potwierdził ręczną próbę otwierania STP i zlecił wcześniejsze dodanie
nawigacji obrazu. To część zakresu [05](implementation/issues/05-preview-controls.md),
bez zamykania jego przyszłych wymagań dotyczących serii i gamma.

Kółko zmienia zoom pod kursorem (czynnik 1.2 na krok, zakres 0.1–64 względem
dopasowania), lewy przycisk przesuwa obraz w obu osiach bez zmiany zoomu.
Przycisk „Dopasuj” przywraca cały obraz. Poprawny import dopasowuje nową klatkę,
anulowanie i błąd zachowują nawigację. Pusty program ma nieaktywne Dopasuj.
Zależności i wspólny kod pozostają bez zmian. Przy wprowadzaniu przeglądania
serii trzeba zachować zoom na zmianie klatki: obecne `set_frame` oznacza nowy import.

Sprawdzenia dodatku: pięć testów publicznych gestów GUI przechodzi w offscreen
(zoom pod kursorem, ruch podczas przeciągania i stała wielkość znacznika,
Dopasuj, zachowanie/reset przy imporcie, pusty program). Mypy strict: 8 plików,
bez błędów. Automatyczna próba xcb otworzyła rzeczywisty 34855.STP przez dialog,
sprawdziła kółko, przeciąganie i powrót przez Dopasuj. Użytkownik potwierdził
ręczny odbiór nawigacji 2026-10-21: „testy manualne ok”.
[Scenariusz](single-stp-manual.md#zoom-i-przesuwanie). Nie wskazał platformy;
potwierdzenie nie zamyka osobnych odbiorów Ubuntu i Windows.
[Przegląd dodatku](implementation/review-preview-navigation.md): Standards — 0 ustaleń,
Spec — 0 ustaleń. Największy zmieniony plik kodu ma 132 linie, `git diff --check`
bez błędów. Zrzut automatycznej próby: `/tmp/stmviewer-navigation-xcb.png`.
Pełny zestaw repo w `netcat`:
`PYTHONPATH=.:tests/moltrack QT_QPA_PLATFORM=offscreen python -m pytest -q --import-mode=importlib --continue-on-collection-errors`
— **1758 passed, 63 failed, 12 skipped** w 203.27 s. Wszystkie 19 testów
Viewera przeszły. Zestaw 63 niezaliczonych testów jest identyczny z wcześniejszą
bazą `ba4e0d3`; nie ma nowych błędów ani błędów zbierania testów.
Log: `/tmp/stmviewer-navigation-full-suite.log`.

## 01: Pierwszy obraz STP — poprzedni etap

Data: 2026-10-21. Gałąź: `viewer/start`. Baza zmiany i code-review: `ba4e0d3`.
Commit implementacji: `960101c`; finalny zakres `ba4e0d3..HEAD`.
Commit raportu odbioru podany w końcowej wiadomości sesji.
Ticket: [01-single-stp](implementation/issues/01-single-stp.md).

## Wynik

Działa otwieranie pojedynczego STP z przycisku, menu i Ctrl+O. Obraz jest
w całości dopasowany, z proporcjami fizycznymi przy znanej skali obu osi,
a przy braku skali — pikselowymi. Panel pokazuje źródło, rozmiar, kanał,
jednostkę sygnału, pole i offsety X/Y, napięcie, prąd oraz kąt.
Brak metadanych pozostaje brakiem, rzeczywiste zera są zachowane.
Anulowanie i błąd odczytu nie wymieniają poprzedniego obrazu.

`stmviewer.io.open_stp` wykorzystuje dekodowanie double i obrót 180°
w `napara.io.stp_reader`. Adapter zachowuje źródłowy kanał, metadane
z nagłówka i jednostkę z Z Amplitude bez skalowania próbek. Odczytuje UTF-8
oraz starsze nagłówki Latin-1 bez usuwania µ. Odrzuca jawny typ inny niż
`double`, błędne wymiary, niepełny payload i brak końca nagłówka.
Nagłówek adaptera ograniczono do 1 MiB, 64 KiB na linię i limitu liczby
linii wspólnego czytnika. Wartości pozostają float64; podgląd to osobny raster.

Nie zmieniono wspólnych aplikacji ani głównej konfiguracji. Małe wzorce,
ich generator i [ręczny scenariusz](single-stp-manual.md) są w Git.
Uruchomienie z `netcat`: `python -m stmviewer.main` z katalogu repo.
Instrukcje środowisk Ubuntu/Windows: [README](README.md#uruchomienie).

## Sprawdzenia

- TDD: zaobserwowane red → green dla dekodowania, publicznego otwarcia
  w GUI, błędów importu z nazwą źródła oraz zachowania jednostki µ w Latin-1.
- Testy Viewera: 12 testów importu i 2 testy GUI offscreen — zaliczone.
  Publiczne kontrolki sprawdzają również zastąpienie, anulowanie i błędny plik.
- `python -m mypy --config-file stmviewer/mypy.ini`: 8 plików aplikacji,
  strict, bez błędów. Stary kod `napara` nie jest objęty tym sprawdzeniem typów.
- Trzy rzeczywiste STP (34855, 17851, 17544) wczytane poprawnie: 256 × 256,
  kanał Topo, jednostka nm, zachowane zakresy wartości i skala X/Y.
- Automatyczna próba z prawdziwym oknem Qt xcb na Linuksie: wybór wzorca
  i rzeczywistego 34855.STP w dialogu, zmiana rozmiaru okna do 640 × 480.
  Zapisane obrazy ocenione wizualnie: prawidłowe L i pełne pole pomiaru.
  To próba sterowana skryptem, nie ręczny odbiór użytkownika.
- Pełny zestaw repo uruchomiony raz w `netcat` z
  `QT_QPA_PLATFORM=offscreen python -m pytest -q --import-mode=importlib --continue-on-collection-errors`:
  **1479 passed, 64 failed, 12 skipped, 36 errors**. Błędy dotyczą
  MolTrack/NanoTrack (brak `data/MOVIE_3.MPP`, ścieżki Windows, SAM2)
  oraz importów helperów testowych MolTrack przy `importlib`.
  Czyste archiwum `ba4e0d3` uruchomione tą samą komendą:
  **1466 passed, 63 failed, 12 skipped, 36 errors**. Wszystkie 99
  niepowodzeń bazy występuje też w bieżącym kodzie. Jedyna różnica to timeout
  10 s workera SAM2; powtórzony samodzielnie w bieżącym kodzie przeszedł
  w 0.70 s. Nie stwierdzono regresji Viewera; nie jest to zielony odbiór repo.
  Błędy zbierania wynikają z braku `tests/moltrack` w ścieżce importów
  pomocników testowych przy wybranym trybie `importlib`.
  Ponowiono tylko te 36 modułów z `PYTHONPATH=.:tests/moltrack`:
  **273 passed in 151.70 s**, bez błędów zbierania. Nie zmieniano ich kodu.
- Limit plików: największy nowy/zmieniony plik Python ma 109 linii.
  `git diff --check` bez błędów.
- [Przegląd Standards/Spec](implementation/review-01-single-stp.md):
  Standards — 0 ustaleń; Spec — 0 usterek kodu. W chwili przeglądu pozostały
  2 warunki odbioru; ich zamknięcie opisano poniżej.
  Obie osie wykonane przez niezależnych recenzentów od uzgodnionej bazy.

Lokalne logi: `/tmp/stmviewer-full-suite.log`, `/tmp/stmviewer-baseline-suite.log`
i `/tmp/stmviewer-collection-recheck.log`. Generator odtworzył wzorce bajtowo
bez zmiany w Git; 36 lokalnych odnośników zmienionej dokumentacji jest poprawnych.
Zrzuty próby xcb: `/tmp/stmviewer-asymmetric-xcb.png`,
`/tmp/stmviewer-measurement-xcb.png`, `/tmp/stmviewer-measurement-small-xcb.png`.
Artefakty lokalne nie są częścią repozytorium.

## Odbiór i integracja

Ticket 01 ma status `done`: funkcja działa, testy i instrukcje są dostarczone,
a użytkownik zatwierdził odbiór. Następny odblokowany etap to ticket 02.
Użytkownik potwierdził ręczny scenariusz otwierania STP 2026-10-21:
„testy manualne ok”. Nie podał systemu, więc nie oznacza to odbioru Windows.
Usunięto dodatkową blokadę osobnego potwierdzenia lokalnej konfiguracji:
nie zmieniono konfiguracji głównej ani wspólnych modułów. Doprecyzowanie
zapisano w kryterium ticketu i zasadach implementacji.

Do wykorzystania przy integracji: minimalne wymagania aplikacji
`stmviewer/requirements.txt` (wspólny PyQt6 + NumPy 2.2.5),
`stmviewer/requirements-dev.txt` oraz komenda
`python -m mypy --config-file stmviewer/mypy.ini`. Konfiguracja działa lokalnie
bez zmiany root i została przekazana w dokumentacji. Odrębnego zatwierdzenia
przez sesję integracyjną nie przeprowadzono; nie jest ono warunkiem zamknięcia
tego lokalnego etapu. Scalenie gałęzi pozostaje osobną czynnością.
Wspólny czytnik wymaga w przyszłości obsługi Acquisition channel,
X-Offset/Y-Offset, nieznanych wartości, osobnej jednostki sygnału i kodowania
nagłówka bez utraty µ. Adapter zapewnia ten kontrakt już w Viewerze.
Zmiany wspólnego czytnika powinny objąć testy jego istniejących odbiorców.

Pozostałe potrzeby integracyjne i zakres całej aplikacji zachowano
we [wcześniejszym przekazaniu planu](planning-handoff.md).
