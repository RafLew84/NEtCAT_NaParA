# REG-03: Ręczne maski zakłóceń

**What to build:** Użytkownik wskazuje prostokątne obszary do wykorzystania lub
pominięcia i widzi wpływ masek na dopasowanie pary oraz całej serii.
**Blocked by:** [REG-02a](02a-manual-movie-corrections.md), w tym odbiór manualny — spełnione.
REG-02a odebrano 2026-10-31; REG-03 jest odblokowany.
**Status:** ready-for-review
**Wykonawca:** Codex; baza przeglądu `270097b`.
**Manualny odbiór:** oczekuje na użytkownika; [instrukcja próby](../manual-masks-manual.md).

Obowiązują [plan](../README.md) i [protokół odbioru](../manual-protocol.md).

## Zakres i kryteria odbioru

- [x] W oryginalnej klatce można dodać/usunąć prostokąty „użyj” i „pomiń”.
  Bez obszarów „użyj” podstawą jest cała klatka; w przeciwnym razie ich suma.
  Prostokąty „pomiń” są od niej odejmowane. Nakładka pokazuje faktyczną maskę.
- [x] Każda klatka ma własną maskę w pikselach original, przypisaną do jej
  pochodzenia. W pierwszej wersji nie ma automatycznego przenoszenia maski
  między klatkami. Klatki bez oznaczeń używają całego dostępnego obrazu.
- [x] Tryb edycji nie koliduje z dotychczasowym przesuwaniem/zoomem. Układ
  original/aligned i padding nie zmieniają współrzędnych zapisanej maski.
- [x] Osobny wariant korelacji z maskami faktycznie respektuje obie maski.
  Porównanie maska wyłączona/włączona używa tego samego wariantu, aby zmienić
  tylko maskę. Nie udajemy, że parametr normalizacji nadal steruje masked NCC.
- [x] Brak wystarczającej tekstury/poparcia lub części wspólnej daje czytelną
  odmowę albo niepewność zgodnie z kontraktem; nigdy cichy powrót do obrazu bez maski.
- [x] Pełna seria wykorzystuje maski odpowiadające jej klatkom. Usunięcie
  klatki usuwa jej edytowalną maskę, pozostałe zachowują przypisanie. Nowy import
  czyści maski. Obliczenia używają ich niezmiennej kopii z chwili uruchomienia.
- [x] Maski żyją na razie w sesji programu; zapis na dysk powstaje w REG-07.
  Edycja nie zmienia wcześniejszej próby A/B ani gotowego aligned.
- [x] Piksele wyłączone z obliczeń pozostają w original i aligned. Zapis
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

## Wykonanie — 2026-10-31

Wdrożono osobny edytor oryginalnych klatek i metodę **Korelacja z maskami (v1)**
dla pary oraz pełnej serii. Przełącznik **Uwzględnij oznaczenia klatek**
porównuje ten sam masked NCC z oznaczeniami i bez nich. Definicje są przypisane
do źródeł, mają niezmienną kopię na czas obliczeń i pozostają w bieżącej sesji.

Implementacja: `868dae4`; poprawka szerokości kart porównania: `b318e1d`;
zachowanie próbek przy NaN: `5bc7175`, `61fa45c`.
[Karta sprawdzeń i przeglądu](../reviews/REG-03.md) zawiera pełne wyniki,
poprawki po przeglądzie i ograniczenia. [Instrukcja manualna](../manual-masks-manual.md)
obejmuje wzorzec z prawdziwym XY, oba filmy, cykl masek i eksport.

Funkcja przeszła próby automatyczne oraz sterowane skryptem w widocznym GUI.
Wybrane pasy na MOVIE_4/MOVIE_8 nie potwierdzają poprawy jakości pełnych filmów;
MOVIE_4 nadal wykazuje duży błędny dryf. Ocena użytkownika pozostaje otwarta.
**REG-04 czeka na ręczny odbiór i osobne zlecenie.**
