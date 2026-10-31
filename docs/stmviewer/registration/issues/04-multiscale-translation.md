# REG-04: Deep Matcher + doprecyzowanie ECC

**What to build:** Użytkownik wybiera osobny wariant, w którym Deep Matcher
wyznacza początkowe XY pary, a ECC doprecyzowuje tę translację. Porównuje
wynik samego Deep z wynikiem hybrydy, aby ocenić rzeczywisty wpływ doprecyzowania.
**Blocked by:** [REG-02a](02a-manual-movie-corrections.md), w tym odbiór manualny — spełnione.
**Status:** done
**Manualny odbiór:** użytkownik potwierdził „testy manualne 04 ok” 2026-10-31.
**Kod:** `f639fd8`, poprawki `1a2766b`. [Karta sprawdzeń](../reviews/REG-04.md),
[instrukcja GUI](../deep-ecc-manual.md), [próby rzeczywiste](../deep-ecc-results.md).
**Wykonawca:** Codex, gałąź `viewer/registration-difficult-movies`; baza przeglądu `29d7fc9`.
**Zmiana zakresu:** 2026-10-31, zatwierdzona przez użytkownika. Hybryda zastępuje
wcześniejszy eksperyment ogólnego dopasowania wieloskalowego. Numer i ścieżka
ticketu pozostają dla zachowania istniejących odnośników.

Obowiązują [plan](../README.md), [protokół odbioru](../manual-protocol.md)
i [zasady wykonania](../../implementation/README.md).

## Cel eksperymentu

W obejrzanych pierwszych 100 klatkach poprawionej serii MOVIE_4 użytkownik
ocenił Deep Matcher najlepiej. Obecny ECC w repo domyślnie zaczyna od Phase,
lecz jego publiczny interfejs przyjmuje inne początkowe XY. Badamy więc wpływ
ECC uruchomionego od wyniku Deep. To hipoteza do sprawdzenia: ECC może nadal
dopasować zakłócenia i pogorszyć dobry wynik początkowy.

W tej wersji używamy istniejącego Deep Matcher/LoFTR i ECC na pełnej
rozdzielczości, ograniczonego do translacji. Nie dodajemy zewnętrznej piramidy
ani wyboru dowolnej kombinacji algorytmów. Każda para jest sąsiednia: 2→1,
3→2 itd.; wcześniejsze klatki wpływają na położenie przez sumowanie XY.

## Zakres i kryteria odbioru

- [x] Nowa, jawnie wybierana metoda **Deep Matcher + ECC (v1)** współistnieje
  z dotychczasowym Deep Matcher i ECC. Nie zmienia domyślnej metody ani
  zachowania wcześniejszych wariantów.
- [x] Dla pary Deep wyznacza początkowe XY. ECC otrzymuje dokładnie ten wynik
  jako `initial_shift_xy` i korzysta z `MOTION_TRANSLATION`; nie wykonuje
  własnej inicjalizacji Phase. Oba etapy liczą na tej samej parze oryginałów.
- [x] Wynik ECC jest całkowitym przesunięciem do nałożenia na klatkę przesuwaną.
  Poprawka wynosi `XY_ECC − XY_Deep`; nie dodajemy wyniku ECC ponownie do Deep.
  Obie estymaty i poprawka mają jednostkę piksela original, +X w prawo, +Y w dół.
- [x] Można obejrzeć i porównać dokładny wynik Deep użyty jako start oraz
  końcowy wynik tej samej próby, bez ponownego obliczania modelu. Wspólny kadr,
  kontrast, zoom i gamma pozwalają ocenić różnicę. Dotychczasowa zachowana
  próba nie jest automatycznie nadpisywana nowym porównaniem.
- [x] UI pokazuje XY Deep, końcowe XY, poprawkę i informacje o przebiegu obu
  etapów. Wynik doprecyzowany nie otrzymuje automatycznie etykiety „lepszy”.
  Jeśli pokazujemy score Deep/ECC, są opisane oddzielnie jako miary backendów,
  nie niezależna ocena poprawności. Status hybrydy wskazuje potrzebę oceny;
  wysoki score ECC nie usuwa ostrzeżeń startu Deep. Mała poprawka również
  nie dowodzi sukcesu, a zmiana kierunku dryfu sama nie jest błędem.
- [x] Jeden wersjonowany zestaw ustawień określa konfigurację Deep i ECC,
  w tym limit iteracji, tolerancję i filtr ECC. Używamy tych samych ustawień
  Deep przy bazie i hybrydzie; nie stroimy ich po cichu osobno do filmu.
  Zachowujemy informacje o lokalnych wagach i wybranym/faktycznym urządzeniu.
  Nie dodajemy rozbudowanego panelu strojenia.
- [x] Metoda działa dla pojedynczej pary i całej serii przez ten sam przebieg
  Deep→ECC. Model jest używany ponownie w serii, bez ładowania wag dla każdej
  pary. Wersja startowa zachowuje Auto/CPU/CUDA dla Deep; ECC wykonuje etap CPU.
  Brak wag lub zależności oznacza jawną niedostępność, bez pobierania modelu.
- [x] Brak poprawnego wyniku Deep, brak zbieżności ECC, niepoprawne XY lub
  nieobsługiwane wejście (np. NaN/Inf wymagające odmowy istniejącego backendu)
  dają czytelną przyczynę z numerem pary i etapem. Nie podstawiamy po cichu
  samego Deep, Phase ani zerowego XY. Nie zamieniamy brakujących danych w zera.
  Dostępny start Deep po błędzie ECC może być pokazany jako diagnostyka;
  nie stanowi ukończonego wyniku hybrydy.
- [x] Wybór hybrydy i Rejestruj uruchamia całą serię bez osobnego zatwierdzania
  każdej pary. Ukończony wynik podmienia aligned po sukcesie jak dotychczas;
  nie jest to automatyczny werdykt poprawy jakości. Błąd/anulowanie pozostawia
  poprzedni kompletny aligned i jego korekty. Postęp rozróżnia Deep i ECC;
  anulowanie jest sprawdzane między etapami i po bieżącym wywołaniu biblioteki.
- [x] Do sumowania względem pierwszej klatki trafiają końcowe XY par.
  Aligned powstaje z oryginalnych wartości, z jedną końcową interpolacją.
  Nie przesuwamy kolejno gotowego obrazu przez Deep i ponownie przez ECC.
  Jedno globalne XY nie deformuje poszczególnych fragmentów klatki.
- [x] Działają podgląd, Play, ręczna korekta REG-02a i eksport MPP/AVI.
  Nazwa/wersja hybrydy, końcowe XY, geometria i status pozostają prawidłowe
  po odczycie MPP. Lekka diagnostyka obu etapów nie wymaga dwóch dodatkowych
  stosów obrazów; zapis dokumentów prób na dysk pozostaje w REG-07.

Poza zakresem: ręczne maski, zewnętrzna piramida rozdzielczości, globalne
poszukiwanie wszystkich konkurencyjnych maksimów, lokalny konsensus,
niezależna walidacja na wydzielonych danych, deformacje, wiele klatek
w jednym estymatorze i wygładzanie czasu. Numery dalszych etapów pozostają.

## Publiczne granice TDD i automatyczne sprawdzenia

- **Para → start Deep → ECC → wynik:** kontrolowana granica zewnętrznego
  matchera i rzeczywisty ECC na wzorcach ze znanym dużym/subpikselowym XY,
  oboma znakami i niekwadratowymi wymiarami. Sprawdzenie inicjalizacji z Deep,
  jednostek, poprawki i braku podwójnego dodania przesunięcia; błąd każdego
  etapu oraz brak cichej metody zastępczej. Wzorce mają rzeczywiste krawędzie.
- **Para → porównanie w GUI:** dokładnie ten sam start Deep i jego wynik ECC,
  niezmienność wcześniej zachowanej próby, ustawienia/urządzenie, jawna
  niezweryfikowana jakość, brak wyniku po błędzie oraz zachowany widok.
- **Seria → aligned → eksport:** zgodność końcowego XY pary i serii,
  sumowanie, pojedyncze renderowanie oryginałów, wartości/geometria,
  anulowanie obu etapów, ochrona starego wyniku, MPP roundtrip i mały AVI.
- Rzeczywista próba lokalnego modelu z ECC uzupełnia testy kontrolowanej
  granicy. Sprawdzamy CPU/CUDA zgodnie z dostępnym stanowiskiem, bez pobierania
  wag; brak takiej próby jest jawnym brakiem odbioru. Wzorzec okresowy oraz
  nieruchomy artefakt służą też pokazaniu ograniczeń miar backendów.
  Żaden test syntetyczny nie potwierdza fizycznego dryfu MOVIE_4/MOVIE_8.

## Próba manualna

1. Na dostarczonym wzorcu z dużym i subpikselowym przesunięciem obejrzyj
   start Deep, wynik ECC i poprawkę. Sprawdź oba znaki oraz znane końcowe XY.
   Przełączaj dokładny start i wynik przy tym samym kadrze i kontraście.
2. Otwórz MOVIE_4 i usuń źródłowe klatki 1 i 2 przed rejestracją. Porównaj
   sam Deep z hybrydą na stałych parach protokołu oraz miejscach wskazanych
   przez użytkownika: bieżące 29→30, 35→36, 44→45→46, 61→62, 94→95→96→97.
   Odpowiedniki źródłowe i granica 150 są zapisane w protokole.
3. W MOVIE_8 sprawdź źródłowe 1→2, 16→17 i 56→57. Dla każdej pary zanotuj
   początkowe XY, poprawkę, wynik i ocenę struktur **lepiej / podobnie / gorzej /
   niejednoznacznie** w kilku częściach obrazu. Wyższy score ECC nie zastępuje
   tej oceny. Tearing opisz oddzielnie.
4. Przy obecnych lokalnych wagach uruchom pełne filmy samym Deep i hybrydą
   przy tej samej konfiguracji Deep; zapisz wyniki i ograniczenia według
   protokołu. Próby pełnej serii nie mogą wymagać klikania każdej pary.
   Po błędzie zapisz parę i etap; nie pomijaj jej, aby otrzymać pełny film.
5. Sprawdź brak wag/biblioteki, kontrolowaną odmowę ECC i anulowanie podczas
   pracy. Poprzedni aligned ma pozostać. Realizujący dostarcza odtwarzalne
   wzorce/narzędzia błędu, aby test nie wymagał edycji kodu przez użytkownika.
6. Zapisz mały kompletny aligned do MPP+metadane i AVI; odczytaj MPP oraz
   obejrzyj AVI według protokołu. Sprawdź też ręczną korektę REG-02a na wyniku
   hybrydy. Brak pełnego wyniku na pomiarze sprawdź osobno na łatwym wzorcu
   i pozostaw jawny w karcie odbioru.

**Oczekiwany wynik:** sprawdzony wpływ ECC startującego od Deep. Użytkownik
podejmuje decyzję, czy zachować wariant eksperymentalny, poprawić go lub
odrzucić; nie zakładamy poprawy względem samego Deep na wszystkich parach.
REG-05 ma spełnioną zależność po odbiorze REG-04.

## Odbiór — 2026-10-31

Użytkownik potwierdził **„testy manualne 04 ok”**. REG-04 zamknięto jako
`done`; zależność REG-05 jest spełniona. Potwierdzenie nie zawiera osobnych
wyników dla par, systemu ani VLC, więc nie dopisujemy takich szczegółów
do [karty sprawdzeń](../reviews/REG-04.md). Wariant pozostaje eksperymentalny;
odbiór nie oznacza przewagi ECC nad samym Deep na wszystkich obrazach.
Wcześniejsze wyniki testów i ograniczenia pozostają zapisane bez zmian.
