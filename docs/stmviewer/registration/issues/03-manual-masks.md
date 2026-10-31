# REG-03: Ręczne maski zakłóceń

**What to build:** Użytkownik wskazuje prostokątne obszary do wykorzystania lub
pominięcia i widzi wpływ masek na dopasowanie pary oraz całej serii.
**Blocked by:** [REG-02a](02a-manual-movie-corrections.md), w tym odbiór manualny.
Zależność dodana 2026-10-31, po odbiorze REG-02. Implementacja czeka na zlecenie i odbiór REG-02a.
**Status:** ready-for-agent
**Manualny odbiór:** niewykonany; implementacja nierozpoczęta.

Obowiązują [plan](../README.md) i [protokół odbioru](../manual-protocol.md).

## Zakres i kryteria odbioru

- [ ] W oryginalnej klatce można dodać/usunąć prostokąty „użyj” i „pomiń”.
  Bez obszarów „użyj” podstawą jest cała klatka; w przeciwnym razie ich suma.
  Prostokąty „pomiń” są od niej odejmowane. Nakładka pokazuje faktyczną maskę.
- [ ] Każda klatka ma własną maskę w pikselach original, przypisaną do jej
  pochodzenia. W pierwszej wersji nie ma automatycznego przenoszenia maski
  między klatkami. Klatki bez oznaczeń używają całego dostępnego obrazu.
- [ ] Tryb edycji nie koliduje z dotychczasowym przesuwaniem/zoomem. Układ
  original/aligned i padding nie zmieniają współrzędnych zapisanej maski.
- [ ] Osobny wariant korelacji z maskami faktycznie respektuje obie maski.
  Porównanie maska wyłączona/włączona używa tego samego wariantu, aby zmienić
  tylko maskę. Nie udajemy, że parametr normalizacji nadal steruje masked NCC.
- [ ] Brak wystarczającej tekstury/poparcia lub części wspólnej daje czytelną
  odmowę albo niepewność zgodnie z kontraktem; nigdy cichy powrót do obrazu bez maski.
- [ ] Pełna seria wykorzystuje maski odpowiadające jej klatkom. Usunięcie
  klatki usuwa jej edytowalną maskę, pozostałe zachowują przypisanie. Nowy import
  czyści maski. Obliczenia używają ich niezmiennej kopii z chwili uruchomienia.
- [ ] Maski żyją na razie w sesji programu; zapis na dysk powstaje w REG-07.
  Edycja nie zmienia wcześniejszej próby A/B ani gotowego aligned.
- [ ] Piksele wyłączone z obliczeń pozostają w original i aligned. Zapis
  MPP/AVI nie wycina ich i nie zawiera kolorowej nakładki edytora.

Poza zakresem: wykrywanie automatyczne, śledzenie obszaru próbki i maski domen.

## Publiczne granice TDD i automatyczne sprawdzenia

- **Oznaczenia klatek → maski → rejestracja:** suma/różnica obszarów, osobne
  maski obu obrazów, granice i brak poparcia. Wzorzec z nieruchomym artefaktem
  i przesuniętą strukturą sprawdza wpływ wykluczenia artefaktu.
- **GUI → oryginalne współrzędne i wynik:** zoom, pan, edycja, źródłowe
  identyfikatory po usuwaniu, niezmienność przypiętej próby i oryginalnych próbek.
- Mały eksport nowego wariantu sprawdza zachowanie wszystkich wartości
  pomiarowych pod maską; nie ocenia automatycznie poprawności ręcznego wyboru.

## Próba manualna

1. Na przygotowanym wzorcu zaznacz pas zakłócenia; porównaj ten sam wariant
   masked NCC bez wykluczenia i z nim. Oczekuj dopasowania znanej struktury.
2. W MOVIE_4 i MOVIE_8 zaznacz widoczne uszkodzone pasy w wybranych klatkach.
   Obejrzyj maskę osobno na obu obrazach i sprawdź wpływ na stałe pary.
3. Przybliż obraz, przesuń go, zmień klatkę i wróć. Prostokąty nadal obejmują
   właściwe piksele. Wykonaj pełną serię; zapisz, które klatki miały maski.
4. Wyklucz cały obszar w jednej klatce. Program ma wyjaśnić brak danych do
   dopasowania i zachować poprzedni pełny wynik; nie ma ukrytej próby bez maski.
5. Usuń klatkę, sprawdź przypisanie pozostałych masek; otwórz nową serię.
   Zapisz mały aligned i sprawdź obecność wartości w oznaczonym wcześniej pasie.

**Oczekiwany wynik:** kontrolowany wpływ doboru danych; wykluczenie artefaktu
nie gwarantuje poprawy każdej pary. Werdykt jakości zapisujemy w karcie.
