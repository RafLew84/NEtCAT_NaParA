# REG-11: RoMa v2 — gęste dopasowania do jednej translacji

**What to build:** Użytkownik porównuje RoMa v2 z odebranymi modelami i widzi,
czy gęste korespondencje poprawiają globalne XY na trudnych obrazach STM.
**Blocked by:** [REG-10](10-efficient-loftr.md), w tym odbiór manualny.
**Status:** ready-for-review
**Manualny odbiór:** oczekuje na użytkownika; automatyczne Qt offscreen CPU/CUDA zaliczone.
**Wykonawca:** Codex; baza przeglądu `3a3a684`.
**Dodano do planu:** 2026-10-31, na zlecenie użytkownika po research.

**Decyzja i przygotowanie — 2026-11-02:** użytkownik wybrał osobne środowisko
`netcat-romav2` oraz proces roboczy dla tej metody; aplikacja nadal działa
w `netcat`. Na tym etapie zlecił tylko przygotowanie środowiska i aktualizację
ticketu. [Zasoby, wersje i sprawdzenia](../roma-environment.md).
Po przygotowaniu status wynosił `ready-for-agent`. Na kolejne zlecenie
użytkownika wdrożono pełną integrację REG-11. REG-10 ma odbiór `done`.

**Wynik — 2026-11-02:** implementacja `cfc1547`, poprawka przeglądu `4e69d40`.
[Instrukcja ręczna](../roma-manual.md), [wyniki rzeczywiste](../roma-results.md),
[testy i przeglądy](../reviews/REG-11.md). 761 testów Viewera zaliczonych,
14 pominiętych; osobno 4 rzeczywiste testy modelu i 2 rzeczywiste testy GUI.
Oba filmy mają kompletny łańcuch i LS; Huber osiągnął limit iteracji.
RoMa podąża za nieruchomym pasem w jednym wzorcu; jakość STM wymaga oceny.
REG-12 pozostaje nierozpoczęty, zablokowany odbiorem tego etapu.

Obowiązują [plan](../README.md), [protokół odbioru](../manual-protocol.md)
i [przegląd modeli](../../registration-multiframe-research.md).
Blokada ustala kolejność odbiorów. RoMa v2 nie wywołuje EfficientLoFTR
i nie wymaga jego wag podczas własnych obliczeń.

## Uzgodnione uruchamianie w osobnym procesie

- GUI, odczyt obrazów, sesje, konsensus `translation-consensus-v2`, LS/Huber,
  renderowanie i eksport pozostają w `netcat`. Tylko inferencja RoMa v2
  i próbkowanie gęstego pola działają w `netcat-romav2`.
- Interpreter uruchamiamy bezpośrednio po pełnej ścieżce, bez powłoki
  i `conda activate`. Utworzenie procesu następuje przy rozpoczęciu obliczeń
  lub jawnym sprawdzeniu dostępności, nie przy samym otwarciu sesji.
  Jeden proces i model obsługują całe zadanie pary, serii lub grafu.
- Sterowanie i metadane mają wersjonowany protokół JSON. Pary obrazów oraz
  ograniczone tablice punktów przekazujemy lokalnymi plikami NumPy,
  z `allow_pickle=False`. Bez pickle i bez kopiowania całego filmu.
  Gęste pola pozostają w procesie RoMa i są zwalniane po próbkowaniu.
- Wynik zawiera korespondencje oraz informacje o geometrii wejścia,
  urządzeniu, wersjach kodu/bibliotek i wagach. Rodzic sprawdza odpowiedź
  przed użyciem wspólnej agregacji i istniejącego renderera.
- Anulowanie, błąd i zamknięcie programu kończą proces, czekają na jego
  zakończenie i sprzątają pliki robocze; w razie braku reakcji proces jest
  przymusowo kończony. Awaria, zerwany protokół lub OOM zachowuje poprzedni
  aligned. Bez pobierania w tle, cichego fallbacku lub zmiany urządzenia.
- Sesja zachowuje ścieżkę interpretera i konfigurację obliczeń. Jej odczyt
  nie uruchamia zapisanego interpretera i nie wymaga środowiska RoMa.
  Przed nowym obliczeniem można poprawić ścieżkę na innym komputerze.
- Dla domyślnego modelu wymagany jest jeden pełny checkpoint RoMa v2
  oraz lokalny kod DINOv3. Wagi DINOv3 i VGG są częścią tego checkpointu;
  nie wymagamy osobnego pobierania wag tych składników.

## Zakres i kryteria odbioru

- [x] RoMa v2 jest osobnym wyborem dla pary, całej serii sąsiednich klatek
  i odebranego grafu. Wszystkie drogi korzystają z tego samego estymatora
  pary. Dotychczasowe modele pozostają dostępne bez automatycznej promocji.
- [x] Adapter jawnie przelicza współrzędne znormalizowane/gęstego pola
  oraz przygotowanych wejść na piksele obu oryginałów. Zapisuje skalowanie,
  padding, kanały i normalizację. Próbkowanie gęstych korespondencji ma
  wersjonowane parametry, limit liczby punktów i seed, jeśli jest losowe.
- [x] Po odrzuceniu korespondencji poza ważnymi próbkami wyznaczamy jedno
  XY agregacją korespondencji odebraną w REG-10, bez wyszukiwania wycinków
  z REG-05. Gęste punkty z jednego zakłócenia nie są niezależną większością.
  Ocena pokrycia i precyzji modelu pozostaje
  jego diagnostyką, bez udawanej kalibracji prawdopodobieństwa poprawnego STM.
- [x] GUI pokazuje pokrycie dopasowaniami, przestrzenne poparcie i odmowy.
  Porównanie z EfficientLoFTR zachowuje tę samą agregację z REG-10, listę
  kandydatów par, graf, progi w pikselach original i renderer. Historyczny
  Deep jest dodatkowym porównaniem całych estymatorów. Różnice przygotowania
  wejścia oraz kwalifikacji punktów są jawne w zapisanej konfiguracji.
- [x] Wynikiem do renderowania pozostaje jedna translacja na klatkę.
  Nie zapisujemy gęstego pola jako deformacji pomiaru, nie poprawiamy lokalnie
  ruchu molekuł i nie stosujemy automatycznie ECC po RoMa v2.
- [x] Opcjonalny adapter działa z lokalnymi wagami i pełnym zestawem
  potrzebnych zasobów DINOv3. Instrukcja przypina wersje kodu/bibliotek,
  warianty i SHA-256 wag oraz warunki kodu i modeli. Brak któregokolwiek
  zasobu daje przyczynę niedostępności, bez próby pobierania w tle.
- [x] Brak pamięci, błąd modelu lub brak wskazanego urządzenia pozostawia
  poprzedni wynik. Nie zmieniamy po cichu modelu, urządzenia ani rozdzielczości.
  Możliwy jawny preset o mniejszym koszcie jest odrębną zapisaną konfiguracją.
  Model ładuje się raz na zadanie; dane gęste pary zwalniamy po próbkowaniu,
  zachowując tylko potrzebną, ograniczoną diagnostykę.
- [x] RoMa v2 działa w osobnym procesie środowiska `netcat-romav2`, zgodnie
  z powyższym kontraktem. GUI i pozostałe metody zachowują środowisko `netcat`.
  Brak interpretera lub zależności daje konkretną niedostępność tej metody.
  Konfiguracja i wymagania procesu są w zakresie Viewera; ewentualne zmiany
  modułów wspólnych lub konfiguracji głównej trafiają do handoff.
- [x] Ten ticket rozszerza sesję o konfigurację modelu/próbkowania, urządzenie,
  pochodzenie wag, XY i diagnozy. Odczyt oraz porównanie nie wymagają modelu.
  Przywracamy zapisany aktywny film, bez stosowania niezastosowanego kandydata.
  Nowe obliczenie sprawdza dostępność zasobów.
  Zastosowanie, ręczne korekty i MPP/AVI zachowują kontrakt REG-08c.
- [x] Raport oddziela poparcie modelu od oceny obrazowej. REG-06 jest
  odłożony; nie wymagamy jego implementacji ani oznaczania fragmentów,
  a brak kontroli pozostaje brakiem oceny. Po ewentualnym wznowieniu REG-06
  wskazujemy ocenę zależną, jeśli model lub przygotowanie wejścia używały
  danych kontrolnych. Wybranie punktów poza prostokątem nie usuwa wpływu
  tych pikseli przez kontekstowe cechy DINOv3.
- [x] Raport rzeczywistych prób obejmuje czas estymacji, solvera i renderu,
  RAM/VRAM, faktyczne urządzenie, odmowy i ocenę obrazową osobno. Uruchomienie
  na GPU z większą pamięcią nie potwierdza dostępności wariantu na 8 GB.
  Brak próby na docelowym budżecie pozostaje ograniczeniem, a nie sukcesem.

Poza zakresem: trening, deformacja obrazów, uśrednianie klatek, automatyczne
łączenie wyników różnych modeli i gwarancja przewagi gęstych dopasowań.
Gorszy lub niejednoznaczny wynik może zakończyć eksperyment po zapisanej
decyzji użytkownika, zgodnie z planem.

## Publiczne granice TDD i automatyczne sprawdzenia

- **Pole/korespondencje → globalne XY:** poprawne osie i znaki, transformacja
  współrzędnych obu obrazów, niekwadratowe wymiary, subpiksele, padding,
  znany ruch i błędna gęsta grupa. Sprawdzamy także odmowę i brak lokalnego warpu.
- **Konfiguracja/zasoby → wykonanie:** brak części wag, błąd/OOM/anulowanie,
  brak sieciowego pobierania i fallbacku. Granica procesu obejmuje brak
  interpretera, niezgodność protokołu, awarię/EOF, anulowanie, oczekiwanie
  na zamknięcie i sprzątanie plików. Próbkowanie jest odtwarzalne według
  zapisanych ustawień. Test adaptera nie zastępuje próby rzeczywistego modelu.
- **GUI/seria/graf/sesja:** zgodność XY w poszczególnych drogach, trwałość
  diagnostyki i pochodzenia, ograniczona pamięć, odczyt bez modelu oraz ochrona
  wcześniejszego aligned. Eksport i korekta ręczna obejmują nowe pochodzenie.
- Z rzeczywistymi lokalnymi wagami sprawdzamy znany wzorzec i oba filmy.
  Raport CPU/CUDA, GUI oraz VLC rozdziela dowody; istniejące testy solvera
  i eksportu rozszerzamy tylko w miejscach nowego zachowania.

## Próba manualna

1. Uruchom `python -m stmviewer.main` w opisanym środowisku. Sprawdź komunikat
   przy brakującym zasobie, następnie uruchom z przygotowanymi wagami.
   UI ma wskazywać RoMa v2 i faktyczne urządzenie.
2. Porównaj RoMa v2 z Deep i EfficientLoFTR na `cpu.mpp` oraz wzorcu
   z nieruchomymi pasami. Obejrzyj rozmieszczenie korespondencji i obszary
   poparcia; więcej punktów nie musi oznaczać lepszego XY.
3. Na MOVIE_4 usuń źródłowe 1 i 2 przed obliczeniami. Obejrzyj stałe pary
   i problemy 29→30, 35→36, 44→45→46, 61→62, 94→95→96→97 według numeracji
   po usunięciu. Powtórz porównanie na MOVIE_8 i nowych przypadkach.
4. Uruchom oba pełne filmy w trybie sąsiednim oraz jednym ustalonym wariancie
   grafu. Porównaj przy stałym konsensusie i widoku. Zapisz odmowy, jakość
   pierwszych 150 klatek MOVIE_4 i dalszej części oraz zmierzone zasoby.
5. Anuluj nowe obliczenie. Poprzedni aligned ma zostać. Zapisz/otwórz sesję,
   również przy niedostępnym modelu; dostępny ma być podgląd zapisanych XY.
6. Zastosuj kompletny wynik, popraw parę ręcznie i zapisz małe MPP+metadane
   oraz AVI. Otwórz MPP w Viewerze, AVI w VLC. Sprawdź położenia, brak gęstego
   warpu i nakładek diagnostycznych; zanotuj osobno wynik próby 8 GB VRAM.

**Oczekiwany wynik:** sprawdzenie innej rodziny matcherów przy niezmienionej
warstwie globalnego XY i świadoma decyzja o przydatności na obu filmach.
