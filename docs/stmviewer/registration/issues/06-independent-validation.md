# REG-06: Niezależna kontrola dopasowania

**What to build:** Użytkownik wydziela fragmenty kontrolne i widzi na nich
rozbieżność po dopasowaniu, oddzielnie od wewnętrznej oceny algorytmu.
**Blocked by:** [REG-05](05-local-consensus.md), w tym odbiór manualny.
**Status:** ready-for-agent
**Manualny odbiór:** niewykonany; implementacja nierozpoczęta.

Obowiązują [plan](../README.md) i [protokół odbioru](../manual-protocol.md).

## Zakres i kryteria odbioru

- [ ] W podglądzie pary można nadać prostokątom rolę kontroli. Dla nowego
  wariantu walidowanego wykluczamy te dane z estymacji, również z etapu
  zgrubnego. Obszary w OBU klatkach i margines poszukiwania zamrażamy przed
  estymacją; nie wyznaczamy maski drugiej klatki z ocenianego dopiero XY.
  Wykluczenie obejmuje wpływ tych danych przez filtry i piramidę rozdzielczości.
- [ ] Wynik kontrolny mierzy pozostałe lokalne przesunięcie i jednoznaczność
  dopasowania na tych fragmentach. Nie służy wyborowi kandydata XY, strojeniu
  parametrów ani iteracyjnemu poprawianiu tej samej próby.
- [ ] Jeśli podgląd ocenia wcześniejszy wynik, który używał tych pikseli,
  nazywa ocenę zależną. Brak poprawnego dopasowania fragmentu lub brak kontroli
  jest opisany jako brak oceny, nie jako zerowy błąd.
- [ ] UI oddziela poparcie estymatora, kontrolę obrazową i niepewność
  odziedziczoną z poprzednich par. Wskazuje pary i fragmenty do obejrzenia.
  Wskaźniki nie są przedstawiane jako prawdopodobieństwo prawdziwego dryfu.
- [ ] Zmiana kontroli oznacza nową konfigurację/próbę; stare A/B pozostaje
  niezmienne. Progi alarmu mają jawne jednostki i wersję; próg 3 px z jednego
  reproduktora nie staje się uniwersalną definicją poprawnego filmu.
- [ ] Kontrola jest dostępna dla par i pełnej serii w oznaczonych klatkach.
  Brak oznaczeń w pozostałych nie symuluje oceny. Sama diagnostyka nie modyfikuje
  geometrii istniejącego aligned ani nie kasuje rzeczywistych zmian próbki.

Poza zakresem: automatyczne uznawanie wyniku za prawdę fizyczną, poprawianie
przesunięcia na podstawie fragmentów, które mają pozostać niezależną kontrolą.
„Niezależna” oznacza tu wyłączenie z estymacji danej próby. Fragment wielokrotnie
używany do wyboru wariantów nie jest już niewidzianym zbiorem walidacyjnym;
końcowy odbiór obejmuje dodatkowe, wcześniej niewykorzystane przypadki.

## Publiczne granice TDD i automatyczne sprawdzenia

- **Role fragmentów → estymacja i kontrola:** wykluczenie danych kontrolnych
  także przy inicjalizacji, obsługa obu klatek i zakresu poszukiwania.
  Wzorzec z rozbieżnymi fragmentami sprawdza wykrycie problemu poza estymacją.
- **Wynik + kontrola → diagnoza:** poprawny/błędny znany XY, brak tekstury,
  niejednoznaczny wzór i brak kontroli. Test nie orzeka o ruchu realnej molekuły.
- **GUI → lista par i niezależność prób:** właściwy numer źródłowy, ocena
  zależna/niezależna, brak unieważniania obrazu przez samą zmianę prezentacji.

## Próba manualna

1. Na wzorcu wybierz obszary estymacji i odrębne kontroli. Dla poprawnego
   przesunięcia kontrola potwierdza pokrycie; dla dostarczonego przypadku
   mylącego estymator pokazuje pozostałą rozbieżność.
2. Na obu filmach oznacz nowe fragmenty, których nie używano do strojenia.
   Obejrzyj każdy z nich w nakładce i porównaj opis programu z oceną wzrokową.
3. Sprawdź obszar bez rozpoznawalnej struktury: oczekiwane „brak oceny” lub
   „niejednoznaczne”, a nie bezbłędny wynik. Zapisz także rzeczywiste zmiany próbki.
4. Uruchom pełną serię z kontrolą w wybranych klatkach, przejdź po wskazanych
   parach i sprawdź rozdzielenie lokalnego problemu od odziedziczonej niepewności.

**Oczekiwany wynik:** jawne ograniczenia oceny i skuteczne wskazanie miejsc
do obejrzenia. Samo dodanie metryki nie ma poprawiać ani wygładzać obrazów.
