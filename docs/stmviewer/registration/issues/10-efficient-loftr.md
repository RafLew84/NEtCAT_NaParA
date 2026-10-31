# REG-10: EfficientLoFTR — porównanie z obecnym Deep Matcherem

**What to build:** Użytkownik wybiera EfficientLoFTR, porównuje dopasowanie
z obecnym Deep Matcherem i stosuje wybrany wynik do filmu.
**Blocked by:** [REG-08c](08c-graph-movie-application.md), w tym odbiór manualny.
**Status:** ready-for-agent
**Manualny odbiór:** niewykonany; implementacja nierozpoczęta.
**Dodano do planu:** 2026-10-31, na zlecenie użytkownika po research.

Obowiązują [plan](../README.md), [protokół odbioru](../manual-protocol.md)
i [przegląd modeli](../../registration-multiframe-research.md).
Zależność od REG-08c ustala kolejność prób i zapewnia gotowy graf oraz eksport.
EfficientLoFTR nie potrzebuje grafu do dopasowania pojedynczej pary.

## Zakres i kryteria odbioru

- [ ] EfficientLoFTR jest osobnym wyborem dla pary, rejestracji sąsiednich
  klatek całej serii oraz grafu odebranego w REG-08a–08c. Te drogi korzystają
  z tego samego estymatora pary. Obecny Deep pozostaje dostępny.
- [ ] Wynik modelu jest przeliczany na korespondencje w pikselach original,
  a następnie na jedno XY. Zapisujemy skalowanie, padding, normalizację
  jasności i ewentualne kopiowanie kanału szarości. Odwzorowanie powrotne
  uwzględnia obie osie i obie klatki; gamma podglądu nie wpływa na estymację.
- [ ] Ten ticket wprowadza wspólną, wersjonowaną agregację wektorów
  korespondencji do jednej translacji: wybór zgodnej grupy, odporne wyznaczenie
  XY oraz ocenę przestrzennego poparcia. Korzysta z zasad REG-05, ale nie
  uruchamia jego wyszukiwania wycinków. Te same reguły i parametry będą używane
  w REG-11/12. Lokalna metoda wycinków pozostaje osobnym wariantem pary.
- [ ] Porównanie z historycznym Deep zachowuje listę kandydatów par, graf
  i renderer, ale przy innej agregacji jest porównaniem całych estymatorów.
  Nie przypisujemy całej różnicy samemu modelowi ani nie wymagamy przebudowy
  wspólnego backendu Deep, aby uzyskać jego korespondencje w tym tickecie.
- [ ] UI pokazuje wynik i rozkład poparcia albo jawną odmowę. Liczba punktów
  i score modelu nie są prawdopodobieństwem poprawnego dryfu. Reguły kwalifikacji
  par są zapisane; surowy score nie staje się wagą porównywalną między modelami.
- [ ] Zależności i wagi są opcjonalne oraz ładowane lokalnie. Przypinamy
  wersję kodu, wariant checkpointu i SHA-256, sposób przygotowania oraz warunki
  kodu i wag. Brak, uszkodzenie lub niezgodność daje konkretną niedostępność.
  Aplikacja nie pobiera modeli, nie instaluje pakietów i nie przełącza metody
  ani urządzenia po błędzie. OOM nie prowadzi do cichego zmniejszenia obrazu.
- [ ] Model jest używany ponownie dla kolejnych par, bez ładowania na każdą
  krawędź grafu. Błąd, anulowanie i zakończenie zwalniają zasoby zadania.
  Ewentualny konflikt zależności izolujemy w opcjonalnym adapterze/środowisku,
  z opisanym uruchomieniem z GUI; potrzebne zmiany wspólne trafiają do handoff.
- [ ] Ten ticket rozszerza sesję o ustawienia, pochodzenie wag, urządzenie,
  wyniki i diagnozy nowej metody. Ponowne otwarcie nie wymaga wag ani modelu.
  Aktywny wynik jest odtwarzany, niezastosowany kandydat nadal wymaga zastosowania.
  Nowe obliczenie sprawdza dostępność modelu.
- [ ] Gotowy wynik działa z zastosowaniem do filmu, ręcznymi korektami,
  zapisem i odczytem sesji oraz MPP/AVI zgodnie z REG-08c. Finalne obrazy
  powstają raz z oryginałów; nie deformujemy fragmentów ani nie dopisujemy
  punktów diagnostycznych do filmu. Poprzedni aligned pozostaje po błędzie.
- [ ] Raport oddziela poparcie modelu i oględziny danych użytych do estymacji
  od niezależnej oceny. REG-06 jest odłożony; nie wymagamy jego implementacji
  ani oznaczania fragmentów, a brak kontroli pozostaje brakiem oceny. Po jego
  ewentualnym wznowieniu kontrola jest zależna, jeśli model widział jej piksele,
  również przez cechy kontekstowe lub przygotowanie wejścia. Samo pominięcie
  korespondencji z prostokąta nie zapewnia niezależności.
- [ ] Próba z rzeczywistymi wagami obejmuje pary i oba pełne filmy. Raport
  rozdziela jakość, odmowy, czas modelu/solvera/renderowania, RAM i VRAM.
  Zapisujemy faktyczne CPU/CUDA i sprzęt. Działanie na GPU o większej pamięci
  nie zalicza wymagania 8 GB; brak tej próby pozostaje jawnym ograniczeniem.

Poza zakresem: trening, automatyczne ECC po modelu, zmiana domyślnej metody,
lokalna deformacja i twierdzenie o poprawie STM na podstawie benchmarków
fotograficznych. Wynik „gorzej” lub „niejednoznacznie” jest dopuszczalną oceną
eksperymentu, lecz wymaga zapisanej decyzji użytkownika.

## Publiczne granice TDD i automatyczne sprawdzenia

- **Korespondencje → XY i diagnoza:** znane przesunięcia subpikselowe w obu
  osiach, niekwadratowy obraz, skalowanie/padding, odstające punkty i poparcie
  skupione w jednym pasie. Sprawdzamy układ original, odmowę i brak deformacji.
- **Dostępność/konfiguracja → wykonanie:** brak i zły checkpoint, wybór
  urządzenia, OOM, błąd i anulowanie; brak prób sieciowych i cichego fallbacku.
  Atrapa adaptera sprawdza kontrakt, nie potwierdza jakości ani działania CUDA.
- **Para/seria/graf → zapisany i zastosowany wynik:** zgodność estymatora,
  pochodzenia i XY, trwałość sesji, zachowanie aktywnego filmu po błędzie,
  jedna interpolacja i zgodność MPP/AVI po korekcie ręcznej.
- Rzeczywisty model uzupełnia testy kontraktów na znanym wzorcu oraz pomiarach.
  Kontrole i limity plików kodu wynikają z planu; nie kopiujemy testów
  istniejącego solvera lub renderera bez nowego zachowania do sprawdzenia.

## Próba manualna

1. Uruchom `python -m stmviewer.main` w przygotowanym środowisku. Bez wag
   sprawdź wyjaśnienie niedostępności, następnie wskaż lokalne wagi według
   dostarczonej instrukcji. Sprawdź nazwę modelu i faktyczne urządzenie.
2. Na `cpu.mpp` oraz dostarczonym wzorcu z nieruchomym pasem porównaj Deep
   i EfficientLoFTR. Obejrzyj nakładkę i poparcie w różnych częściach obrazu.
   Ruch w przeciwnych kierunkach jest poprawnym przypadkiem testowym.
3. Otwórz MOVIE_4, usuń źródłowe klatki 1 i 2 przed obliczeniami. Porównaj
   stałe pary z protokołu oraz bieżące 29→30, 35→36, 44→45→46, 61→62
   i 94→95→96→97. Użyj tego samego widoku i kontrastu dla obu modeli.
4. Porównaj oba pełne filmy najpierw w trybie sąsiednich par, następnie
   w jednym ustalonym wariancie grafu, przy tej samej liście kandydatów par
   i widoku. Deep kontra EfficientLoFTR ocenia cały estymator, jeśli różni się
   agregacja. Obejrzyj pierwsze 150 klatek MOVIE_4, dalszą część i MOVIE_8;
   zapisz też nowe przypadki.
5. Anuluj nowe obliczenie przy istniejącym aligned: wcześniejszy wynik zostaje.
   Zapisz i ponownie otwórz sesję, także bez udostępnionych wag. Podgląd ma działać,
   nowe obliczenie ma podać niedostępność. Sesja odtwarza zapisany aktywny film,
   nie stosuje niezastosowanego kandydata.
6. Jawnie zastosuj kompletny wynik, popraw jedną parę ręcznie i wyeksportuj
   małe MPP+metadane oraz AVI. Otwórz MPP w Viewerze, AVI w VLC; sprawdź
   położenia i brak diagnostyki na obrazie. Zapisz ograniczenia zasobów.

**Oczekiwany wynik:** odtwarzalne porównanie EfficientLoFTR z obecnym Deep,
z rozdzieleniem wpływu modelu, agregacji i grafu oraz ręczną decyzją o jakości.
