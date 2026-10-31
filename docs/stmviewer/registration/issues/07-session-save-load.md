# REG-07: Zapis i odczyt sesji

**What to build:** Użytkownik zapisuje bieżącą pracę do jednego przenośnego pliku
`.stmsession`, otwiera go po ponownym uruchomieniu programu i kontynuuje przeglądanie,
ręczne korekty oraz eksport bez ponownej rejestracji.
**Blocked by:** [REG-05](05-local-consensus.md), w tym odbiór manualny — spełnione 2026-10-31.
**Status:** ready-for-review
**Manualny odbiór:** niewykonany; implementacja i automatyczne sprawdzenia zakończone, oczekuje na próbę użytkownika.
**Wykonawca:** Codex; baza przeglądu `750c474`. Implementacja `5afa8c2`, poprawka instrukcji po przeglądzie `ea30b5f`.

Obowiązują [plan](../README.md) i [protokół odbioru](../manual-protocol.md).

**Zmiana zakresu — 2026-11-01:** użytkownik odrzucił bibliotekę prób pełnych
filmów A/B i zlecił usunięcie jej implementacji oraz zastąpienie zapisem sesji.
Wybrał samowystarczalny plik zawierający obrazy, łatwy do przeniesienia na inny
komputer. Ten ticket nie służy porównywaniu kilku dokumentów rejestracji.
Dotychczasowe porównanie pojedynczej pary i ręczne dopasowanie REG-01/01a/02a
pozostają dostępne. REG-06 nadal jest odłożony; REG-07 nie dodaje walidacji jakości.

## Zakres i kryteria odbioru

- [x] GUI udostępnia **Zapisz sesję…** i **Otwórz sesję…**. Otwarcie działa także
  w pustym programie. Sesja zawiera jedną bieżącą serię i jej aktywny stan pracy;
  nie trzeba wcześniej otwierać MPP ani wskazywać plików źródłowych.
  Instrukcja i wyniki: [kroki GUI](../session-manual.md),
  [raport sprawdzeń](../session-results.md), [przegląd](../reviews/REG-07-session.md).
- [x] Jeden plik `.stmsession` zawiera bezstratnie oryginalne obrazy pozostałych
  klatek, ich kolejność, trwałe identyfikatory, pochodzenie i pełne metadane.
  Limit ochronny formatu wynosi 8 GiB łącznych nieskompresowanych danych
  obrazów original i aligned; przekroczenie daje czytelną odmowę. To limit pliku,
  a nie potwierdzenie działania na komputerze z określoną ilością RAM.
  Usunięte klatki nie wracają. Nazwy i ścieżki źródeł są informacją historyczną,
  a brak tych plików na drugim komputerze nie blokuje odczytu.
- [x] Jeśli istnieje aktywny aligned, zapis obejmuje również jego gotowe próbki,
  w tym NaN, ważność, geometrię, rozmiar płótna, padding, odniesienie, przesunięcia
  i dane kalibracji. Otwarcie przywraca te same wartości bez nowej interpolacji,
  estymacji ani uruchamiania modelu. Można zapisać również serię bez aligned.
- [x] Zapis zachowuje metodę bazową, dostępne statusy i diagnostykę aktywnego
  wyniku, bazowe XY i zastosowane ręczne nadpisania z REG-02a oraz końcowe XY.
  Pochodzenie ręczne i brak automatycznej oceny jakości pozostają jawne.
  Po odczycie można dalej poprawiać i cofać korekty tych samych par, jeśli
  aktywny wynik przed zapisem dopuszczał edycję.
- [x] Usunięcie klatki, także odniesienia, nie zmniejsza zapisanego płótna ani
  nie przesuwa pozostałych obrazów. Sesja odtwarza zachowaną geometrię i stan
  edytowalności. Jeśli usunięcie unieważniło dalsze ręczne poprawki, nadal
  wymagają one nowej rejestracji; zapis/odczyt nie znosi tego ograniczenia.
- [x] Przywracane są wybrana klatka, original/aligned, gamma, proporcje pikselowe,
  zoom i przesunięcie widoku osobno dla original/aligned, FPS, pętla oraz wybrana
  metoda i ustawienia Deep Matcher. Odtwarzanie po otwarciu pozostaje zatrzymane.
  Ścieżka wag jest ustawieniem, nie warunkiem wczytania gotowych wyników;
  dostępność modelu jest sprawdzana dopiero przy nowym obliczeniu.
- [x] Zapis i odczyt działają w tle, pokazują postęp i umożliwiają anulowanie.
  Podczas operacji skład serii i zapisywany stan nie mogą się zmieniać.
  Nowa sesja zastępuje bieżącą dopiero po pełnym, poprawnym odczycie. Błąd lub
  anulowanie zachowują dotychczasową pracę i istniejący plik docelowy.
- [x] Format jest wersjonowany, początkowo wersja 1. Nieobsługiwana wersja,
  uszkodzone obrazy/metadane, niezgodna geometria lub powiązania klatek powodują
  czytelną odmowę. Nie uzupełniamy brakujących danych fikcyjnym XY ani oceną jakości.
- [x] MPP/AVI po otwarciu sesji korzystają z odtworzonej aktywnej serii i aligned.
  Zachowują dotychczasowe opcje, wartości i metadane. Ten ticket nie zmienia
  formatów eksportu; sesja jest zapisem pracy, odrębnym od eksportu filmu.
- [x] Usunięto bibliotekę pełnych prób A/B i obsługę `*.stmtrial.json` dodane
  w poprzedniej implementacji REG-07. Istniejące pliki użytkownika pozostają
  na dysku. Nie wymagamy migracji tego wycofanego formatu.

Poza zakresem: biblioteka wielu prób, zapis diagnostycznych prób par, przerwanych
rejestracji i niezastosowanych szkiców ręcznych, historia każdego kliknięcia,
nowy algorytm dopasowania oraz zmiana dotychczasowego okna porównania pary.
Przyszłe dane grafu i podgląd jego kandydata należą do REG-08a/08b jako osobne
rozszerzenia sesji. Nie są ukrytą częścią tego ticketu.

## Publiczne granice TDD i automatyczne sprawdzenia

- **Stan programu → plik → odtworzona sesja:** identyczne oryginały i aligned,
  NaN/ważność, geometria i kalibracja, kolejność/pochodzenie, baza/nadpisania
  oraz stan widoku. Próby obejmują brak aligned, dwie korekty ręczne i usunięcie
  klatki odniesienia. Odczyt nie wywołuje rejestracji ani dostępu do modelu.
- **Zapis/odczyt → sukces, błąd lub anulowanie:** atomowa podmiana, ochrona
  wcześniejszej pracy/pliku, nieznana wersja i uszkodzony zapis; zwolnienie
  zasobów oraz brak końcowego częściowego pliku.
- **GUI → wznowienie pracy:** odczyt w pustym oknie, odtworzona nawigacja
  i ustawienia, dalsza ręczna korekta/cofnięcie oraz eksport aktywnego wyniku.
  Qt offscreen jest testem automatycznym, odrębnym od ręcznej próby GUI.

## Próba manualna

Uruchom `python -m stmviewer.main` w środowisku `netcat`. Dane:
`tests/stmviewer/fixtures/registration/cpu.mpp` oraz `data/MOVIE_4.mpp`.
Dla MOVIE_4 usuń źródłowe klatki 1 i 2 przed rejestracją.

1. Otwórz serię bez rejestracji, wybierz inną klatkę, gamma, zoom/przesunięcie,
   FPS i pętlę. Zapisz sesję, uruchom program ponownie i otwórz samą sesję.
   Sprawdź klatki, metadane, ustawienia i zatrzymane odtwarzanie.
2. Wykonaj pełną rejestrację. Na małym wzorcu sprawdź dwie zastosowane ręczne
   korekty różnych par; na MOVIE_4 sprawdź wybraną problematyczną parę według
   protokołu. Ustaw osobny widok original i aligned, zapisz sesję.
3. Przenieś kopię sesji do innego katalogu/komputera bez źródłowego MPP i wag.
   Otwórz ją bez wcześniejszego importu. Sprawdź ten sam film, płótno, brakujące
   próbki, przesunięcia i historię. Nie może ruszyć ponowna rejestracja.
4. Kontynuuj ręczną korektę i cofnij jedną z wcześniejszych. Pozostała korekta
   ma zostać. Zapisz i ponownie otwórz sesję. Wyeksportuj małe MPP+metadane
   oraz AVI; sprawdź MPP w Viewerze, AVI w VLC i zgodność z aktywnym aligned.
5. W oddzielnej kopii pracy usuń klatkę, także źródłowe odniesienie, zapisz
   i otwórz sesję. Geometria i eksport pozostałych obrazów pozostają takie same;
   dalsza ręczna edycja nadal wymaga nowej rejestracji.
6. Otwórz przygotowany uszkodzony plik i plik z nieznaną wersją. Anuluj długi
   odczyt/zapis. Dotychczasowa sesja i wcześniejszy plik docelowy muszą zostać
   poprawne. Sprawdź następnie zwykłe otwarcie i zapis.
7. Otwórz dotychczasowe porównanie pary: nawigacja, nakładka, wynik zachowany
   i bieżący oraz **Zastosuj do filmu** działają jak przed zmianą REG-07.
   Program nie wymaga tworzenia ani porównywania pełnych prób A/B.

**Oczekiwany wynik:** przenośny zapis jednej bieżącej pracy, który pozwala
wznowić ręczne dopasowanie i eksport dokładnie od zapisanego stanu.
Jakość rejestracji nie zmienia się od samego zapisu i odczytu.
