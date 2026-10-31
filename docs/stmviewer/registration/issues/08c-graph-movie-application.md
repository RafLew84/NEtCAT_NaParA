# REG-08c: Zastosowanie grafu do filmu, ręczne korekty i eksport

**What to build:** Użytkownik jawnie stosuje kompletną próbę grafu jako aligned,
poprawia wybrane przejścia ręcznie i zapisuje wynik do MPP/AVI.
**Blocked by:** [REG-08b](08b-robust-graph.md), w tym odbiór manualny.
**Status:** ready-for-agent
**Manualny odbiór:** niewykonany; implementacja nierozpoczęta.
**Dodano do planu:** 2026-10-31, na zlecenie użytkownika po research.

Obowiązują [plan](../README.md#kontrakty-rozszerzenia-wieloklatkowego),
[protokół](../manual-protocol.md), [zapis prób REG-07](07-full-movie-comparison.md)
oraz odebrany [workflow ręczny REG-02a](02a-manual-movie-corrections.md).
Nie zmieniamy solvera ani nie wybieramy automatycznie LS zamiast Hubera.

## Zakres i kryteria odbioru

- [ ] **Zastosuj wynik do filmu** działa dla kompletnej próby LS albo Hubera
  zgodnej z aktualnymi oryginałami, kolejnością i geometrią. Samo obliczenie,
  otwarcie dokumentu lub oglądanie próby nadal nie podmienia aktywnego wyniku.
  Niepełna, rozłączna, anulowana lub numerycznie niepoprawna próba ma powód odmowy.
- [ ] Przed zastosowaniem widać metodę pary, okno, solver, źródła, oznaczone
  ograniczenia oraz liczbę istniejących ręcznych korekt, które nie są częścią
  nowej próby. Dotychczasowy lekki wynik z korektami zostaje zachowany do
  porównania/przywrócenia; nie wymaga kopii pikseli. Ten ticket dodaje również
  jawne **Przywróć zachowany wynik** dla poprzedniego kompletnego filmu,
  także łańcuchowego Deep z ręcznymi korektami. Przywrócenie odtwarza jego
  bazę, nadpisania i końcowe XY z oryginałów, bez ponownej inferencji;
  sprawdza tożsamość/skład serii oraz zachowuje aktywny wynik po błędzie.
- [ ] Zastosowanie liczy aligned z oryginalnych próbek i końcowych globalnych
  XY, z jedną interpolacją. Zachowuje skalę, geometrię źródeł, ważność i padding.
  Postęp, anulowanie i blokady są zgodne z rejestracją; błąd/anulowanie pozostawia
  cały poprzedni wynik wraz z nadpisaniami. Po sukcesie pokazujemy tę samą
  klatkę aligned, nowy obszar dopasowany do okna, dotychczasową gamma i Pause.
- [ ] Wynik grafu `G` staje się zamrożoną bazą ręcznego workflow. Dla sąsiadów
  `i-1,i` punkt startu to aktualna różnica globalnych XY, a bazowe przesunięcie
  do przywrócenia wynosi `G[i]-G[i-1]`. Nie jest to surowe d_ij modelu; UI
  i dokument odróżniają te dwie liczby, które w grafie mogą być różne.
- [ ] Po **Zakończ korektę** powstaje tylko próba pary. **Zastosuj do filmu**
  zastępuje jej względne XY i przesuwa dalsze klatki jak w REG-02a, bez nowego
  rozwiązania grafu. Powtórzenie jest idempotentne; nadpisania różnych par
  współistnieją; cofnięcie jednej przywraca różnicę bazy G, zachowując inne.
- [ ] Przechowujemy osobno pomiary grafu, rozwiązanie bazowe G, ręczne
  nadpisania i końcowe XY. Reszty/oceny solvera dotyczą bazy; nie opisujemy nimi
  ręcznie zmienionego filmu jako ponownie zweryfikowanego grafu. Ręczne zmiany
  i zależny dalszy ciąg zachowują jawny brak automatycznej oceny jakości.
- [ ] Nowe obliczenie grafu korzysta z oryginałów i tworzy odrębną próbę.
  Nie wciąga ręcznych poprawek jako krawędzi, nie nadpisuje ich w trakcie pracy
  ani nie obiecuje ich zachowania po zastosowaniu nowej bazy. Nadpisanie
  aktywnego filmu następuje wyłącznie przez opisane jawne zastosowanie.
- [ ] Nieaktualna próba ręczna po zmianie bazy/serii jest odrzucana.
  Usunięcie klatki zachowuje gotową geometrię i eksport pozostałych; przed
  dalszą ręczną korektą lub nowym zastosowaniem starego grafu wymagana jest
  nowa rejestracja aktualnej serii. Nie przepisujemy relacji na nowe numery listy.
- [ ] Dokument próby zachowuje pełny graf, bazę G, korekty, końcowe XY i ich
  wersje. Można go odczytać przy właściwych oryginałach bez modelu, porównać
  oraz jawnie zastosować. Rozszerzenie formatu zachowuje stare dokumenty REG-07.
- [ ] MPP+metadane zachowuje końcowe obrazy, geometrię/braki, źródła, opis
  modelu/okna/solvera, bazowe i końcowe XY oraz historię ręcznych nadpisań.
  Szczegółowe wszystkie krawędzie/diagnozy przechowuje dokument próby; sam MPP
  nie udaje edytowalnego zapisu grafu i nie odtwarza oryginałów sprzed interpolacji.
  Potrzebne rozszerzenie metadanych należy do ticketu, z odczytem starszych wersji.
- [ ] AVI korzysta z aktywnego poprawionego filmu i dotychczasowych opcji.
  Nakładki, wektory i wagi nie trafiają do obrazów eksportu. Original pozostaje
  niezmieniony. Odbiór obejmuje ponowny odczyt MPP oraz AVI w VLC.

Poza zakresem: optymalizacja grafu z ręcznymi twardymi/miękkimi ograniczeniami,
automatyczny wybór lepszego wariantu, przenoszenie korekt po zmianie źródeł,
deformacje lokalne oraz odtwarzanie sesji obliczeniowej z samego aligned MPP.

## Publiczne granice TDD i automatyczne sprawdzenia

- **Próba grafu → aktywny film:** znane subpikselowe XY, dokładnie jeden render
  z oryginałów, geometria/braki, odmowa niepełnej/starej próby, atomowe zachowanie
  poprzedniego stanu po błędzie/anulowaniu i zachowanie lekkiego poprzednika.
  Scenariusz łańcuch Deep+korekty → graf → przywrócenie daje identyczne
  wcześniejsze XY, ręczne nadpisania i pochodzenie, bez ponownego modelu.
- **Baza G + ręczne nadpisania → wynik:** wzorzec, gdzie różnica G jest inna
  niż surowa krawędź Deep; zmiana jednej i dwóch par, ponowienie, cofnięcie jednej,
  pochodzenie i zakres niepewności. Solver nie uruchamia się po ręcznej zmianie.
- **Dokument/MPP/AVI → odczyt:** graf i korekty przy oryginałach, zgodne końcowe
  próbki i metadane MPP, stare formaty, klatki/FPS AVI, ochrona plików po błędzie.
  Sam MPP nie daje edytowalnej sesji ani danych do ponownej interpolacji oryginałów.

## Próba manualna

1. Otwórz przygotowaną małą serię i jej kompletną próbę grafu. Przeglądanie
   próby nie zmienia filmu. Zastosuj ją: sprawdź XY, Play, original/aligned,
   gamma, zoom i położenia źródeł. Spróbuj zastosować próbę rozłączną: odmowa.
2. Realizujący dostarcza przykład z różnymi surowymi d_ij i różnicami G.
   Wybierz **Popraw dopasowanie z filmu**, sprawdź start, dodaj X+ i zakończ.
   Film zmienia się dopiero po **Zastosuj do filmu**, z propagacją na dalsze klatki.
3. Popraw drugą parę, powtórz zastosowanie, cofnij pierwszą i drugą osobno.
   Sprawdź powrót do bazy G, brak ponownego modelu/solvera i oznaczenia ręczne.
4. Z aktywnymi korektami oblicz nową próbę. Przed zastosowaniem korekty zostają;
   UI pokazuje zakres zastąpienia. Anuluj zastosowanie, potem wykonaj je skutecznie
   i sprawdź zachowanie poprzedniego lekkiego wyniku do porównania. Wykonaj
   **Przywróć zachowany wynik** także dla wcześniejszego łańcucha Deep z ręcznymi
   poprawkami: porównaj XY, nadpisania i mały eksport MPP z wynikiem sprzed grafu.
5. Na MOVIE_4 bez źródłowych 1/2 i MOVIE_8 zastosuj wybrany kompletny graf.
   Obejrzyj problemy i cały film według protokołu, popraw ręcznie wybraną parę.
6. Zapisz próbę oraz mały aligned MPP+metadane i AVI FFV1/MJPG. Otwórz próbę
   przy oryginałach, MPP jako film, AVI w VLC. Sprawdź obrazy, brzegi i pochodzenie.
   Usuń klatkę: eksport gotowego wyniku działa, dalsza edycja wymaga przeliczenia.

**Oczekiwany wynik:** sprawdzony graf jest użyteczny w całym dotychczasowym
workflow, z jasnym rozdzieleniem pomiarów, optymalizacji i ręcznych poprawek.
