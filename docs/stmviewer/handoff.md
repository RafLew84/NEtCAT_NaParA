# Przekazanie — STM Viewer

## 15: Prezentacja AVI — 2026-10-26

[Ticket 15](implementation/issues/15-avi-presentation.md): **done**.
Baza `d6a08e1`, implementacja **`3e1fddf`**.
[Instrukcja ręczna i dane](avi-presentation-manual.md),
[przegląd dwóch osi](implementation/review-15-avi-presentation.md).
Użytkownik potwierdził 2026-10-26: „testy manualne ok”. Odbiór obejmuje
implementację `3e1fddf` i przekazanie `e80a93d`. Aktualizacja dotyczy wyłącznie
dokumentacji: sprawdzono spójność statusów, linki i `git diff --check`;
nie ponawiano testów kodu.

Dialog AVI daje gamma z podglądu lub 1, kontrast osobno dla każdej klatki
lub wspólny dla wybranego zakresu oraz tło czarne/szare/białe (0/128/255).
Wartości domyślne pozostają: gamma podglądu, kontrast osobny, czarne tło.
Nowe otwarcie dialogu przywraca te wartości. Opcje po rozpoczęciu są niezmienne;
zmiana podglądu nie wpływa na rozpoczęty film. Nie zmieniono podglądu ani MPP.

Wspólne poziomy wyznacza worker tylko ze skończonych próbek wybranych klatek,
blokami około 4 MiB z punktami anulowania. Nie powstaje dodatkowy stos filmu.
Postęp obejmuje wyznaczanie poziomów, zapis i weryfikację. Braki i dopełnienie
używają wybranego koloru po gamma, bez udziału w poziomach. Przy stałym zakresie
u=0,5 przed gamma; pusty film/klatka z punktu widzenia próbek daje wybrane tło.
MJPG/FFV1 nadal mają wspólne renderowanie i zabezpieczenia z ticketu 14.

Zakres AVI to nadal original. Renderer działa też na pikselach gotowego aligned
wczytanego z MPP jako źródło; dodanie wyboru bieżącego aligned jest w tickecie 16.
Nie dodano opisów ani nowych zależności, nie zmieniono wspólnych modułów.

Sprawdzenia:

- TDD: red → green kolejno dla teł, wspólnego kontrastu i publicznych opcji GUI;
  pozostałe scenariusze rozszerzają regresje granic zatwierdzonych dla AVI.
- **57 passed**, 12.83 s, `/tmp/stmviewer-avi15-focused.log`. Obejmuje 24
  kombinacje kodeka/tła/kontrastu/gamma przez GUI i faktyczny odczyt AVI,
  skrajne finite float64, NaN/Inf, stały zakres, brak próbek, wybór zakresu,
  niezmienność ustawień podczas pracy i anulowanie obliczeń kontrastu.
- Mypy strict: **31 plików, 0 błędów**. `git diff --check` czysty.
  Największy zmieniony plik kodu: `avi_export.py`, **171 linii**.
- Pełne repo raz na końcu implementacji: **2095 passed, 14 failed, 16 skipped**,
  259.60 s, `/tmp/stmviewer-avi15-full-suite.log`. Porównanie z logiem ticketu 14
  `/tmp/stmviewer-avi-full-suite.log`: identyczne 14 identyfikatorów błędów
  MolTrack/NanoTrack, bez nowych. Nie deklarujemy zielonego całego repo.
- **34 passed**, 9.69 s, GUI Qt xcb na osobnym Xvfb; log
  `/tmp/stmviewer-avi15-xcb.log`. Obejrzano także rozszerzony dialog.
- Faktyczne **VLC 3.0.20** odtworzyło 10 filmów w MJPG/FFV1 z nowymi opcjami,
  do EOF, z wyjściem obrazu xcb_x11 i kodem 0, bez błędów; obejrzano zrzuty.
  Raporty: `/tmp/stmviewer-avi15-vlc/`. Użyto tymczasowej kopii VLC z poprzedniego
  etapu; niczego nie instalowano w systemie. Brak stanowiska Windows.
- Dane: `data/avi-ticket15/presentation.mpp` i JSON oraz 10 lokalnych AVI;
  generator `tests/stmviewer/make_avi_presentation_fixtures.py`. Pięć klatek
  65 × 49, wynik 66 × 50, rozpoznawalne skale i skrajna pierwsza klatka.
  Pomiary i filmy pozostają poza Git.

Przegląd skilla code-review: Standards **0 ustaleń**, Spec **0 ustaleń**.
Nie były potrzebne poprawki kodu. Ręczny odbiór użytkownika potwierdzony.
Nie wskazano systemu; odrębne próby platformowe w ticketach 20 i 21 pozostają
otwarte. Współpraca z integracją: brak nowych wspólnych
zmian i zależności; użyto netcat oraz konfiguracji OpenCV z ticketu 14.

## 14: Original do AVI — 2026-10-26

[Ticket 14](implementation/issues/14-original-avi-basic.md): **done**.
Baza `60785df`, implementacja `959c5c6`, poprawki `a9cf6b4`.
[Instrukcja uruchomienia i ręcznej próby](original-avi-manual.md),
[przegląd dwóch osi](implementation/review-14-original-avi.md).
Użytkownik potwierdził 2026-10-26: „testy manualne ok”. Odbiór obejmuje
implementację i poprawkę wskazane wyżej oraz przekazanie `7d546d3`.
Aktualizacja statusu dotyczy wyłącznie dokumentacji: sprawdzono spójność
statusów, linki i `git diff --check`; nie ponawiano testów kodu.

Dostępny przycisk/menu „Zapisz AVI original…”: cała seria lub zakres włącznie,
FPS 1–30 (domyślnie Play), MJPG domyślnie lub FFV1. Podsumowanie pokazuje
liczbę klatek, rozmiar i czas. Pełne obrazy niezależne od zoomu; gamma pobrana
z podglądu, kontrast per klatka, czarne braki, bez opisów. Wspólna skala daje
proporcje fizyczne; nieznana/niespójna lub opcja Proporcje pikselowe daje
pikselowe. Nearest sampling zachowuje wspólnie dane/maskę przy rozszerzeniu;
nieparzyste wymiary są dopełniane z prawej/dołu bez obcinania krawędzi.

Worker blokuje import, Play, usuwanie, rejestrację i oba eksporty; przeglądanie,
zoom i gamma działają dalej bez zmiany ustawień bieżącego filmu. Zapis etapowy
chroni istniejący plik. Pełny odczyt sprawdza liczbę, FPS, geometrię i kodek;
FFV1 dodatkowo skróty rastrów uint8. Brak kodeka lub błąd daje komunikat.
Próba kodera odbywa się w osobnym procesie po wykryciu natywnej awarii MJPG
przy 4 × 4. Bez automatycznej zamiany kodeka czy pobierania. Zamknięcie okna
anuluje pracę i czeka na worker. MPP i białe tło jego podglądu są zachowane.

Wykonane sprawdzenia:

- TDD na zatwierdzonych granicach: renderer, publiczny eksport z rzeczywistym
  odczytem i publiczne kontrolki GUI. Testy awarii kodeka obejmują też faktyczny
  SIGABRT małego MJPG izolowany w procesie potomnym.
- Po przeglądzie **62 passed**, 18.71 s: AVI oraz powiązane MPP, Play,
  rejestracja i usuwanie. Log `/tmp/stmviewer-avi-focused-final.log`.
- Mypy strict: **31 plików, 0 błędów**. `git diff --check` czysty.
  Największy zmieniony plik `main_window.py`: **802 linie** (limit 1500).
- Pełne repo raz na końcu implementacji: **2056 passed, 14 failed, 16 skipped**,
  239.70 s, `/tmp/stmviewer-avi-full-suite.log`. Porównanie z
  `/tmp/stmviewer-white-full-suite.log`: identyczne 14 identyfikatorów błędów
  MolTrack/NanoTrack; nie dodano nowych. Nie deklarujemy zielonego całego repo.
- Qt xcb na osobnym Xvfb: **13 passed**, 2.78 s, AVI/MPP GUI.
  Obejrzano główne okno i dialog. To próba automatyczna, nie akceptacja użytkownika.
- Faktyczne VLC **3.0.20**: sześć filmów (MOVIE_3, odd, anisotropic × oba kodeki),
  renderowanie xcb_x11, dojście do EOF i kod wyjścia 0, bez błędów; obejrzano
  zrzuty. Pakiety Ubuntu rozpakowano wyłącznie do `/tmp/stmviewer-avi-vlc/`;
  tam logi, `results.json` i obrazy. Windows nie był dostępny.
- Rzeczywiste anulowanie przez GUI w trakcie kodowania 600 klatek 512 × 512:
  komunikat anulowania, wcześniejszy AVI identyczny bajtowo. Mały wzorzec
  kończył zapis przed kliknięciem, więc większy plik generuje opcja `--long`.
- Dane: `data/avi-ticket14/`, generator `tests/stmviewer/make_avi_fixtures.py`.
  Gotowe AVI i MPP są poza Git. `MOVIE_3.MPP`: 17 klatek 256 × 256;
  `odd`: sześć 65 × 49 → 66 × 50; `anisotropic` → 130 × 50.

Przegląd Standards: 0 twardych naruszeń, 1 uwaga P3 o powtarzaniu blokad
rozwiązana w `a9cf6b4`, potwierdzona przez recenzenta; Spec: 0 ustaleń.
Końcowo obie osie bez otwartych uwag. Ręczny odbiór użytkownika potwierdzony.
Nie wskazano systemu, więc osobne odbiory platform w ticketach 20 i 21
pozostają otwarte.

Współpraca: brak zmian wspólnego kodu/konfiguracji. Lokalny
`stmviewer/requirements-avi.txt` korzysta z istniejącego przypięcia OpenCV
w requirements-ecc.txt. Integracja powinna uwzględnić ten zestaw podczas
przygotowania pełnego środowiska; netcat już zawiera wymagany build.
Duże serie, dodatkowe prezentacje, aligned i opisy pozostają w ich ticketach.

## 13: Potwierdzenie odbioru — 2026-10-26

Użytkownik potwierdził: „teraz jest ok. testy manualne ok”.
[Ticket 13](implementation/issues/13-aligned-mpp.md),
[poprawka zgodności MPP](implementation/issues/13-wsxm-compatibility-fix.md)
i [białe tło oraz uproszczony zapis](implementation/issues/13-white-background.md)
mają status **done**. Potwierdzenie dotyczy końcowego rozwiązania z dwoma
wyborami original/aligned, jasnym tłem i odtwarzaniem braków przez V3.

Implementacja i kolejne poprawki znajdują się w zakresie `6ab0837..223c1bb`,
w tym `ec21f6a`, `35858f1`, `2343bd6`, `e013d73` i `2175cfe`.
Aktualizacja odbioru obejmuje wyłącznie dokumentację: sprawdzono spójność
statusów, linki i `git diff --check`; nie ponawiano testów kodu.
Nie przypisujemy ogólnemu potwierdzeniu odbioru konkretnych platform;
użytkownik nie wskazał systemu, więc pozostają osobne zadania 20 i 21.
Ticket 14 ma spełnioną zależność 07 i status ready-for-agent; nie rozpoczęto go.

## 13: Białe tło i dwa wybory zapisu — 2026-10-26

Baza `7123d1b`, implementacja **`2175cfe`**.
[Ticket poprawki](implementation/issues/13-white-background.md): **ready-for-review**.
[Próba ręczna](wsxm-export-manual.md), [przegląd](implementation/review-13-white-background.md).
Zmiana wynika z prośby użytkownika o ujednolicenie dodatkowego obszaru.

W oknie zapisu pozostają original/aligned, domyślnie bieżący widok.
Zapis z GUI zawsze używa skończonego tła z dokładnymi brakami w V3.
Tłem MPP jest maksimum klatki, a przy braku skończonych próbek zero.
Podgląd i miniatury malują braki na biało po zastosowaniu gamma do pomiaru.
NaN/Inf pozostają w pamięci, maska i historia odtwarzają się z JSON.
Rejestracja, interpolacja i skończone wartości nie zmieniły się.

Kolor MPP zależy od zewnętrznej palety i kontrastu — to liczby, nie RGB.
Dokumentacja wyjaśnia też klatki stałe/puste oraz zakres całego filmu.
Czytnik nadal obsługuje stare V3 z minimum i V1/V2. API zachowało poprzedni
parametr i domyślny zapis NaN; dodatkowych wariantów nie ma już w GUI.
Komunikaty limitu nie sugerują usuniętej opcji interfejsu.

Sprawdzenia:

- Trzy przebiegi TDD red → green na publicznym eksporcie i GUI.
- Zestaw zmiany: **32 passed**, 3.49 s; rzeczywiste Qt xcb na oddzielnym
  ekranie: **13 passed**, 1.22 s. Gamma, białe piksele i miniatury, dialog,
  odczyt i resave starego aligned zostały sprawdzone automatycznie.
- Mypy strict: **26 plików** bez błędów. Największy zmieniony plik kodu:
  **765 linii**. `git diff --check` i linki dokumentacji poprawne.
- Pełne repo raz na końcu: **2038 passed, 14 failed, 16 skipped**, 239.13 s.
  Wszystkie 14 identyfikatorów błędów MolTrack/NanoTrack jest identycznych
  z `/tmp/stmviewer-wsxm-full-suite.log`; brak nowych niepowodzeń.
- `data/MOVIE_3-aligned-white.mpp` + JSON wygenerowano publicznym eksportem
  original z istniejącego aligned. Każda z **17 klatek** zachowuje dokładne
  skończone próbki, a po odczycie V3 także pełne bajty braków i historię.
  Publiczny `check_aligned_mpp.py` ponownie obliczył Optical Flow i potwierdził
  próbki, maskę, geometrię oraz metadane wszystkich klatek.
- Nowy plik otwarto w rzeczywistym WSxM 5.0 Develop 12.0 pod Wine:
  widoczny jasny dodany obszar i szczegóły pomiaru. Wycinek pomiaru:
  **167** kolorów spełniających próg diagnostyczny; zrzut oceniono wizualnie.
- Przegląd Standards: 0 uwag; Spec: 0 uwag. Bez zmian wspólnych modułów.

Logi: `/tmp/stmviewer-white-full-suite.log`, `/tmp/stmviewer-white-xcb.log`,
`/tmp/stmviewer-white-values.log`; WSxM: `/tmp/wsxm-aligned-investigation/white-export-result.log`
i `white-export-frame0.png` (etykieta próby, faktyczna klatka na zrzucie: 8).
Oryginalny pomiar i JSON nie były nadpisywane. Izolowane okno WSxM nie
zmieniało konfiguracji użytkownika. Ręczny odbiór i Windows oczekują.

Uruchom ponownie `python -m stmviewer.main` w środowisku `netcat`.
Stary aligned wystarczy otworzyć i zapisać jako original pod nową nazwą;
nie wymaga ponownej rejestracji. Do analizy przenosić MPP i JSON razem.
Starsze czytniki bez V3 nadal interpretują sztuczne tło jako liczby;
ewentualna wspólna obsługa V3 pozostaje zadaniem sesji integracyjnej.

## 13: Poprawka eksportu WSxM w aplikacji — 2026-10-26

Baza `01259e1`, implementacja **`2343bd6`**, korekta przeglądu **`e013d73`**.
[Poprawka](implementation/issues/13-wsxm-compatibility-fix.md) i ticket 13:
**ready-for-review**, ręczny odbiór użytkownika oczekuje.
[Instrukcja GUI](wsxm-export-manual.md), [kontrakt V3](mpp-metadata-format.md),
[przegląd Standards/Spec](implementation/review-13-wsxm-compatibility.md).

### Zachowanie

Okno zapisu domyślnie wybiera bieżącą wersję original/aligned w wariancie
WSxM. Zachowano wariant NaN i dotychczasowe domyślne API. WSxM zapisuje
skończone tło zamiast NaN/Inf: minimum danej klatki lub zero, gdy nie ma
skończonych wartości. Skończone pomiary i natywny nagłówek nie są zmieniane.
Dodatek V3 przechowuje dokładne pozycje i bity zastąpionych próbek; otwarcie
pary przywraca maskę, NaN/Inf, historię i pochodzenie. Działa też zapis
original po otwarciu wcześniejszego aligned. Odrzucenie błędnego dodatku
nie pozostawia częściowo odtworzonych pikseli. Zapis używa dotychczasowego
postępu, anulowania i przywracania pary przy błędzie.

### Wykonane sprawdzenia

- TDD red → green: publiczny zapis/odczyt, następnie publiczne kontrolki
  GUI (domyślne WSxM i identyczny podgląd z szachownicą po odczycie).
- Końcowy Viewer po poprawce przeglądu: **252 passed, 2 skipped**, 26.74 s.
  Pominięcia dotyczą opcjonalnych wag Deep Matcher. Zakres obejmuje V1/V2/V3,
  niezależny czytnik, NaN payloady/Inf/dziury, błędny/brakujący dodatek,
  rollback/anulowanie i zachowanie alternatywnego zapisu NaN.
- Mypy strict: **26 plików**, bez błędów. Największy zmieniony plik kodu:
  **766 linii**, wszystkie poniżej 1000/1500; `git diff --check` poprawny.
- Pełne repo: **2038 passed, 14 failed, 16 skipped**, 235.44 s.
  Dokładnie te same 14 identyfikatorów niepowodzeń MolTrack/NanoTrack co
  `/tmp/stmviewer-aligned-full-suite.log`; brak nowych. W poprzedniej sesji
  13 odtworzono na bazie, jeden test NanoTrack był niestabilny w pełnym biegu.
  Pierwsze polecenie bez importlib zatrzymało się przy zbieraniu (6 kolizji
  nazw istniejących modułów); pełny przebieg wykonano udokumentowaną komendą:
  `PYTHONPATH=.:tests/moltrack:tests/stmviewer QT_QPA_PLATFORM=offscreen python -m pytest -q --import-mode=importlib -p no:cacheprovider`.
- Qt xcb na oddzielnym ekranie: **4 passed**, 0.96 s. Rzeczywisty dialog
  zapisu, warianty WSxM/NaN, ponowny odczyt, historia i szachownica.
- `data/MOVIE_3.MPP` → Optical Flow → nowy eksporter:
  `data/MOVIE_3-aligned-wsxm.mpp` + `.stmviewer.json` (502 882 B).
  Wszystkie **17 klatek** po otwarciu odzyskują dokładne bajty, NaN,
  geometrię i parametry; kontrola publicznym `check_aligned_mpp.py` zaliczona.
  Resave starego aligned przez original WSxM daje te same bajty MPP.
- MPP jest bajtowo identyczny z diagnostyczną kopią podglądową:
  SHA-256 `dfc7013b984eb05a101070f13a930893e451320bbb6f4b5dc624746e253d6fc4`.
  Nowy plik rzeczywiście otwarto w WSxM 5.0 Develop 12.0 pod Wine:
  obraz ma szczegóły, wycinek zawiera **207** kolorów spełniających próg
  diagnostyczny; zrzut oceniono wizualnie. To nie próba wszystkich wersji WSxM.
- Standards: brak uwag. Spec: drobne P3 komunikatu limitu poprawione
  i zamknięte przez recenzenta; **0 otwartych uwag**.

Logi: `/tmp/stmviewer-wsxm-final-viewer.log`, `/tmp/stmviewer-wsxm-full-suite.log`,
`/tmp/stmviewer-wsxm-collection.log`, `/tmp/stmviewer-wsxm-xcb.log`,
`/tmp/stmviewer-wsxm-values.log`. Próba WSxM i zrzut:
`/tmp/wsxm-aligned-investigation/production-export-result.log`,
`production-export-frame0.png` (etykieta próby, faktyczna pozycja na zrzucie: 5).
Izolowany prefiks i ekran nie zmieniały konfiguracji WSxM użytkownika.

### Odbiór i ograniczenia

Zrestartuj program: `conda activate netcat`, `python -m stmviewer.main`.
Własny stary aligned można otworzyć i zapisać jako **original — WSxM**
bez ponownej rejestracji. [Próba ręczna](wsxm-export-manual.md) pozostaje
użytkownikowi; Windows nie był dostępny. Oryginalny pomiar i JSON bez zmian.
Dla odtworzenia braków przenosić trzeba MPP i JSON razem. Brakujący,
nieprawidłowy lub nieobsługiwany dodatek pozostawia sztuczne skończone tło.
Starsze czytniki repo nie odtwarzają V3: należy do nich wybrać wariant NaN;
ewentualną wspólną obsługę V3 koordynuje sesja integracyjna. Nie zmieniano
wspólnych modułów. Limit dodatku 64 MiB; eksporter ogranicza też liczbę
przedziałów do 500 000. Zapis NaN pozostaje dostępny bez tej listy.

## 13: Diagnoza czarnego aligned w WSxM — 2026-10-26

Na bazie `e49bc6b` sprawdzono zgłoszony `data/MOVIE_3-aligned.mpp`.
[Raport](wsxm-aligned-investigation.md): zapis Optical Flow, nagłówek i
dodatek są poprawne; ponowne obliczenie potwierdza dokładną zgodność
wszystkich 17 klatek, NaN i geometrii. Rzeczywisty WSxM pod Wine pokazuje
czarny obraz przy NaN. Kopia z identycznym nagłówkiem i skończonymi
próbkami, w której zmieniono tylko brakujące piksele na minimum klatki,
odzyskuje szczegóły. Plane i tryb palety nie usuwają błędu oryginału.

Lokalna kopia wyłącznie do oglądania:
`data/MOVIE_3-aligned-wsxm-preview.mpp` oraz opis `.README.txt`.
Oryginał i JSON pozostają bez zmian; kopia nie ma dodatku geometrii/maski.
Nie zmieniono kodu, kontraktu NaN ani statusu **ready-for-review**.
Ręczny odbiór ticketu 13 i próba kopii na Windows oczekują. Automatyczne
GUI Wine oraz kontrola wszystkich próbek zostały wykonane; pełnego
zestawu testów kodu nie ponawiano przy zmianie samej dokumentacji.
Brak potrzebnych zmian wspólnych. Commit dokumentacji podany w odpowiedzi.

## 13: Zapis aligned do MPP — 2026-10-26

Gałąź `viewer/start`. Baza `6ab0837abb5b4e6ba356a1ff6121779302e3585a`.
Implementacja **`ec21f6a`**, poprawki przeglądu **`35858f1`**.
[Ticket 13](implementation/issues/13-aligned-mpp.md): **`ready-for-review`**.
[Próba ręczna](aligned-mpp-manual.md), [kontrakt V1/V2](mpp-metadata-format.md),
[przegląd Standards/Spec](implementation/review-13-aligned-mpp.md).

### Wynik

Zapisz MPP… / Ctrl+S oferuje original/aligned w polu Typ pliku okna zapisu,
domyślnie aktualny widok. Aligned wymaga gotowego wyniku rejestracji.
Oba warianty zapisują całą pozostałą serię, używając wspólnego zapisu
z postępem, anulowaniem i przywracaniem poprzedniej pary przy błędzie.

Eksport aligned zachowuje float64, NaN, pełny obszar, padding, skumulowane
przesunięcia, prostokąty źródeł i historyczne odniesienie — także usunięte.
Nie interpoluje ponownie. Dodatek V2 rozdziela źródłowe pole/offsety od
rozmiaru obszaru aligned i regułę ważności próbek od prostokąta źródła.
Odczyt traktuje zapisane piksele jako nowe wejście original; pokazuje
historię i obrys bez tworzenia fikcyjnych oryginałów ani wyniku rejestracji.
Ponowny zapis original zachowuje historię; nowa rejestracja tworzy nowy etap,
zachowując poprzednie. NaN/Inf blokują obecne backendy z czytelną przyczyną;
skończony plik ze znacznikiem aligned może być rejestrowany.

Przegląd wskazał niespójność tolerancji wspólnej skali: kolejne porównania
mogły uznać dryfujące wartości za wspólne. Teraz wszystkie klatki porównuje
się z jedną skalą odniesienia. Przy niespójności aligned używa pikseli,
a zapis zachowuje indywidualne parametry źródeł. Wspólna walidacja pochodzenia
obsługuje również odniesienie historyczne.

### Sprawdzenia

- TDD na zatwierdzonych granicach: dokładny zapis/odczyt subpikseli po
  usunięciu odniesienia, publiczny wybór wersji i historia w GUI, niespójna
  skala kolejnych etapów oraz regresja dryfujących skal — red → green.
- Końcowy Viewer: **231 passed, 2 skipped**, 23.95 s. Obejmuje V1/V2,
  zachowanie maski i prostokąta osobno, różne/nieznane kalibracje, ponowny
  zapis i rejestrację, błędy dodatku, rollback i anulowanie obu wariantów,
  rzeczywisty dialog Qt oraz odczyt przez trzy dotychczasowe aplikacje.
  Dwa pominięcia dotyczą opcjonalnych testów wag Deep Matcher.
- Mypy strict: **25 plików** bez błędów. Największy zmieniony plik Python:
  `main_window.py`, **767 linii**; wszystkie poniżej 1000/1500.
- Pełny zestaw repo uruchomiony raz przed poprawką przeglądu:
  **2016 passed, 14 failed, 16 skipped**, 239.42 s, bez błędów zbierania.
  Wszystkie niepowodzenia dotyczą MolTrack/NanoTrack. W czystym archiwum
  bazy `6ab0837` uruchomiono te 14 testów: **13 failed, 1 passed**.
  Przechodzący osobno `test_edge_correction_and_resume_replace_suffix`
  przeszedł również na bieżącej gałęzi (0.66 s). To niepowtarzalny lokalnie
  błąd pełnego przebiegu; nie deklarujemy zielonego odbioru całego repo.
  Po poprawce przeglądu uruchomiono pełny zestaw Viewera, bez ponawiania repo.
- Automatyczne Qt xcb na Linuksie: rzeczywisty wybór pliku i wersji w oknie,
  Phase na `subpixel.mpp`, usunięcie odniesienia, gamma 2, zapis i otwarcie.
  Zrzuty pokazują prawidłowy wybór aligned oraz odtworzony obrys 64 × 64
  na obszarze 68 × 67. Skrypt kontrolny potwierdził dokładne próbki,
  3969 ważnych pikseli i całą geometrię.
- Lokalny `data/MOVIE_3.MPP`: Phase, usunięcie pierwszej klatki,
  **16 klatek 398 × 398**, dokładna zgodność bajtów próbek i prostokątów.
  Wyniki zapisano pod nowymi nazwami w `/tmp/stmviewer-ticket13/`.
- Przegląd dwóch niezależnych agentów: Standards — jedna drobna duplikacja;
  Spec — jeden błąd P2 wspólnej skali. Obie poprawki zatwierdzone przez
  recenzentów, **0 otwartych ustaleń** w obu osiach.

Logi lokalne: `/tmp/stmviewer-aligned-full-suite.log`,
`/tmp/stmviewer-aligned-final-viewer-tests.log`,
`/tmp/stmviewer-aligned-baseline-failures.log`,
`/tmp/stmviewer-aligned-edge-repeat.log`, `/tmp/stmviewer-ticket13-probe.log`.
Zrzuty: `/tmp/stmviewer-ticket13/save-dialog.png` i `reopened.png`.

### Odbiór i integracja

Uruchomienie: z katalogu repo `conda activate netcat`, `python -m stmviewer.main`.
Ręczna próba użytkownika **oczekuje**; automatyczne offscreen/xcb nie są jej
zastępstwem. Windows 11 oraz opcjonalne odczytanie aligned z NaN w WSxM
pozostają niesprawdzone w tym etapie. Do ręcznej próby dostarczono istniejące
małe wzorce i `tests/stmviewer/check_aligned_mpp.py` z kontrolą wartości i geometrii.

Nie zmieniono współdzielonych aplikacji ani głównej konfiguracji; brak
nowej blokady integracyjnej. Istniejące czytniki wspólne nadal nie rozumieją
indywidualnej historii JSON; jej obsługa jest lokalna dla STM Viewera.
Historia ma limit 32 etapów i limit dodatku 64 MiB. MPP oraz JSON należy
przenosić razem. Nie jest to atomowa operacja dwóch plików przy twardym
zakończeniu procesu; niezgodny dodatek jest wtedy odrzucany przez SHA-256.


## 12: Potwierdzenie odbioru — 2026-10-26

Użytkownik potwierdził: „testy manualne 12 ok”.
[Ticket 12](implementation/issues/12-original-mpp.md) ma status **`done`**.
Implementacja i poprawki są w zakresie `7756c3d..6282365`, w tym eksport
`678269f`, korekta przeglądu `e24e560` i nagłówek WSxM `b887b2b`/`0cb6644`.
Aktualizacja potwierdzenia obejmuje tylko dokumentację; sprawdzono spójność
statusów i `git diff --check`, bez ponawiania testów kodu.
Nie przypisujemy temu ogólnemu potwierdzeniu pełnego odbioru obu platform;
pozostają osobne tickety platformowe. Ticket 13 — zapis aligned do MPP —
ma spełnione zależności 08 i 12, jest gotowy do podjęcia.

## 12: Nagranie Windows i zakres palety — 2026-10-23

Dalsze zgłoszenie słabego kontrastu w Windows sprawdzono na nagraniu
`bandicam 2026-10-23 19-19-29-772.mp4`. Kopia v2 z pendrive ma ten sam
SHA-256 co sprawdzony film. Objaw odtworzono w WSxM pod Wine przez wybór
zakresu palety całego filmu. Przełączenie **Settings → Movie Settings →
Palette range → Fit to frame Max/Min values**, zatwierdzenie i odświeżenie
klatki przywróciło szczegóły: kontrast percentylowy tej samej klatki 24 → 217.
Zmiana dotyczy wyłącznie konfiguracji podglądu WSxM. Kod i pliki pomiarowe
pozostały bez zmian, więc nie ponawiano testów aplikacji. [Raport](wsxm-investigation.md).
Ręczny odbiór ticketu 12 potwierdzono 2026-10-26. Użytkownik nie opisał
osobno wyniku zmiany ustawienia na Windows.

## 12: Poprawka odczytu MPP w WSxM — 2026-10-23

Baza poprawki: `7eab8e9`. Commity **`b887b2b`**, **`0cb6644`**.
[Raport diagnozy](wsxm-investigation.md),
[przegląd Standards/Spec](implementation/review-12-wsxm.md).

Pierwszy nagłówek CRLF z zakresem wartości przywracał odcienie, ale
pozostawiał przesunięcie obrazu. Nagrania użytkownika ujawniły pasek przy
lewej krawędzi. Rzeczywisty odczyt/zapis wzorca w WSxM wykazał zmianę
pozycji próbek: program odczytywał dane z offsetu odpowiadającego długości
natywnego układu nagłówka, niezależnie od poprawnej deklaracji jego rozmiaru.
Końcowa poprawka odtwarza ten układ, łącznie z wcięciami, odstępami między
sekcjami i pominięciem pustych sekcji. Dane nie są przeskalowywane ani
przesuwane w eksporterze. Pełne indywidualne metadane pozostają w JSON.

Wynik dla użytkownika: **`data/test-wsxm-v2.mpp` + `.stmviewer.json`**.
Oryginał `test.mpp` i pierwsza kopia `test-wsxm.mpp` nie były nadpisane.

Wykonane sprawdzenia:

- Publiczna regresja zapisu: RED przed poprawką, GREEN po poprawce;
  literalny nagłówek oparty na wzorcu sprawdzonym w rzeczywistym WSxM.
- Wszystkie 369 klatek v2 dokładnie zgodne ze źródłowymi S94: wartości,
  parametry, czasy i pochodzenie. Bajty pomiarów identyczne z oryginałem.
- WSxM 5.0 Develop 12.0, Wine 9: otwarcie i zapis całego filmu bez Plane,
  **24 182 784 próbek dokładnie zgodnych**, we właściwej kolejności.
  Oceniono zrzuty klatek 0/184/368; brak paska. Dodatkowy prostokątny
  film z czasami 2/5/9 s: **18 432 próbek zgodnych**, czasy zachowane.
- Końcowy zestaw Viewera: **217 passed, 2 skipped**, 22.07 s;
  obejmuje eksport przez czytniki NaPara/NanoTrack/MolTrack.
  Mypy strict: **23 pliki** bez błędów. `git diff --check` poprawny.
- Pełny zestaw repo po pierwszej poprawce: **2002 passed, 14 failed,
  16 skipped**, 230.78 s. Wszystkie identyfikatory niepowodzeń są zgodne
  z ticketem 12; brak nowych błędów. Końcowa korekta miała następnie pełne
  sprawdzenie Viewera, bez ponawiania całego repo.
  Logi: `/tmp/stmviewer-wsxm-full-suite.log`,
  `/tmp/stmviewer-wsxm-edge-viewer-tests.log`.
- Przegląd: Standards bez naruszeń, jedna uwaga do nieaktualnego opisu
  testu poprawiona; Spec bez uwag. Największy zmieniony plik kodu: 234 linie.

Próby Wine były automatyczne, sterowane GUI. Ręczny odbiór użytkownika
potwierdzono 2026-10-26; ticket 12 ma status `done`. Windows 11, NaN
w WSxM oraz indywidualna kalibracja JSON w tym zewnętrznym programie nie
zostały potwierdzone. Zmiana nie obejmuje wspólnych modułów. Instalacja
Wine/WSxM, dane i artefakty `/tmp/wsxm-investigation/` pozostają lokalne.


## 12: Zapis original do MPP — 2026-10-23

Gałąź `viewer/start`. Baza `7756c3d6e018ad1820f7400dc2d606b49d0975f2`.
Implementacja **`678269f`**, poprawki przeglądu **`e24e560`**.
[Ticket 12](implementation/issues/12-original-mpp.md): `done` po potwierdzeniu
ręcznego odbioru użytkownika 2026-10-26.

### Wynik

Przycisk Zapisz original MPP…, menu Plik i Ctrl+S zapisują całą pozostałą
serię original do MPP i `<nazwa MPP>.stmviewer.json`. Jedna klatka jest
obsługiwana; pusta seria wyłącza zapis. Wybrana klatka ani widok aligned
nie zmieniają zakresu. Gamma, zoom i opcja proporcji pikselowych nie trafiają
do eksportera. Dane to float64 little endian w konwencji orientacji MPP;
zachowane są NaN, pełne wymiary i dokładne skończone wartości.

Dodatek [V1](mpp-metadata-format.md) zachowuje własne parametry każdej klatki,
surowe nagłówki, braki i przerwy czasu oraz historyczne pochodzenie.
Wspólny nagłówek ma tylko wspólne znane parametry, a przy różnicach/nieznanych
wartościach jednostki umowne i Unknown. Znany prąd zapisuje się w nA, ponieważ
wspólny starszy parser myli A z angstromem. Pełne długie teksty pozostają
w JSON; reprezentacja w nagłówku mieści się w limicie czytnika.

Worker zapisuje dane partiami wierszy, bez kopii całej serii. Zapisany snapshot
to niezmieniana podczas operacji krotka obrazów. UI zatrzymuje Play i blokuje
nowy import, usuwanie, rejestrację oraz kolejny zapis; przeglądanie/gamma/zoom
pozostają dostępne. Przycisk Anuluj i zamknięcie okna kończą operację przez
worker. Spóźnione anulowanie po zakończonej publikacji nie udaje wycofania.

MPP i JSON powstają w katalogu tymczasowym obok celu. Przed podmianą
zabezpieczane są kopie istniejących plików; błąd/anulowanie przywraca parę.
Gdy samo przywracanie zawiedzie, kopie pozostają, a komunikat wskazuje katalog.
Dwa renamy nie są transakcją odporną na twarde zakończenie procesu: jeśli
pozostanie nowy MPP ze starym JSON, import wykryje niezgodność SHA-256.
Przerwanie procesu między podmianami sprawdzono osobnym podprocesem.

### Sprawdzenia

- TDD RED → GREEN: zapis z niezależnymi oczekiwaniami bajtowymi; bezpieczeństwo
  zastępowania pary; publiczne kontrolki GUI; poprawka długich tekstów UTF-8.
  Testy obejmują STP/S94/MPP, NaN, skrajne float64 i ujemne zero, długi
  nagłówek, indywidualne metadane, przeniesienie pary, błąd/krótki zapis,
  anulowanie pomiędzy publikacjami, twarde zakończenie procesu, blokady GUI,
  potwierdzenie nadpisania także samego JSON i zamknięcie podczas zapisu.
- Zestaw Viewera: **214 passed, 2 skipped**, 21.78 s. Pominięte istniejące
  opcjonalne testy lokalnego LoFTR; eksport nie zmienia modelu.
  Po poprawce przeglądu **38 passed**, 3.53 s: eksport, bezpieczeństwo,
  GUI eksportu, import metadanych i GUI importu; zawiera dodatkowy test UTF-8.
  Mypy strict: **23 pliki**, bez błędów.
- Pełny zestaw repo uruchomiony raz:
  `PYTHONPATH=.:tests/moltrack:tests/stmviewer QT_QPA_PLATFORM=offscreen python -m pytest -q --import-mode=importlib --continue-on-collection-errors -o cache_dir=/tmp/stmviewer-original-mpp-full-pytest`.
  Kompletny log: **2000 passed, 14 failed, 16 skipped**, 231.70 s,
  bez błędów zbierania. Wszystkie 14 identyfikatorów niepowodzeń jest identyczne
  z `/tmp/stmviewer-mpp-metadata-full-suite.log`; brak nowych niepowodzeń.
  Log bieżący: `/tmp/stmviewer-original-mpp-full-suite.log`. Narzędzie sesji
  procesu zwróciło kod 143 po pełnym podsumowaniu pytest; podane wyniki
  pochodzą z logu zawierającego 100% testów i końcową listę niepowodzeń.
  Zestaw rozpoczęto dla `678269f`; poprawkę `e24e560` sprawdzono wymienionymi
  38 testami i mypy. Nie deklarujemy zielonego odbioru całego repo.
- Automatyczne rzeczywiste Qt xcb z dialogami: zapis/ponowne otwarcie
  znanych czasów po usunięciu środka, S94, mieszanych metadanych oraz
  **MOVIE_3: 17 klatek 256 × 256**. Dokładne wartości i parametry zachowane;
  źródła mają niezmienione SHA-256. Obejrzano dwa zrzuty podglądu.
  Skrypt/log/manifest: `/tmp/stmviewer-original-mpp-smoke.{py,log,json}`.
  Zrzuty: `/tmp/stmviewer-original-mpp-{saved,reopened}-xcb.png`.
- Sprawdzono CLI porównania eksportu na dwóch klatkach po usunięciu środka
  oraz generator wzorca na 4 × 16 × 16 z NaN i jego zapis/odczyt.
  Nie jest to odbiór dużej serii 1000 × 512 × 512 z ticketu 18/19.
- [Przegląd](implementation/review-12-original-mpp.md): jedno P2 Spec i drobna
  heurystyka Standards zamknięte po poprawce; **0 otwartych uwag** w obu osiach.
  Największy zmieniony plik kodu: **751 linii**, poniżej celu 1000 i limitu 1500.
  Sprawdzono lokalne odnośniki dokumentacji i `git diff --check`.

### Ręczny odbiór i integracja

[Instrukcja manualna](original-mpp-manual.md) podaje uruchomienie, gotowe dane,
generator dużego wzorca, raport dokładnego porównania oraz oczekiwane wyniki.
Ręczna próba użytkownika **potwierdzona 2026-10-26**; Qt offscreen i xcb
pozostają odrębnymi próbami automatycznymi. Dodatkowe sprawdzenia WSxM
opisano powyżej; potwierdzenie ticketu nie zamyka odbiorów platformowych.

Zmiany tylko w Viewerze, jego testach i dokumentacji. Nowych zależności nie ma;
bez zmian wspólnego kodu, konfiguracji, środowiska i pomiarów. Bez push/scalania.
Istniejące czytniki NaPara/NanoTrack/MolTrack czytają wartości i wspólne parametry
z typowych filmów. NaPara zwraca kolejność plikową, NanoTrack/MolTrack wykonują
własny obrót 180°. Dla integracji pozostają znane ograniczenia wspólnego
czytnika: limit 1000 linii nagłówka, błędna interpretacja A, nieznanej skali
oraz brak indywidualnych metadanych JSON. Eksporter używa nA; pełen kontrakt
nieznanych i mieszanych parametrów zapewnia para otwierana w Viewerze.
Eksport aligned i geometria są zakresem ticketu 13, odblokowanego po
potwierdzeniu ręcznego odbioru ticketu 12.

## 11: Otwarcie MPP z metadanymi towarzyszącymi — 2026-10-23

Gałąź: `viewer/start`. Baza implementacji i przeglądu:
`b71305bfb2886d734cc087708780f22ea12fd30d`. Implementacja: `137655d`.
Ticket: [11-mpp-metadata-import](implementation/issues/11-mpp-metadata-import.md).
Status: `done` po potwierdzeniu ręcznego odbioru użytkownika 2026-10-23.
Raport implementacji i przeglądu: `33a672b`. Commit potwierdzenia odbioru
podany w wiadomości sesji.

### Wynik i kontrakt

MPP automatycznie szuka obok siebie dodatku `<pełna nazwa MPP>.stmviewer.json`.
[Kontrakt V1](mpp-metadata-format.md) wiąże go ze wszystkimi bajtami filmu
przez SHA-256, liczbą oraz kształtem klatek. Skrót powstaje na tych samych
bajtach, które są dekodowane; uwzględnia nagłówek i ewentualny koniec pliku.
Przeniesienie lub wspólna zmiana nazwy pary zachowuje powiązanie.

Adapter w Viewerze waliduje cały JSON przed nałożeniem jakichkolwiek danych.
Wersja, format, rodzaj obrazu, komplet pól, typy, skończone wartości, dodatnia
skala i integralność muszą się zgadzać. JSON UTF-8 ma limit 64 MiB; powtórzone
klucze, NaN i Infinity są odrzucane. Błąd dowolnego rekordu odrzuca cały
dodatek. Brak, nieprawidłowy dodatek i błąd jego odczytu pozostawiają działający
film z metadanymi nagłówka oraz widoczną przyczyną. Anulowanie jest odrębne:
zachowuje poprzednią serię, jej pozycję, gamma i kadr. Praca jest w istniejącym
workerze, z punktami anulowania przy odczycie i walidacji rekordów.

Każda klatka odzyskuje własne parametry, kanał, jednostkę, surowy nagłówek,
czasy i ich źródłowy opis oraz informację o kalibracji. Null i rzeczywiste
zero pozostają rozróżnione; nie zgadujemy parametrów z nagłówka ani nie
przeliczamy próbek. `ImageFrame.source` oraz `source_frame_index` nadal
wskazują faktycznie otwarty plik i indeks w nim. Nowe `provenance` przechowuje
historyczną ścieżkę jako tekst i historyczny indeks od zera. Ścieżka jest
zachowana dosłownie, także Windows i względna; nie jest rozwiązywana/otwierana.

Panel i podpowiedzi miniatur rozdzielają obie lokalizacje i numery;
miniatury pokazują historyczne nazwy, a bieżąca pozycja nadal należy do serii.
Usuwanie nie zmienia pochodzenia pozostałych klatek. Komunikat o dodatku
pozostaje przy nawigacji i znika po opróżnieniu lub otwarciu STP/S94.

### Sprawdzenia i odbiór

- TDD red → green: indywidualne metadane przez publiczny import; odrzucenie
  całego nieprawidłowego dodatku; prezentacja przez publiczne kontrolki GUI.
  Pozostałe próby obejmują zmianę nagłówka/próbek/końca MPP, przeniesienie
  i zmianę nazwy pary, null/zera/typy, brak/uprawnienia, anulowanie odczytu
  dodatku i zachowanie starego podglądu. Oczekiwane liczby i orientacja
  wzorców są niezależne od przyszłego eksportera.
- **193 testy Viewera zaliczone, 2 pominięte**, 18.86 s. Pominięcia to
  istniejące opcjonalne próby rzeczywistego LoFTR bez ścieżki do wag;
  ticket 11 nie dotyka modelu. **Mypy strict: 21 plików**, bez błędów.
- Automatyczne rzeczywiste GUI Qt xcb z dialogami plików: poprawny dodatek,
  sześć przypadków braku/odrzucenia, wszystkie klatki i parametry, przeniesiona
  oraz przemianowana para, usunięcie pierwszej klatki z zachowaniem obu
  indeksów, lokalny MOVIE_3 (17 klatek) bez dodatku — zaliczone.
  Źródła zachowały SHA-256. Obejrzano zrzuty poprawnego i odrzuconego dodatku.
  Skrypt/log/manifest: `/tmp/stmviewer-mpp-metadata-smoke.{py,log,json}`;
  zrzuty `/tmp/stmviewer-mpp-metadata-{valid,rejected,measurement}-xcb.png`.
- Pełne repo uruchomione raz w netcat:
  `PYTHONPATH=.:tests/moltrack:tests/stmviewer QT_QPA_PLATFORM=offscreen python -m pytest -q --import-mode=importlib --continue-on-collection-errors -o cache_dir=/tmp/stmviewer-mpp-metadata-full-pytest`:
  **1979 passed, 14 failed, 16 skipped**, 229.88 s, bez błędów zbierania.
  Wszystkie 14 niepowodzeń MolTrack/NanoTrack jest identyczne z ticketem 10;
  nie ma nowych niepowodzeń. Całe repo nadal nie ma zielonego odbioru.
  Log `/tmp/stmviewer-mpp-metadata-full-suite.log`; porównanie z
  `/tmp/stmviewer-deep-full-suite.log`.
- [Code-review](implementation/review-11-mpp-metadata-import.md): Standards — 0,
  Spec — 0. Kod po przeglądzie niezmieniony. Generator odtwarza wszystkie
  13 plików bajtowo. `git diff --check` i lokalne odnośniki poprawne;
  największy zmieniony plik kodu ma **640 linii**, poniżej celu 1000 i limitu 1500.
- [Instrukcja manualna](mpp-metadata-manual.md) zawiera uruchomienie,
  gotowe poprawne/błędne pary i oczekiwane parametry. Użytkownik potwierdził
  ręczny odbiór 2026-10-23: „testy manualne ok”. Nie wskazał systemu;
  potwierdzenie nie zamyka odrębnych odbiorów platform. Tekstowe ścieżki
  Windows sprawdzono automatycznie na Linuksie; to nie zastępuje odbioru
  Windows. Aktualizacja odbioru zmienia wyłącznie dokumentację; testów
  automatycznych nie ponawiano.

### Integracja i następne etapy

Zmiany wyłącznie w Viewerze, jego testach i dokumentacji. Nie zmieniono
wspólnych czytników, konfiguracji głównej, środowiska ani lokalnych pomiarów.
Nowych zależności nie ma; moduły modelu/metadanych nie importują Qt.
Nie publikowano ani nie scalano gałęzi.

Ticket 12 powinien zapisywać ten kontrakt dla original. Przy ponownym
zapisywaniu zaimportowanej pary należy zachować istniejące `provenance`;
dla klatki bez niego pochodzenie pochodzi z `source/source_frame_index`.
Nie należy zastępować historii nazwą najnowszego kontenera MPP. Wersja 1
jawnie odrzuca rodzaj aligned; ticket 13 ma rozszerzyć wersjonowany kontrakt
z zachowaniem odczytu V1 i dodać geometrię, maskę, historyczne odniesienie
oraz ich podgląd. Ten etap nie wprowadza eksportera ani odtwarzania historii
rejestracji, nie obiecuje zgodności dodatku z zewnętrznymi programami.


## 10: Diagnoza obwódki na cpu.mpp — 2026-10-23

Baza: `3ba1ea0`, gałąź `viewer/start`. Zmiana wyłącznie dokumentacji:
[wyjaśnienie i porównanie w GUI](deep-matcher-manual.md#obwódka-przy-ostrych-krawędziach-wzorca).
Diagnoza zapisana w `2b13195`. Następnie użytkownik potwierdził ręczny odbiór
2026-10-23; ticket 10 ma status `done`. Samo wcześniejsze zgłoszenie
nie stanowiło jeszcze odbioru.

Dwie próby rzeczywistego LoFTR CPU odtworzyły pas przy krawędzi ciemnego
obiektu. Klatka 3: XY = (−0,7461051941; +0,9392890930) wobec dokładnego
(−1; +1) wynikającego z generatora `np.roll`. W punkcie lewej krawędzi
różnica względem klatki odniesienia wynosi 0,352253 jednostki danych.
Minimalna próba z dwiema klatkami i tym zmierzonym przesunięciem odtwarza
identyczny efekt bez modelu i GUI. Zmiana wyłącznie przesunięcia na (−1; +1)
sprowadza tę różnicę do zera. Rzeczywisty Phase również daje (−1; +1) i zero.

Niezależny rachunek wag czterech sąsiadów dla wszystkich 6241 ważnych próbek
klatki 3 potwierdza interpolację biliniową z maksymalnym błędem
4,44 × 10⁻¹⁶. Żadna próbka nie wychodzi poza zakres swoich czterech sąsiadów.
Na lewej krawędzi udział tła wynosi 25,3895%, obiektu 74,6105%.
To wyjaśnia pas wartości pośrednich widoczny na zrzucie. Nie jest wymagane
poprawianie implementacji interpolacji; zaokrąglenie do pikseli zmieniłoby
uzgodniony kontrakt rejestracji subpikselowej. Zmierzony błąd estymacji modelu
mieści się w obecnej tolerancji testu 0,75 px; nie dowodzi dokładności
modelu na innych obrazach. Nie zmieniono kodu, danych ani wag.

Diagnostyka lokalna: `/tmp/stmviewer-halo-probe.py` (rzeczywisty model),
`/tmp/stmviewer-halo-minimal.py` (domyślnie zmierzona translacja;
`--integer` przełącza na dokładną), macierze `/tmp/stmviewer-halo-arrays.npz`
i porównanie `/tmp/stmviewer-halo-comparison.png`. Warunek wykrywający
widoczny pas celowo zgłasza błąd w obu próbach ułamkowych i przechodzi
w próbie całkowitej. Jest to detektor objawu, nie nowy wymóg testów aplikacji.
Zrzut porównania obejrzano. Wszystkie próby automatyczne; GUI użytkownika
oraz Windows nie były ponownie testowane. Pełnego zestawu nie powtarzano
przy tej zmianie dokumentacji. Commit przekazania podany w wiadomości sesji.


## 10: Deep Matcher z lokalnymi wagami — 2026-10-23

Gałąź: `viewer/start`. Baza implementacji i przeglądu:
`d899ea0648af2ab507b41fc24d2c2bdcf5c356c2`. Commit implementacji: `30ddddf`.
Ticket: [10-deep-matcher](implementation/issues/10-deep-matcher.md).
Status: `done` po potwierdzeniu ręcznego odbioru użytkownika 2026-10-23.
Raport implementacji i przeglądu: `3ba1ea0`; diagnoza obwódki: `2b13195`.
Commit potwierdzenia odbioru podany w wiadomości sesji.

### Wynik i kontrakt

Deep Matcher ma pole lokalnego checkpointu, wybór Auto/CPU/CUDA i Sprawdź
model. Pole można wypełnić przez `STMVIEWER_LOFTR_WEIGHTS`. Domyślnie jest
puste. Wstępna kontrola sprawdza plik i moduły, bez importowania modelu;
panel nie twierdzi wtedy, że model został już zweryfikowany. Sprawdź model
można uruchomić przed wczytaniem obrazów; nie zmienia istniejącego aligned.

Import bibliotek, ładowanie i weryfikacja wag oraz rejestracja działają
w QThread, z postępem i punktami anulowania. Checkpoint jest czytany przez
`torch.load(weights_only=True)` na CPU, następnie `LoFTR(pretrained=None)`
sprawdza ścisłą zgodność parametrów i przechodzi na wybrane urządzenie.
Nie ma pobierania bibliotek/wag. Auto wybiera CUDA, gdy Torch zgłasza jego
obecność, inaczej CPU; błąd wykonania na CUDA nie powoduje ponowienia na CPU.
Wykonywana jest rzeczywista operacja na urządzeniu, a wynik zapisuje jego
numer/nazwę. Zmiana wyboru metody lub urządzenia nie zmienia starego wyniku.

Każde Rejestruj ponownie ładuje wskazany plik. Jeden model obsługuje wszystkie
pary danej próby. Adapter zachowuje normalizację NanoTrack i domyślny
konsensus translacji XY. Wykorzystuje istniejący punkt
`DeepMatcherTranslationBackend(matcher=...)`, bez modyfikacji wspólnego kodu.
Geometria, sąsiednie oryginały, kumulacja względem pierwszej klatki, statusy,
interpolacja, publikacja kompletnego wyniku i usuwanie pozostają wspólne
z wcześniejszymi metodami. Błąd, brak zasobów i anulowanie zachowują poprzedni
wynik. Rozdzielczość wejścia nie jest zmieniana dla modelu.

### Sprawdzenia i odbiór

- TDD red → green w zatwierdzonych granicach rejestracji i publicznego GUI.
  Kontrolowany model używa prawdziwego Torch i konsensusu NanoTrack;
  sprawdza znane XY, lokalny odczyt, niezgodne/uszkodzone/brakujące wagi,
  brak bibliotek, Auto/CPU/CUDA, błędy zasobów i anulowanie. Testy GUI
  sprawdzają stare aligned, blokady, nawigację, gamma i zoom w trakcie pracy.
- **177 testów Viewera zaliczonych, 2 opcjonalne pominięte**, 18.58 s.
  Te dwie próby rzeczywistych wag wykonano osobno po ustawieniu
  `STMVIEWER_TEST_LOFTR_WEIGHTS`: **2 passed**, CPU i CUDA, 1.72 s,
  przy zablokowanych funkcjach pobierania. Log: `/tmp/stmviewer-deep-real-tests.log`.
  **Mypy strict: 19 plików**, bez błędów.
- Rzeczywisty checkpoint LoFTR outdoor: 46 341 978 bajtów,
  SHA-256 `21f5bec5968178e8bc8b7633441836fe5de4f47d861dd2cd7dc38e271b0479ec`,
  11 561 456 parametrów. Ścieżka w [instrukcji](deep-matcher-manual.md).
  Torch 2.9.1+cu128, Kornia 0.8.2, kornia_rs 0.1.10; CUDA:0,
  NVIDIA GeForce RTX 5090. Sprawdzono rzeczywistą operację CUDA oraz model,
  a nie samą nazwę GPU. Niczego nie instalowano ani nie pobierano.
- Automatyczne GUI Qt xcb z prawdziwymi dialogami: Phase → brak wag →
  wybór pliku → Sprawdź model/Rejestruj na CPU, CUDA i Auto. Dla klatki 2
  wzorca CPU: XY około (1.955, −1.072), CUDA: (1.956, −1.072), obszar 83 × 83.
  Auto wybrało CUDA. Błędne wagi i rzeczywiste anulowanie zachowały stary wynik.
  Pełny MOVIE_3, 17 klatek, zakończył się wynikiem 312 × 291 px.
  To potwierdzenie wykonania i prezentacji, nie fizycznej poprawności każdego
  dopasowania. Źródła oraz wagi zachowały SHA-256. Obejrzano zrzuty GUI.
  Skrypt/log/manifest: `/tmp/stmviewer-deep-smoke.{py,log,json}`;
  zrzuty `/tmp/stmviewer-deep-{CPU,CUDA,Auto,measurement}-xcb.png`
  oraz `/tmp/stmviewer-deep-missing-settled-xcb.png`.
- Pełne repo, uruchomione raz w netcat:
  `PYTHONPATH=.:tests/moltrack:tests/stmviewer QT_QPA_PLATFORM=offscreen python -m pytest -q --import-mode=importlib --continue-on-collection-errors -o cache_dir=/tmp/stmviewer-deep-full-pytest`:
  **1963 passed, 14 failed, 16 skipped**, 227.13 s, bez błędów zbierania.
  Zestaw 14 niepowodzeń MolTrack/NanoTrack jest identyczny z ticketem 09;
  brak nowych niepowodzeń. Całe repo nadal nie ma zielonego odbioru.
  Log `/tmp/stmviewer-deep-full-suite.log`; porównanie z
  `/tmp/stmviewer-cpu-full-suite.log`.
- [Code-review](implementation/review-10-deep-matcher.md): Standards — 0,
  Spec — 0. Kod po przeglądzie niezmieniony. `git diff --check` i lokalne
  odnośniki dokumentacji poprawne; największy zmieniony plik kodu ma 634 linie.
- [Instrukcja manualna](deep-matcher-manual.md) zawiera uruchomienie,
  wzorzec, lokalne wagi i scenariusze. Użytkownik potwierdził ręczny odbiór
  2026-10-23: „testy manualne ok”, po wyjaśnieniu obwódki interpolacyjnej.
  Nie wskazał systemu ani urządzenia użytego do próby; potwierdzenie nie
  zamyka odrębnych odbiorów platform. Aktualizacja odbioru dotyczy wyłącznie
  dokumentacji; testów automatycznych nie ponawiano.

### Integracja

Zmiany wyłącznie w Viewerze, jego testach i dokumentacji. Wspólne moduły,
konfiguracja główna, pomiary i istniejące środowisko netcat niezmienione.
Opcjonalne zależności zapisano w `stmviewer/requirements-deep.txt`;
instrukcja rozdziela instalację CPU i CUDA. Ewentualne wspólne wydzielenie
lokalnego loadera może prowadzić integracja, ale nie blokuje tej funkcji.
Nie publikowano ani nie scalano gałęzi.

## 09: Pozostałe metody rejestracji CPU — 2026-10-23

Gałąź: `viewer/start`. Baza implementacji i przeglądu:
`b8dcc4596988e8a2ee529f60b860f030b1be9749`.
Ticket: [09-cpu-registration-methods](implementation/issues/09-cpu-registration-methods.md).
Status: `done` po potwierdzeniu ręcznego odbioru użytkownika 2026-10-23.
Commit implementacji: `3e31161`; poprawka importu testowego: `5d4ea6b`.
Raport implementacji i przeglądu: `935c638`; pełny zakres `b8dcc45..HEAD`.
Commit potwierdzenia ręcznego odbioru podany w wiadomości sesji.

### Wynik i kontrakt

Lista rejestracji zawiera Phase, Tile+RANSAC, ECC i Optical Flow.
Adapter używa istniejącej `build_registration_backend_from_settings` NanoTrack,
`reference_strategy=adjacent`, `registration_view=raw`, pustych backend_params.
Nie zmieniano algorytmów, progów ani domyślnych parametrów. ECC ma własne
wstępne oszacowanie Phase, a Optical Flow używa mediany TV-L1 do wyznaczenia
jednego przesunięcia XY. Brak automatycznego zastępowania metody po błędzie.

Wybór jest zapamiętany w uruchomionym zadaniu, a nazwa metody w kompletnym
wyniku. Zmiana listy nie zmienia starego aligned, jego opisu ani kadru.
Wszystkie metody korzystają z cyklu, geometrii, interpolacji i anulowania
wprowadzonego w tickecie 08. Usuwanie zachowuje także metodę starego wyniku.
Niska pewność/manual_review pozostają dostępne i są dziedziczone jak wcześniej.
Błąd, failed, brak wyniku lub nieprawidłowe XY odrzuca całą nową próbę.

Lokalna dostępność sprawdzana jest przy starcie okna. Brak OpenCV wyłącza
wyłącznie ECC. Brak SciPy/scikit-image wyłącza rejestrację, zachowując start
aplikacji, import i przeglądanie. Powód pojawia się osobno od opisu starego
wyniku; niedostępne metody pozostają na liście. Instalacja biblioteki wymaga
ponownego startu. Program nie instaluje ani nie pobiera zależności.

### Sprawdzenia i odbiór

- TDD: red → green dla wyboru realnych backendów i porównania z domyślnym
  NanoTrack, wyboru metody w GUI oraz braku OpenCV. Kontrolowane wyniki
  i błędy uzupełniają próby prawdziwych metod; nie zastępują oceny dopasowania.
- **155 testów Viewera zaliczonych**, w tym 32 nowe. **Mypy strict: 17 plików**
  bez błędów. Opcjonalne cv2 ma ignore_missing_imports w lokalnej konfiguracji.
- Nowe testy obejmują wszystkie trzy metody, znane XY, status/quality zgodne
  z NanoTrack, postęp, usuwanie oraz zachowanie starego aligned po anulowaniu,
  wyjątku, failed, braku wyniku i nieprawidłowym XY. Kontrolowane manual_review
  i low_confidence sprawdzają kompletny wynik, dziedziczenie i ostrzeżenia GUI.
- Osobne procesy z pustym cache importów i kontrolowanym brakiem cv2/scipy/skimage:
  rzeczywisty start okna, import MPP i widoczne powody niedostępności przeszły.
  To symulacja na granicy importu bibliotek, nie instalacja nowego środowiska.
- Automatyczna próba Qt xcb z rzeczywistymi dialogami: cztery metody na
  `cpu.mpp` i `data/MOVIE_3.MPP`, zmiana wyboru, błąd ECC, rzeczywiste anulowanie
  Optical Flow, usunięcie odniesienia — zaliczona. SHA-256 źródeł zachowane.
  Obejrzano zrzuty ECC/wzorca i Optical Flow/pomiaru. To nie ręczny odbiór.
  Skrypt, log i manifest: `/tmp/stmviewer-cpu-smoke.{py,log,json}`;
  zrzuty `/tmp/stmviewer-cpu-{cpu,MOVIE_3}-{Phase,TileRANSAC,ECC,OpticalFlow}.png`.
- Na wzorcu 80 × 80 przesunięcia są zgodne z (0,0), (2,−1), (−1,1),
  z tolerancją 0,3 px dla metod subpikselowych. Aligned: Phase/Tile 83 × 82,
  ECC 84 × 83, Optical Flow 84 × 84 px. Generator odtwarza plik bajtowo.
- Lokalny MOVIE_3, 17 klatek: Phase 398 × 398, Tile+RANSAC 256 × 305,
  Optical Flow 274 × 281 px, z oznaczeniami niepewności. ECC nie zbiega się
  dla pary 2 → 3 i zachowuje wcześniejszy wynik. To test kontraktu i prezentacji,
  nie potwierdzenie fizycznej poprawności dopasowań każdego pomiaru.
- Pełne repo uruchomione raz w netcat:
  `PYTHONPATH=.:tests/moltrack:tests/stmviewer QT_QPA_PLATFORM=offscreen python -m pytest -q --import-mode=importlib --continue-on-collection-errors -o cache_dir=/tmp/stmviewer-cpu-full-pytest`:
  **1934 passed, 14 failed, 14 skipped, 1 błąd zbierania**, 225.91 s.
  Log: `/tmp/stmviewer-cpu-full-suite.log`. Wszystkie 14 niepowodzeń
  MolTrack/NanoTrack jest identyczne z listą ticketu 08; brak nowych failed.
  Nowy błąd zbierania wynikał z importu `test_registration` z MolTrack zamiast
  pomocnika Viewera. Poprawiono w `5d4ea6b`, używając publicznego odczytu gotowego
  `cpu.mpp`. Powtórka dwóch modułów CPU wraz z kolidującym modułem MolTrack
  w tej samej konfiguracji ścieżek/importlib: **36 passed**, 2.36 s.
  Ponowne zbieranie całego repo: **1969 testów, bez błędów**, 0.85 s;
  log `/tmp/stmviewer-cpu-collection.log`. Całego wykonania nie powtarzano.
  Pełny zestaw repo nadal nie ma zielonego odbioru.
- [Przegląd Standards/Spec](implementation/review-09-cpu-registration.md):
  Standards — 0; Spec — 0, także po poprawce testu. Kod aplikacji po przeglądzie
  nie był zmieniany. `git diff --check` bez błędów; największy zmieniony plik
  Python ma **608 linii**, poniżej celu 1000 i limitu 1500.
- [Instrukcja manualna](cpu-registration-manual.md), wzorzec i generator są
  w repo. Użytkownik potwierdził pozytywny wynik testów manualnych 2026-10-23.
  Nie podał systemu ani szczegółów osobnej próby środowiska bez OpenCV.
  Potwierdzenie zamyka ticket 09, lecz nie oznacza zaliczenia odrębnych
  odbiorów platform. Zmieniono wyłącznie dokumentację; testów automatycznych
  nie ponawiano.

### Integracja

Zmiany wyłącznie w Viewerze, jego testach i dokumentacji. Wspólne moduły,
konfiguracja główna i pomiary pozostają bez zmian. Podstawowy zestaw zależności
obsługuje Phase/Tile/Optical Flow. Lokalny `stmviewer/requirements-ecc.txt`
dodaje opencv-python 4.11.0.86, użyty w netcat; [README](README.md#uruchomienie)
podaje instalację dla Ubuntu 24.04 i Windows 11. Zmiana wspólnych zależności
nie jest potrzebna do tego ticketu. Deep Matcher pozostaje w tickecie 10.

## 08: Rejestracja Phase i pełny widok aligned — 2026-10-23

Gałąź: `viewer/start`. Baza implementacji i przeglądu:
`1dc159ee48341b2180cea47947a3fb38d59dd0c6`.
Ticket: [08-phase-registration](implementation/issues/08-phase-registration.md).
Status: `done` po potwierdzeniu ręcznego odbioru użytkownika 2026-10-23.
Commit implementacji: `2fea452`; końcowy raport: `c4c6fe5`.
Commit potwierdzenia ręcznego odbioru podany w wiadomości sesji.

### Wynik i kontrakt

Lokalny runner korzysta z istniejącego `PhaseCorrelationShiftBackend`
(default: upsample 20, normalization phase, min_texture_std 1e-8,
peak_exclusion_radius 3, low_confidence_peak_ratio 3). Jak NanoTrack UI używa
raw, sąsiednich oryginałów i kumulacji XY, jakości minimum i najgorszego statusu.
Nie zmieniano algorytmu ani progów. Pojedyncza klatka ma przesunięcie zerowe.

`RegistrationResult` przechowuje pole każdej klatki, przesunięcia, status,
maskę, cały obszar i lekkie historyczne pochodzenie odniesienia. Metadane
źródeł pozostają w oryginalnych `ImageFrame`. Aligned ma float64 i NaN,
SciPy affine_transform order=1, constant NaN, bez ekstrapolacji. Geometria
odpowiada NanoTrack (ceil marginesów); lokalny materializator zachowuje
float64 oraz punkty anulowania między klatkami. Wspólna kalibracja wynika
z każdej klatki, a przy braku/niezgodności aligned ma proporcje pikselowe.
Pole źródłowe opisuje prostokąt krawędzi pikseli; maska nie określa jego rozmiaru.

QThread publikuje tylko kompletny wynik. Start zatrzymuje Play i blokuje
import/usuwanie/metodę/Play/kolejną próbę. Nawigacja, widoki i ustawienia
obrazu pozostają dostępne. Anulowanie utrzymuje blokady do końca pracy;
zamykanie okna także czeka na zakończenie. Błąd lub anulowanie zachowują
stary wynik i zmiany bieżącego podglądu. Sukces dopasowuje nowe aligned
aktualnej klatki, zachowuje gamma i zapisany kadr original.

Miniatury pozostają original gamma 1; ostrzegają o niepewności, także
odziedziczonej. Usuwanie nie interpoluje ponownie, nie przycina obszaru
ani nie usuwa historycznego odniesienia/niepewności. Rejestracja po usunięciu
korzysta z pozostałych oryginałów i tworzy nowe odniesienie. Nowa seria
czyści wynik; nieudany import go zachowuje.

### Sprawdzenia i odbiór

- TDD w uzgodnionych granicach: znaki/kumulacja, subpiksele i maska ≠ pole,
  anulowanie aligned, błędy i niekompletny wynik, historyczne odniesienie,
  wspólna skala, GUI i bezpieczne zamknięcie. Kontrolowane wyniki backendu
  sprawdzono osobno od rzeczywistego Phase oraz porównania z runnerem NanoTrack.
- **123 testy Viewera zaliczone**, w tym 20 nowych; **mypy strict 17 plików**.
- Automatyczna próba Qt xcb z rzeczywistymi dialogami i lokalnym MOVIE_3.MPP
  przeszła. Źródła zachowały bajty/hash; obejrzano zrzuty aligned/subpixel/pomiar.
  Skrypt i log: `/tmp/stmviewer-phase-smoke.py`, `/tmp/stmviewer-phase-smoke.log`.
  Zrzuty: `/tmp/stmviewer-phase-{aligned,subpixel,uncertain,measurement}-xcb.png`.
  MOVIE_3: 17 klatek, wynik **398 × 398**, 16 niepewnych klatek
  (łącznie z odziedziczoną niepewnością); manifest SHA-256 i przesunięcia:
  `/tmp/stmviewer-phase-measurement.json`. To test wykonania/prezentacji,
  nie potwierdzenie fizycznej poprawności wszystkich dopasowań.
- Pełny zestaw repo w `netcat`:
  `PYTHONPATH=.:tests/moltrack:tests/stmviewer QT_QPA_PLATFORM=offscreen python -m pytest -q --import-mode=importlib --continue-on-collection-errors -o cache_dir=/tmp/stmviewer-phase-full-pytest`:
  **1909 passed, 14 failed, 14 skipped**, 222.93 s. Wszystkie 14 identyfikatorów
  niepowodzeń MolTrack/NanoTrack występuje w poprzednim logu ticketu 07;
  brak nowych niepowodzeń oraz błędów zbierania. Wcześniejszy timeout workera
  SAM2 nie powtórzył się. Nie jest to zielony odbiór całego repo. Log:
  `/tmp/stmviewer-phase-full-suite.log`, porównanie z
  `/tmp/stmviewer-deletion-full-suite.log`.
- [Przegląd Standards/Spec](implementation/review-08-phase-registration.md):
  Standards — 0 uwag; Spec — 0 usterek kodu, 1 drobna uwaga do instrukcji
  manualnej, poprawiona po przeglądzie. Nie zmieniano kodu po testach.
- Generator odtwarza pięć wzorców bajtowo. Największy zmieniony plik kodu:
  `stmviewer/ui/main_window.py`, **590 linii** (limit 1500).
  `git diff --check` oraz lokalne odnośniki zmienionej dokumentacji poprawne.
- [Instrukcja manualna](phase-registration-manual.md) i pięć małych filmów
  oraz generator są w repo. Użytkownik potwierdził ręczny odbiór 2026-10-23:
  „testy manualne ok”. Nie wskazano systemu; potwierdzenie nie zamyka
  odrębnych odbiorów platform. Zmieniono wyłącznie dokumentację,
  bez ponawiania testów automatycznych.

### Integracja

Lokalne wymagania Viewera rozszerzono o sprawdzone SciPy 1.15.2 i scikit-image
0.25.2. Mypy pomija śledzenie starego NanoTrack i brak stubów SciPy; sam kod
Viewera pozostaje strict. Nie zmieniono konfiguracji głównej ani wspólnych
modułów. Istniejący batch/materializator NanoTrack nie mają punktów anulowania,
więc Viewer używa lokalnego cyklu z tym samym backendem i regułami geometrii.
Wspólne wydzielenie runnera/materializatora może koordynować sesja integracyjna;
nie jest blokadą obecnej funkcji. Pozostałe metody: 09–10; duża seria: 18.

## 07: Usuwanie klatek z zachowaniem czasu i pochodzenia — 2026-10-23

Gałąź: `viewer/start`. Baza implementacji i przeglądu:
`e8102e9d21924c8d661e72df223a46343e0183ff`.
Ticket: [07-frame-deletion](implementation/issues/07-frame-deletion.md).
Status: `done` po potwierdzeniu ręcznego odbioru użytkownika 2026-10-23.
Commit implementacji: `bfffd83`; końcowy raport: `6f35585`.
Commit potwierdzenia ręcznego odbioru podany w wiadomości sesji.

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
  Oceniono wizualnie. To próba automatyczna, odrębna od późniejszego
  potwierdzenia użytkownika; odbiór Windows pozostaje w osobnym tickecie.
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
  Użytkownik potwierdził ręczny odbiór 2026-10-23: „testy manualne ok”.
  Nie wskazano systemu; potwierdzenie nie zamyka odrębnych odbiorów platform.
  Zmieniono wyłącznie dokumentację, bez ponawiania testów automatycznych.

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
