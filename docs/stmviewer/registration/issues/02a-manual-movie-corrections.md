# REG-02a: Zastosowanie ręcznych korekt do filmu

**What to build:** Użytkownik rejestruje film automatycznie, poprawia ręcznie
wybrane przejścia między klatkami i jawnie stosuje je do pełnego aligned.
Odtwarzanie oraz eksport MPP/AVI korzystają z poprawionego wyniku.
**Blocked by:** [REG-02](02-unnormalized-correlation.md), w tym odbiór manualny — spełnione.
Korzysta z odebranego [REG-01a](01a-manual-alignment.md).
**Status:** ready-for-agent
**Manualny odbiór:** niewykonany; implementacja nierozpoczęta.
**Dodano do planu:** 2026-10-31, na zlecenie użytkownika, przed REG-03.

Obowiązują [plan](../README.md), [protokół](../manual-protocol.md) i limity plików
z instrukcji aplikacji. Numery wcześniejszych ticketów pozostają bez zmian.
Motywacja: Deep Matcher najlepiej wypadł w oględzinach pierwszych 100 klatek
MOVIE_4, lecz zostały konkretne przejścia wymagające poprawy:
[relacja i numery źródłowe](../reviews/REG-02.md#ręczny-odbiór-użytkownika).

## Zakres i kryteria odbioru

- [ ] W istniejącym oknie pary można rozpocząć **„Popraw dopasowanie z filmu”**.
  Punkt startu pochodzi z aktywnego pełnego aligned: jest przesunięciem wybranej
  pary, a nie skumulowanym XY klatki. Dla już poprawionej pary pobieramy jej
  aktualny wynik. Dostępne pozostają ruchy ±1 px, ułamkowy początek, nakładka,
  przełączanie obrazów, zoom i gamma z REG-01a.
- [ ] **„Zakończ korektę”** nadal zatwierdza tylko próbę pary. Osobne
  **„Zastosuj do filmu”** publikuje zatwierdzony wynik ręczny w pełnej serii.
  Sterowanie pokazuje parę źródłową, poprzednie i nowe XY oraz zakres klatek,
  na który wpłynie zmiana. Porównanie może działać bez pełnej rejestracji,
  lecz zastosowanie do filmu wymaga kompletnego aktywnego wyniku tej samej serii.
- [ ] Ręczne XY zastępuje przesunięcie danej pary. Różnica względem dotychczasowego
  przesunięcia pary zmienia skumulowane XY jej klatki przesuwanej i wszystkich
  następnych. Wcześniejsze XY względem odniesienia pozostają niezmienione.
  Kolejne korekty różnych par współistnieją; zmiana już poprawionej pary zastępuje
  jej nadpisanie. Ponowne zastosowanie tego samego XY nie dodaje korekty drugi raz.
- [ ] **„Usuń korektę tej pary z filmu”** przywraca dla niej przesunięcie z bazowej
  pełnej rejestracji, zachowując korekty innych par. Jest niedostępne bez
  zastosowanej korekty. To odrębne działanie od cofania ruchów szkicu REG-01a;
  nie budujemy wielopoziomowej historii kliknięć.
- [ ] Nowy pełny aligned powstaje z zachowanych oryginalnych próbek i końcowych
  skumulowanych XY, z jedną interpolacją. Przeliczamy padding, cały obszar,
  położenia pól źródłowych i maski ważności. Nie przesuwamy ponownie wcześniej
  interpolowanego aligned. Zmiana paddingu może przesunąć w płótnie także
  wcześniejsze obrazy, mimo że ich XY względem odniesienia nie zmieniły się.
- [ ] Przeliczanie działa w tle z postępem i anulowaniem. Play zatrzymuje się;
  do końca blokowane są zmiana składu serii, inne obliczenia, kolejne zastosowanie
  korekty i eksport. Podgląd, zoom i gamma pozostają dostępne. Błąd/anulowanie
  zachowują poprzedni kompletny film oraz zestaw zastosowanych korekt. Dopiero
  sukces podmienia wynik; pokazujemy aligned tej samej klatki, dopasowujemy nowy
  obszar do okna, zachowujemy gamma i pozostawiamy Play zatrzymany.
- [ ] Korekta jest związana z parą oryginalnych klatek i wersją aktywnego wyniku
  z chwili rozpoczęcia edycji. Nie wolno zastosować starej próby po zmianie filmu,
  pary, składu serii lub zastąpieniu pełnej rejestracji. Zwykłe zmiany podglądu
  nie unieważniają wyniku. Po zastosowaniu zamknięcie okna pary nie usuwa korekty
  z filmu; niezastosowany szkic nadal podlega zasadom REG-01a.
- [ ] Udana nowa pełna rejestracja z oryginałów zastępuje korekty; nieudana lub
  anulowana zachowuje wcześniejszy wynik z korektami. Po usunięciu klatki gotowe
  obrazy, geometria, pochodzenie korekt i eksport pozostałych klatek zostają.
  **Przed dalszą ręczną korektą filmu po usunięciu klatki wymagamy nowej pełnej
  rejestracji**, z czytelnym komunikatem. Nowy udany import czyści stan; nieudany
  zachowuje poprzedni. Nie przypisujemy korekt do przesuniętych numerów listy.
- [ ] Wynik jawnie rozróżnia bazową metodę automatyczną i ręczne nadpisania.
  Zachowuje pary źródłowe, bazowe XY pary, punkt startu ręcznej próby, jej
  pochodzenie, łączną korektę i końcowe XY oraz wersję ustawień. Ręczny wynik
  nie ma pewności algorytmu; klatka poprawiona i zależny dalszy ciąg mają jawny
  brak zweryfikowanej oceny. Cofnięcie korekty odtwarza ocenę z bazy, chyba że
  pozostaje wpływ innej ręcznej korekty. Przechowujemy lekkie metadane i jeden
  aktywny film; bez pełnej kopii obrazów dla każdego kroku.
- [ ] MPP+metadane i AVI zapisują aktywny poprawiony film. MPP zachowuje wartości,
  geometrię, braki, bazową metodę, ręczne pochodzenie i dane nadpisań. Jeśli obecny
  schemat ich nie mieści, minimalne wersjonowane rozszerzenie metadanych Viewera
  należy do tego ticketu, z odczytem starszych plików i opisem zgodności.
  Ponowny odczyt pokazuje historię korekt i te same próbki; nie odzyskuje oryginałów
  sprzed interpolacji. AVI pokazuje poprawione obrazy przy dotychczasowych opcjach.

## Reguła przesunięć

Dla pary klatek `i−1 → i` dotychczasowe przesunięcie pary to `p = S[i] − S[i−1]`,
gdzie `S` oznacza skumulowane XY aktywnego filmu. Operator ustawia nowe XY pary `q`.
Zmiana `delta = q − p` dotyczy `S[i]` i wszystkich kolejnych `S`; wcześniejsze
pozostają. To zastąpienie XY pary, nie dodanie `q` do istniejących przesunięć.

Przykład cpu.mpp: baza `(0,0), (2,−1), (−1,1)`. Zmiana pary 1→2 na `(3,−1)`
daje `(0,0), (3,−1), (0,1)`. Kolejna zmiana pary 2→3 z `(−3,+2)` na `(−3,+3)`
daje `(0,0), (3,−1), (0,2)`. Usunięcie tylko pierwszej korekty daje
`(0,0), (2,−1), (−1,2)`; usunięcie obu przywraca bazę.

Poza zakresem: nowy algorytm dopasowania, korygowanie tearingu wewnątrz klatki,
obrót/skala, ruch myszą zmieniający XY, ręczne budowanie filmu bez kompletnej
rejestracji bazowej, ratowanie niekompletnego przebiegu backendu, przenoszenie
nadpisań po usunięciu klatek, wielopoziomowy undo i odtwarzanie edytowalnej sesji
z samego aligned MPP. Zapis lekkiej sesji przy oryginalnych źródłach pozostaje
w REG-07. Eksport poprawionego filmu jest częścią REG-02a, nie czeka na REG-07.

## Publiczne granice TDD i automatyczne sprawdzenia

- **Pełny wynik + ręczne XY pary → nowy pełny wynik:** niezależnie znane liczby
  z przykładu, znaki i ułamki, zastąpienie/ponowienie/kilka par/cofnięcie,
  propagacja statusu i pochodzenia, niezmienność źródeł i jedna interpolacja,
  padding/maski/skala. Test nie orzeka o fizycznej poprawności ręcznego XY.
- **Kontrolki → aktywny film:** start z różnicy XY pary, rozdzielenie szkicu/próby
  i zastosowania, Play, wybrana klatka, błędy/anulowanie, nieaktualna próba,
  zamknięcie okna, nowy import/rejestracja i usunięcie klatki. Wzorzec subpikselowy
  dostarcza realizujący; nie zależy on od przypadkowego wyniku Deep Matcher.
- **Poprawiony wynik → MPP/AVI → ponowny odczyt:** rzeczywiste wartości i ważność
  próbek, geometria, ręczne pochodzenie i brak pewności, utrzymanie wcześniejszej
  zgodności odczytu MPP, klatki/FPS AVI. Odtwarzanie w VLC i wizualna ocena
  pomiarów są osobnym sprawdzeniem, którego test automatyczny nie zastępuje.

## Próba manualna

1. Uruchom `python -m stmviewer.main` w `netcat`. Otwórz
   `tests/stmviewer/fixtures/registration/cpu.mpp`, wykonaj pełne Phase.
   Zanotuj skumulowane XY `(0,0), (2,−1), (−1,1)` i wygląd aligned.
2. Wybierz klatkę 2, **Porównaj parę… → Popraw dopasowanie z filmu**.
   Oczekuj punktu startu pary `(2,−1)`. Kliknij X+ i **Zakończ korektę**.
   Próba ma `(3,−1)`, a pełny film nadal bazowe XY.
3. Kliknij **Zastosuj do filmu**. Po sukcesie sprawdź wszystkie trzy klatki:
   `(0,0), (3,−1), (0,1)`, nową geometrię i oznaczenie ręcznej korekty.
   Ta celowa zmiana służy sprawdzeniu działania, nie poprawie wzorca.
   Powtórne zastosowanie ma być bez efektu albo niedostępne jako już zastosowane.
4. Dla pary 2→3 pobierz dopasowanie z filmu: musi wynosić `(−3,+2)`, mimo
   wcześniejszej korekty. Dodaj Y+, zakończ i zastosuj. Oczekuj końcowego `(0,2)`.
   Usuń korektę 1→2 i sprawdź `(−1,2)` ostatniej klatki; usuń drugą i porównaj
   z bazą. Sprawdź ponowną edycję tej samej pary oraz ułamkowy wzorzec.
5. Zastosuj ponownie jedną korektę i zamknij okno pary. Sprawdź Play,
   original/aligned, gamma i zoom. Zapisz aligned MPP+metadane oraz AVI FFV1.
   Otwórz MPP ponownie, AVI w VLC: te same poprawione obrazy, pełny obszar,
   braki i historia ręczna. Zapis original ma nadal wartości oryginałów.
6. Na MOVIE_4 usuń źródłowe 1 i 2 **przed** rejestracją: zostaje 362 klatek,
   źródłowe 3–364. Wykonaj Deep Matcher z lokalnymi wagami. Jeśli nie da kompletnego
   wyniku, zapisz odmowę i użyj dostępnej metody dającej pełny wynik do próby funkcji;
   nie deklaruj wówczas odbioru jakości kompletnego Deep Matcher.
7. Zacznij od bieżącej pary **29→30 = źródłowe 31→32**. Obejrzyj struktury,
   popraw XY, zakończ korektę i zastosuj do filmu. Odtwórz sąsiedztwo przejścia
   i dalszą część; wcześniejsze XY względem odniesienia mają pozostać takie same.
   Kolejne miejsca: bieżące 35→36, 44–46, 61→62, 94–97; odpowiadają źródłowym
   37→38, 46–48, 63→64, 96–99. Zanotuj poprawę/pogorszenie i resztkowy tearing.
8. Podczas kolejnego przeliczania rzeczywiście użyj Anuluj; poprzedni film
   i korekty mają zostać. Realizujący zapewnia odtwarzalną próbę błędu bez zmiany
   plików źródłowych. Sukces zbyt szybkiej operacji nie zalicza anulowania.
9. Rozpocznij szkic, zmień aktywną rejestrację i sprawdź odmowę zastosowania
   starej próby. Po usunięciu klatki sprawdź zachowanie gotowego aligned/eksportu
   oraz komunikat wymagający nowej rejestracji przed dalszymi korektami.
   Udana nowa rejestracja usuwa wcześniejsze nadpisania.

**Oczekiwany wynik:** operator poprawia konkretne przejścia w automatycznie
zarejestrowanym filmie i może zapisać użyteczny poprawiony MPP/AVI.
Po implementacji status `ready-for-review`; manualny odbiór blokuje REG-03.
