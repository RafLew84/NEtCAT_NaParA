# REG-14: AKAZE — rejestracja cech bez wag sieci

**What to build:** Użytkownik rejestruje parę, film lub graf metodą AKAZE
na CPU, bez modeli sieciowych, i porównuje wynik z Deep, RoMa i LightGlue.
**Blocked by:** [REG-13](13-lightglue-superpoint.md), w tym odbiór manualny — spełnione 2026-11-02.
**Status:** ready-for-agent
**Manualny odbiór:** niewykonany; implementacja nierozpoczęta.
**Dodano do planu:** 2026-11-02, na zlecenie użytkownika.

Obowiązują [plan](../README.md), [protokół](../manual-protocol.md),
[przegląd metod i projekt eksperymentu](../next-methods-research.md)
oraz [zasady implementacji i odbioru](../../implementation/README.md).
Blokada REG-13 porządkuje implementacje i ręczne odbiory; AKAZE nie zależy
technicznie od LightGlue ani jego wag.

## Zakres i kryteria odbioru

- [ ] Osobna opcja **AKAZE** dla podglądu pary, sąsiedniej serii i grafu
  wieloklatkowego. Wszystkie drogi używają jednego estymatora pary,
  istniejącego konsensusu i LS/Hubera; domyślna metoda nie zmienia się.
- [ ] Używamy AKAZE z binarnymi deskryptorami MLDB oraz wzajemnego dopasowania
  Brute-Force Hamming (`crossCheck`). Parametry detektora i selekcji są
  jawne, wersjonowane i identyczne w porównywanych parach; nie stroimy ich
  osobno do trudnych klatek. To nowy dostawca korespondencji, nie przeniesienie
  sterowania mikroskopem online z publikacji Diao i wsp.
- [ ] Przygotowanie obrazu do OpenCV jest określone i zapisane: przekształcenie
  wartości pomiaru na intensywności, rozmiar, skala i ważność próbek.
  Gamma podglądu pozostaje niezależna. Domyślnie pracujemy w rozmiarze original;
  każde ewentualne przeskalowanie musi mieć poprawne odwzorowanie obu osi.
  Brak punktów/deskryptorów, stały obraz i niedostateczny wspólny obszar
  dają kontrolowaną odmowę, nie wyjątek nieobsłużony ani fikcyjne XY=(0,0).
- [ ] Koordynaty original trafiają do tego samego `translation-consensus-v2`
  i parametrów co RoMa oraz LightGlue. Wynik jest jedną translacją,
  bez homografii, dodatkowego ECC, deformacji czy wygładzania trajektorii.
  Odległość Hamming nie staje się score porównywalnym z pewnością sieci.
- [ ] Słabe przestrzenne poparcie/konkurencyjne wektory są widoczne z ostrzeżeniem,
  zgodnie z obecną polityką. Faktyczny brak minimum korespondencji/wektorów
  jest lokalną odmową; graf korzysta z pozostałych relacji według istniejących
  reguł. Błąd bibliotek, anulowanie i niezbieżność nie udają braków lokalnych.
- [ ] Wykonanie na CPU nie wymaga Torch, CUDA ani plików wag. UI pokazuje
  faktyczną metodę i urządzenie, bez pól wag i pozornego wyboru CUDA dla AKAZE.
  Brak odpowiedniego OpenCV ma czytelną przyczynę niedostępności.
  Nie wprowadzamy SPMUtil ani nowego czytnika wyłącznie na potrzeby demonstracji.
- [ ] Obliczenia mają postęp i anulowanie; ponownie używamy zasobów zadania,
  a błąd/anulowanie zachowuje wcześniejszy aligned, korekty i kandydatów.
  Żadna ścieżka AKAZE nie ładuje po cichu modelu neuralnego ani nie pobiera plików.
- [ ] Sesja, relacje grafu oraz MPP zachowują metodę, wersję OpenCV/adaptera,
  konfigurację detektora/matchera, przygotowanie, XY i diagnostykę.
  Zapamiętane ustawienia przetrwają przełączenie metody. Starsze sesje
  nadal się otwierają, a gotowa sesja działa bez runtime AKAZE i bez
  automatycznego stosowania niezastosowanego kandydata.
- [ ] Jawne zastosowanie, ręczna korekta/cofnięcie, MPP i AVI zachowują
  dotychczasową geometrię, ważne próbki i pochodzenie. Renderujemy oryginały
  raz; diagnostyka nie trafia do obrazu pomiarowego.
- [ ] Raport uzupełnia te same 18 par o AKAZE: z wynikami REG-13 daje
  porównanie czterech metod (72 wyniki). Zachowuje manifest wejść i ustawień;
  ponawia bazy tylko przy istotnej zmianie warunków. Obejmuje też wzorce
  znanego XY, oba pełne filmy, odmowy/pogorszenia, czas i RAM.
  Brak użycia CUDA przez AKAZE nie jest brakiem wykonania tego ticketu.
- [ ] Dołączamy instrukcję uruchomienia, wersję zależności, źródła/warunki
  wykorzystanego kodu i rzeczywiste wyniki. Brak danych lub nieprzetestowana
  platforma pozostają ograniczeniem. Mniejszy ruch filmu i większa liczba
  punktów nie są samodzielnym kryterium poprawności.

Poza zakresem: sterowanie mikroskopem, k-means jako nowy wspólny solver,
inny wariant detektora/deskryptora, uczenie, filtry pasów, korekcja lokalna,
maski i wznowienie REG-06/08d/09. Gorszy wynik metody jest dopuszczalnym
wynikiem eksperymentu; wymaga zapisanej oceny i decyzji użytkownika.
Kod/testy: cel do 1000, twardy limit 1500 fizycznych linii na plik.

## Publiczne granice TDD i sprawdzenia

- **Obrazy/konfiguracja → punkty/XY/odmowa:** rzeczywisty AKAZE na znanych
  translacjach, także niekwadratowym obrazie; binarne deskryptory i Hamming,
  wzajemność par oraz przypadki pustych/zbyt nielicznych punktów. Konsensus,
  ostrzeżenia i odwzorowanie XY odpowiadają publicznemu kontraktowi.
- **Dostępność/zadanie → wykonanie CPU:** brak OpenCV, błąd i anulowanie,
  zachowanie wcześniejszej pracy; działanie bez modeli/Torch/sieci.
- **Para/seria/graf/sesja → zastosowanie/eksport:** zgodna konfiguracja,
  zapamiętane nieaktywne ustawienia, sesja bez runtime, ręczne korekty,
  ponowny odczyt MPP i zgodność AVI. Testujemy nowe granice, bez powielania
  wewnętrznych testów istniejącego grafu i renderera.
- Testy kontraktowe uzupełniamy rzeczywistym OpenCV, wzorcami i pomiarami.
  Typecheck, pełny zestaw i dwa przeglądy według zasad wykonania;
  automatyczne GUI nie zastępuje ręcznego odbioru.

## Próba manualna po tickecie

1. Uruchom `conda activate netcat`, `python -m stmviewer.main` z katalogu Viewera.
   Wybierz AKAZE bez wskazywania wag. Sprawdź CPU i brak zależności od
   konfiguracji wybranego wcześniej modelu Deep/RoMa/LightGlue.
2. Na `tests/stmviewer/fixtures/registration/cpu.mpp` sprawdź XY, nakładkę
   oraz original/aligned. Sprawdź przygotowany obraz bez cech: oczekiwana
   odmowa ma wyjaśnienie, a wcześniejszy aligned pozostaje.
3. Po usunięciu źródłowych 1/2 z MOVIE_4 porównaj te same 18 par z REG-13,
   używając Deep outdoor, RoMa Turbo, LightGlue i AKAZE. Oceniaj te same kontury
   przy wspólnym widoku; zapisz również odmowy i wynik nierozstrzygalny.
4. Wykonaj próbę obu pełnych filmów i grafu na wspólnej liście par/solverze.
   Obejrzyj wczesny i późny MOVIE_4 oraz MOVIE_8. Sprawdź wyjaśnienie braków
   i możliwość jawnego zastosowania kompletnego wyniku.
5. Ponów obliczenie i anuluj przy istniejącym aligned. Zapisz/otwórz sesję,
   także po przełączeniu metody i przy kontrolowanej niedostępności estymatora
   AKAZE według instrukcji. Nie usuwaj wspólnego OpenCV ze środowiska użytkownika.
6. Na kompletnym wzorcu lub filmie wykonaj/cofnij korektę, zapisz MPP i AVI,
   sprawdź je ponownie (AVI w VLC), wraz z geometrią i pochodzeniem AKAZE.

**Oczekiwany wynik:** dodatkowa metoda CPU bez wag i zakończone, odtwarzalne
porównanie czterech metod, z osobnym ręcznym odbiorem AKAZE.
