# REG-13: LightGlue + SuperPoint — dopasowanie rzadkich punktów

**What to build:** Użytkownik wybiera LightGlue + SuperPoint dla pary, filmu
lub grafu, porównuje wynik z Deep outdoor i RoMa oraz może go zastosować,
zapisać w sesji i wyeksportować.
**Blocked by:** [REG-12](12-matchanything.md), w tym odbiór manualny — spełnione.
**Status:** ready-for-review
**Wykonawca:** Codex; baza przeglądu `d86baba`, implementacja `243f83a`.
**Manualny odbiór:** niezamknięty; użytkownik zgłosił odmowę 2/32 na pierwszej parze MOVIE_4.
[Diagnoza zgłoszenia](../lightglue-results.md#zgłoszenie-użytkownika-odmowa-232-na-pierwszej-parze):
odmowa potwierdzona; powiększenie wejścia nie pomogło. Kod i progi bez zmian.
**Dodano do planu:** 2026-11-02, na zlecenie użytkownika.

Obowiązują [plan](../README.md), [protokół](../manual-protocol.md),
[przegląd metod i projekt eksperymentu](../next-methods-research.md)
oraz [zasady implementacji i odbioru](../../implementation/README.md).
Zależność ustala kolejność odbiorów, nie zależność modelu od MatchAnything.
Nazwa Deep Matcher oznacza obecny LoFTR outdoor; LightGlue jest osobną metodą.

## Przygotowane zasoby — 2026-11-02

Na osobne zlecenie użytkownika pobrano kod oraz oba checkpointy do
`/home/rlew/.cache/stmviewer/lightglue/`. Rzeczywiste próby CPU i CUDA w
niezmienionym `netcat` zaliczone: [ścieżki, wersje i wyniki](../lightglue-environment.md).
Są to próby środowiska, nie implementacja ani manualny odbiór tego ticketu.
Adapter wdrożony w tym tickecie zapewnia lokalne ładowanie, kontrolę
kompletności wag i współrzędne original. [Instrukcja GUI](../lightglue-manual.md),
[wyniki rzeczywistych prób](../lightglue-results.md),
[testy i dwa przeglądy](../reviews/REG-13.md).

814 testów Viewera zaliczonych; osobno rzeczywiste CPU/CUDA i Qt offscreen.
W pilotażu LightGlue dał wynik dla 12/18 par; odmowy rozłączyły pełne grafy
MOVIE_4/MOVIE_8. Jakość nie jest uznana za poprawioną. Poniższe zaznaczenia
oznaczają wdrożenie i sprawdzenia automatyczne, nie odbiór manualny.

## Zakres i kryteria odbioru

- [x] Jedna jawna opcja **LightGlue + SuperPoint** w podglądzie pary,
  rejestracji sąsiedniej serii i dopasowaniu wieloklatkowym. Jeden estymator
  pary obsługuje wszystkie drogi, z dotychczasowymi oknami i solverami LS/Huber.
  Wybór metody nie zmienia domyślnego algorytmu ani aktywnego aligned.
- [x] SuperPoint dostarcza punkty/deskryptory, LightGlue ich korespondencje.
  Przypinamy zgodną konfigurację i wagi obu składników, wersję kodu oraz
  przygotowanie obrazu. Zapisujemy rozmiary, normalizację, kanały, padding
  i skalowanie. Współrzędne obu obrazów wracają do pikseli original dokładnie
  raz, także gdy biblioteka już odwraca skalowanie. Gamma nie wpływa na XY;
  sztuczne marginesy i brakujące próbki nie udają struktur próbki.
- [x] Punkty trafiają do istniejącego `translation-consensus-v2`, z tymi samymi
  regułami co RoMa/EfficientLoFTR/MatchAnything. Wynik to jedno globalne XY;
  nie kopiujemy homografii ani obrotu z przykładów biblioteki. Score LightGlue
  nie jest wagą porównywalną ze score innego modelu ani prawdopodobieństwem
  poprawnego dryfu STM.
- [x] Zachowujemy uzgodnioną politykę niepewności: słabo poparty wynik jest
  dostępny z ostrzeżeniem; rzeczywisty brak wymaganych korespondencji/wektorów
  daje lokalną odmowę. Graf może wykorzystać inne relacje, lecz nie otrzymuje
  fikcyjnych zer. Rozłączny graf i niezbieżny solver nie dają kompletnego filmu.
- [x] UI umożliwia wskazanie lokalnych zasobów obu składników, jawny wybór
  CPU/CUDA i sprawdzenie modelu. Brak bibliotek/wag, zły checkpoint, uszkodzenie,
  niedostępne urządzenie i OOM mają konkretne komunikaty. Bez sieciowego
  pobierania w aplikacji, instalowania pakietów, zastępowania metody/urządzenia
  ani zmniejszania wejścia po błędzie.
- [x] Model i ekstraktor są ładowane raz na zadanie i ponownie używane.
  Postęp/anulowanie działają zgodnie z istniejącym cyklem pracy. Błąd lub
  anulowanie pozostawia wcześniejszy aligned, korekty i kandydatów;
  zasoby są zwalniane. Opcjonalne zależności nie blokują startu aplikacji.
- [x] Sesja zachowuje identyfikator metody, konfigurację obu składników,
  SHA-256 kodu/wag, rzeczywiste urządzenie, przygotowanie, XY i diagnostykę,
  także ustawienia zapamiętane po przełączeniu na inną metodę. Odczyt starszych
  sesji pozostaje dostępny. Odtworzenie zapisanej pracy działa bez modelu
  i nie stosuje niezastosowanego kandydata grafu.
- [x] Zastosowanie wyniku, ręczna korekta i jej cofnięcie, MPP z metadanymi
  oraz AVI korzystają z dotychczasowych kontraktów: render z oryginałów raz,
  poprawna geometria/ważność i pochodzenie, bez diagnostyki w obrazie pomiarowym.
- [x] Powstaje instrukcja środowiska i lokalnych wag: źródła, przypięte wersje,
  SHA-256, rzeczywiste próby CPU/CUDA oraz osobne warunki LightGlue i SuperPoint.
  Nie utożsamiamy licencji LightGlue z licencją kodu/wag SuperPoint.
  Konflikty rozwiązujemy w zakresie Viewera; potrzebne zmiany wspólne do handoff.
- [x] Raport porównuje metodę z Deep outdoor i RoMa v2 Turbo na ustalonych
  18 parach (3 metody × 18 = 54 wyniki prób), wzorcach znanego XY oraz obu
  pełnych filmach. Zapisuje także odmowy,
  pogorszenia, nierozstrzygalne przypadki, czasy i RAM/VRAM. Domknięcie
  czterech metod należy do REG-14; REG-13 nie czeka na implementację AKAZE.
  Sprzęt/platformy faktycznie sprawdzone są oddzielone od nieprzetestowanych.

Poza zakresem: ALIKED/DISK/SIFT, XFeat, nowe treningi, filtry wierszy,
rozszerzenie historycznego Deep o konsensus v2, nowe solvery, maski,
korekcja lokalna oraz przywracanie REG-06/08d/09. Nie wymagamy z góry przewagi
jakościowej nad bazami; ocenę jakości i decyzję użytkownika zapisujemy jawnie.
Kod/testy: cel do 1000, twardy limit 1500 fizycznych linii na plik.

## Publiczne granice TDD i sprawdzenia

- **Obrazy/konfiguracja → korespondencje/XY:** znany ruch w obu osiach,
  obraz niekwadratowy, zmienny rozmiar i odwzorowanie skali bez podwójnej
  korekty; konsensus v2, rozkład poparcia i odmowa przy braku punktów.
- **Dostępność/zadanie → wynik albo błąd:** osobno brak/złe wagi ekstraktora
  i matchera, brak urządzenia, OOM, anulowanie i brak prób pobierania;
  zachowanie poprzedniej pracy i ponowne użycie załadowanych modeli.
- **Para/seria/graf/sesja → zastosowanie i eksport:** ten sam pomiar pary,
  trwałość aktywnej/nieaktywnej konfiguracji, odczyt bez modeli, korekta/cofnięcie,
  ponowny odczyt MPP i zgodność wyrenderowanego AVI. Testujemy nowe granice,
  nie kopiujemy całych testów istniejącego solvera lub renderera.
- Osobno rzeczywiste wagi CPU/CUDA, wzorce i pomiary; atrapy nie potwierdzają
  działania ani jakości modelu. Typecheck, pełny zestaw i przeglądy zgodnie
  z zasadami wykonania; Qt offscreen oddzielnie od odbioru manualnego.

## Próba manualna po tickecie

1. Uruchom `conda activate netcat`, `python -m stmviewer.main` z katalogu Viewera.
   Wybierz nową metodę; według dostarczonej instrukcji wskaż komplet lokalnych
   zasobów. Sprawdź dostępność i faktyczne CPU/CUDA, także komunikat bez wag.
2. Otwórz `tests/stmviewer/fixtures/registration/cpu.mpp`. Sprawdź znane XY,
   nakładkę, original/aligned i niezmienność wyniku po zmianie gamma/zoomu.
   Powtórz próbę na wzorcu z nieruchomym pasem i okresowym motywem.
3. MOVIE_4: usuń źródłowe klatki 1 i 2. Porównaj 18 par z protokołu
   z Deep outdoor i RoMa Turbo, w tym trudne 29→30, 35→36, 44–46, 61→62,
   94–97. Zachowaj wspólne zakotwiczenie, zoom i kontrast; zapisz także pogorszenia.
4. Zarejestruj oba całe filmy oraz oblicz graf przy tej samej liście par i solverze.
   Obejrzyj pierwsze 150 klatek MOVIE_4, dalszą część oraz MOVIE_8.
   Niekompletny wynik ma wyjaśnienie; kompletny można jawnie zastosować.
5. Przy istniejącym aligned ponów i anuluj obliczenie. Zapisz/otwórz sesję,
   także bez wag oraz po wybraniu Phase. Wróć do nowej metody i sprawdź ustawienia.
6. Na kompletnym wzorcu lub filmie zastosuj/cofnij korektę ręczną, zapisz mały
   MPP i AVI, otwórz je ponownie (AVI w VLC). Sprawdź geometrię i pochodzenie.

**Oczekiwany wynik:** działająca dodatkowa metoda oraz odtwarzalne porównanie
jakości, możliwe do ręcznego odebrania przed rozpoczęciem REG-14.

- [ ] Odbiór manualny funkcji i ocena jakości przez użytkownika.
