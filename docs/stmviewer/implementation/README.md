# STM Viewer — tickety implementacyjne

Status zestawu: zatwierdzony do realizacji.
Użytkownik zatwierdził 21 ticketów, zależności i zakres testowania 2026-10-19.
Data: 2026-10-19. Baza specyfikacji: `f394eba`.

Źródła: [zamknięta mapa decyzji](../map.md), [słownik](../GLOSSARY.md),
[kryteria odbioru](../issues/06-acceptance.md#answer) i
[inwentarz danych](../acceptance-reconnaissance.md).
Ta lista prowadzi implementację. Nie zmienia statusów ani rozstrzygnięć
mapy i jej sześciu ticketów decyzyjnych.

## Kolejność i efekty

Każdy punkt dostarcza funkcję możliwą do sprawdzenia w działającej aplikacji.
Numery poniżej należą do tej listy, niezależnie od numeracji decyzji mapy.
Zależności wskazują tylko etapy wymagane do pełnego wykonania danej funkcji;
np. AVI original i MPP original mogą powstawać przed rejestracją.

1. **[Pierwszy obraz STP w działającym oknie](issues/01-single-stp.md)**
   - Blokowane przez: brak.
   - Efekt: Użytkownik uruchamia program, otwiera jeden rzeczywisty STP i widzi poprawny obraz oraz jego pochodzenie i metadane.
   - Próba w GUI: Uruchom program i otwórz mały STP z asymetrycznym znacznikiem; sprawdź obraz, orientację, nazwę źródła i parametry.

2. **[Otwarcie i przeglądanie serii STP](issues/02-stp-series.md)**
   - Blokowane przez: 01 (Pierwszy obraz STP w działającym oknie).
   - Efekt: Po uruchomieniu programu użytkownik otwiera jeden lub wiele STP, ogląda rzeczywiste obrazy i przechodzi między klatkami w układzie z dolnym paskiem miniatur.
   - Próba w GUI: Uruchom aplikację i otwórz przygotowane trzy STP o nazwach klatka10, klatka2, klatka1. Oczekuj kolejności 1, 2, 10 i zgodnych miniatur.

3. **[S94 i mieszane serie STP/S94](issues/03-s94-series.md)**
   - Blokowane przez: 02 (Otwarcie i przeglądanie serii STP).
   - Efekt: Użytkownik otwiera S94 albo wspólnie STP i S94 oraz przegląda je na takich samych zasadach jak serię STP.
   - Próba w GUI: Otwórz rzeczywistą parę odpowiadających sobie STP/S94; porównaj orientację i kształt obrazu oraz podane jednostki.

4. **[Otwarcie filmu MPP z czasami i pochodzeniem](issues/04-mpp-series.md)**
   - Blokowane przez: 02 (Otwarcie i przeglądanie serii STP).
   - Efekt: Użytkownik otwiera jeden film MPP, przegląda wszystkie jego klatki i widzi ich źródłową kolejność oraz dostępny czas pomiaru.
   - Próba w GUI: Otwórz mały rzeczywisty MPP i przejdź do pierwszej, środkowej i ostatniej klatki; porównaj liczbę klatek i ich pochodzenie.

5. **[Zoom, gamma i brakujące próbki](issues/05-preview-controls.md)**
   - Blokowane przez: 02 (Otwarcie i przeglądanie serii STP).
   - Efekt: Użytkownik reguluje gamma, przybliża i przesuwa obraz oraz rozpoznaje brakujące próbki podczas ręcznego przeglądania serii.
   - Próba w GUI: Otwórz serię STP i zmień gamma, zoom oraz przesunięcie. Wybierz kolejne klatki; ustawienia pozostają.

6. **[Play, Pause i tempo odtwarzania](issues/06-playback.md)**
   - Blokowane przez: 05 (Zoom, gamma i brakujące próbki).
   - Efekt: Użytkownik odtwarza serię, steruje tempem i pętlą oraz zatrzymuje się na wybranej klatce bez przeskoków w kolejności.
   - Próba w GUI: Odtwórz serię bez pętli do końca, uruchom Play na ostatniej, potem sprawdź pętlę i różne tempa.

7. **[Usuwanie klatek z zachowaniem czasu i pochodzenia](issues/07-frame-deletion.md)**
   - Blokowane przez: 04 (Otwarcie filmu MPP z czasami i pochodzeniem), 06 (Play, Pause i tempo odtwarzania).
   - Efekt: Użytkownik usuwa wybraną klatkę z otwartej serii i nadal widzi poprawny obraz, numer, czas oraz pochodzenie pozostałych klatek.
   - Próba w GUI: Wczytaj trzyklatkowy MPP z rozpoznawalnymi obrazami i czasami, rozpocznij Play i usuń środkową klatkę.

8. **[Rejestracja Phase i pełny widok aligned](issues/08-phase-registration.md)**
   - Blokowane przez: 07 (Usuwanie klatek z zachowaniem czasu i pochodzenia).
   - Efekt: Użytkownik rejestruje bieżącą serię metodą Phase, ogląda pełny powiększony wynik i może wracać do original, ponawiać oraz anulować obliczenia.
   - Próba w GUI: Wczytaj przygotowaną serię z rozpoznawalnym przesunięciem; ustaw gamma/zoom i uruchom Phase.

9. **[Pozostałe metody rejestracji CPU](issues/09-cpu-registration-methods.md)**
   - Blokowane przez: 08 (Rejestracja Phase i pełny widok aligned).
   - Efekt: Użytkownik wybiera Tile+RANSAC, ECC lub Optical Flow i otrzymuje wynik w tym samym podglądzie i cyklu pracy co Phase.
   - Próba w GUI: Zarejestruj mały wzorzec Phase, zmień wybór na każdą dostępną metodę CPU i kolejno uruchom dopasowanie.

10. **[Deep Matcher z lokalnymi wagami](issues/10-deep-matcher.md)**
   - Blokowane przez: 08 (Rejestracja Phase i pełny widok aligned).
   - Efekt: Użytkownik widzi rzeczywistą dostępność Deep Matcher i przy obecnych lokalnych wagach wykonuje rejestrację, również na CUDA, bez pobierania plików przez aplikację.
   - Próba w GUI: Uruchom aplikację bez udostępnionych wag; wybierz Deep Matcher i sprawdź komunikat oraz brak prób pobierania.

11. **[Otwarcie MPP z metadanymi towarzyszącymi](issues/11-mpp-metadata-import.md)**
   - Blokowane przez: 04 (Otwarcie filmu MPP z czasami i pochodzeniem).
   - Efekt: Użytkownik otwiera przygotowaną parę MPP i dodatku, widzi właściwe parametry oraz pochodzenie każdej klatki i rozpoznaje brakujący lub niedopasowany dodatek.
   - Próba w GUI: Otwórz przygotowaną parę z trzema klatkami o różnych parametrach i czasach. Przejdź przez klatki i sprawdź pochodzenie oraz etykiety.

12. **[Zapis original do MPP i ponowne otwarcie](issues/12-original-mpp.md)**
   - Blokowane przez: 03 (S94 i mieszane serie STP/S94), 07 (Usuwanie klatek z zachowaniem czasu i pochodzenia), 11 (Otwarcie MPP z metadanymi towarzyszącymi).
   - Efekt: Użytkownik zapisuje wszystkie pozostałe klatki original jako MPP z metadanymi, zamyka program i otwiera wynik bez utraty wartości, czasów oraz pochodzenia.
   - Próba w GUI: Otwórz mały MPP ze znanymi czasami, usuń środek, zmień gamma i zapisz original. Zamknij/otwórz wynik; sprawdź obrazy, liczbę, czasy i pochodzenie.

13. **[Zapis aligned do MPP z pełną geometrią](issues/13-aligned-mpp.md)**
   - Blokowane przez: 08 (Rejestracja Phase i pełny widok aligned), 12 (Zapis original do MPP i ponowne otwarcie).
   - Efekt: Użytkownik wybiera original albo aligned przy zapisie MPP i po ponownym otwarciu aligned odzyskuje pełny obszar, braki oraz położenie oryginalnego pola każdej klatki.
   - Próba w GUI: Zarejestruj wzorzec z przesunięciem subpikselowym, usuń odniesienie i zapisz aligned.

14. **[Pierwszy film AVI: zakres, FPS i oba kodeki](issues/14-original-avi-basic.md)**
   - Blokowane przez: 07 (Usuwanie klatek z zachowaniem czasu i pochodzenia).
   - Efekt: Użytkownik zapisuje pełne obrazy original jako MJPG lub FFV1, wybiera klatki i FPS, a gotowy film odtwarza w VLC.
   - Próba w GUI: Zapisz oryginalną serię i krótki zakres w obu kodekach, z FPS innym niż Play. Otwórz wyniki w VLC.

15. **[Kontrast, gamma i tła filmu AVI](issues/15-avi-presentation.md)**
   - Blokowane przez: 14 (Pierwszy film AVI: zakres, FPS i oba kodeki).
   - Efekt: Użytkownik wybiera własną prezentację AVI: wspólny lub osobny kontrast, gamma z podglądu lub neutralną oraz czarne, szare lub białe tło.
   - Próba w GUI: Wyeksportuj wzorzec z różnymi jasnościami klatek w obu trybach kontrastu; porównaj obraz w VLC.

16. **[Film AVI z aligned i pełnym obszarem](issues/16-aligned-avi.md)**
   - Blokowane przez: 08 (Rejestracja Phase i pełny widok aligned), 14 (Pierwszy film AVI: zakres, FPS i oba kodeki).
   - Efekt: Użytkownik eksportuje również aligned, zachowując całe powiększone pole filmu i wybrane tło poza ważnymi próbkami.
   - Próba w GUI: Zarejestruj serię, usuń klatkę skrajną i wyeksportuj krótki zakres aligned w obu kodekach.

17. **[Podziałka, numer i czas w AVI](issues/17-avi-annotations.md)**
   - Blokowane przez: 15 (Kontrast, gamma i tła filmu AVI).
   - Efekt: Użytkownik może dodać do filmu podziałkę długości oraz numer klatki i dostępny czas pomiaru, zachowując czysty obraz jako ustawienie domyślne.
   - Próba w GUI: Otwórz serię z kalibracją i czasami, wyeksportuj zakres 5–10 z podziałką/numerem/czasem i obejrzyj w VLC.

18. **[Duża seria: podgląd i rejestracja](issues/18-large-series-preview.md)**
   - Blokowane przez: 08 (Rejestracja Phase i pełny widok aligned).
   - Efekt: Użytkownik otwiera 1000 klatek 512 × 512, płynnie przegląda original/aligned, usuwa klatki i ponawia Phase w przyjętym budżecie zasobów.
   - Próba w GUI: Wygeneruj deterministyczną serię 1000 × 512 × 512 i zapisz jej manifest, następnie otwórz w programie.

19. **[Duże eksporty i wspólna praca funkcji](issues/19-large-exports.md)**
   - Blokowane przez: 13 (Zapis aligned do MPP z pełną geometrią), 16 (Film AVI z aligned i pełnym obszarem), 17 (Podziałka, numer i czas w AVI), 18 (Duża seria: podgląd i rejestracja).
   - Efekt: Użytkownik zapisuje pełną dużą serię do MPP i AVI, również po usunięciu i ponownej rejestracji, z poprawnym połączeniem aligned, kontrastu, teł i opisów.
   - Próba w GUI: Otwórz przygotowany duży wzorzec, wykonaj Phase i usuń wybrane klatki; zachowaj manifest i parametry wyniku.

20. **[Odbiór programu na Ubuntu 24.04](issues/20-ubuntu-acceptance.md)**
   - Blokowane przez: 09 (Pozostałe metody rejestracji CPU), 10 (Deep Matcher z lokalnymi wagami), 19 (Duże eksporty i wspólna praca funkcji).
   - Efekt: Użytkownik odtwarza środowisko na Ubuntu 24.04 i przechodzi pełny scenariusz GUI wraz z odczytem MPP oraz odtwarzaniem obu AVI w VLC.
   - Próba w GUI: Na Ubuntu 24.04 utwórz środowisko według instrukcji i uruchom rzeczywistą aplikację.

21. **[Odbiór programu na Windows 11](issues/21-windows-acceptance.md)**
   - Blokowane przez: 09 (Pozostałe metody rejestracji CPU), 10 (Deep Matcher z lokalnymi wagami), 19 (Duże eksporty i wspólna praca funkcji).
   - Efekt: Użytkownik odtwarza środowisko na Windows 11 i przechodzi pełny scenariusz GUI wraz z odczytem MPP oraz odtwarzaniem obu AVI w VLC.
   - Próba w GUI: Na Windows 11 utwórz środowisko według instrukcji i uruchom rzeczywistą aplikację.

## Praca ze skillem implement

Każdy ticket obejmuje implementację, TDD w uzgodnionych granicach,
sprawdzenia i przegląd kodu oraz commit. Zakresy są tak rozdzielone, żeby
po pojedynczej sesji było co uruchomić i ocenić ręcznie.

1. Podaj tytuł ticketu, sprawdź blokady i zapisz SHA bieżącego HEAD jako
   bazę przeglądu. Zatwierdzenie tego zestawu ustala taką domyślną bazę;
   nie wybieraj później innego punktu pomijającego część zmiany.
2. Stosuj TDD kolejno: jeden publiczny scenariusz → test red → minimalna
   implementacja green. Granice testów są wymienione w każdym tickecie
   wraz z tym, czego dana próba nie sprawdza. Zatwierdzenie podziału obejmuje
   te granice, bez narzucania nazw klas, metod ani prywatnych helperów.
   Nową granicę wykraczającą poza uzgodnione trzeba uzgodnić przed testem.
3. Regularnie wykonuj sprawdzanie typów i pojedyncze pliki testowe.
   Pierwszy ticket ustala z integracją działającą komendę typecheckingu
   dla Viewera; kompilacja składni nie jest sprawdzaniem typów.
4. Po implementacji wykonaj pełny zestaw testów repozytorium raz na końcu,
   a także próby wskazane w tickecie. Raportuj braki danych/GUI/zależności
   oraz wcześniejsze błędy osobno od regresji; nie utożsamiaj pominięcia
   wymaganego sprawdzenia z sukcesem. Po poprawce powtórz odpowiednie testy.
5. Przeprowadź code-review zgodności ze standardami oraz specyfikacją,
   od zapisanej bazy do bieżącej implementacji. Przegląd musi obejmować
   nowy kod: przed przeglądem diffu commitów zapisz lokalny commit roboczy.
   Poprawki po przeglądzie zapisz kolejnym commitem, a przekazanie podaj
   z finalnym zakresem zmian. Nie publikuj ani nie scalaj bez zlecenia.
6. Dołącz ręczny scenariusz, wyniki i ograniczenia; uzupełnij status ticketu
   oraz przekazanie. Granica 1000–1500 linii dotyczy plików, nie całego ticketu:
   jedna funkcja użytkowa może wymagać kilku spójnych modułów.

Tickety odbioru platform nie tworzą od nowa wszystkich testów: uruchamiają
przygotowane zestawy i dodają test regresji tylko dla naprawianego błędu.
Regresje dotyczące wspólnego kodu podlegają również testom jego odbiorców.

## Zasady wykonania i odbioru

- Każdy ticket zawiera efekt użytkowy, kryteria, testy automatyczne oraz kroki
  ręcznej próby z oczekiwanymi wynikami. Po etapie pozostaje uruchamialna
  aplikacja; wynik nie kończy się na niepodłączonej warstwie kodu.
- Przygotuj zależności i minimalne uporządkowanie kodu potrzebne temu etapowi
  przed zmianą zachowania. Obecny mały szkielet nie wymaga osobnego szerokiego
  refaktoru. Wspólne zmiany należą do sesji integracyjnej według
  [reguł współpracy](../../PARALLEL_DEVELOPMENT.md); potrzebny wkład tej sesji jest częścią odbioru
  odpowiedniego ticketu, a nie niewidoczną zależnością po jego zakończeniu.
- Pracuj według [instrukcji STM Viewer](../../../stmviewer/AGENTS.md). Obowiązuje cel do 1000 linii
  i twardy limit 1500 fizycznych linii pliku kodu oraz podział według odpowiedzialności.
  Reguła i sposób liczenia mają jedno źródło w instrukcji aplikacji.
- Zachowaj działanie funkcji dostarczonych wcześniej. Nieaktywne przyszłe
  funkcje nie są wymagane do ręcznej próby bieżącego etapu. Wprowadzając
  wariant aligned, podłącz istniejące gamma/zoom/usuwanie i opcje eksportu.
- Przygotuj małe wzorce potrzebne do próby (np. asymetryczny obraz, brakujące
  czasy, NaN, uszkodzony plik) oraz opis ich wygenerowania. Nie wymagaj
  ręcznego tworzenia binarnego pliku przez osobę testującą. Pomiary i duże
  wyniki pozostają lokalne; ich wybór opisuje inwentarz danych.
- W przekazaniu podaj sposób uruchomienia programu, dane, kroki i oczekiwane
  wyniki, commit oraz faktycznie wykonane sprawdzenia. Testy automatyczne,
  Qt offscreen, ręczne GUI i zewnętrzny VLC to osobne dowody.
- Każdy etap jest gotowy do ręcznej próby na dostępnym stanowisku. Jeżeli
  agent nie ma GUI, danych, Windows lub wag, zapisuje próbę jako niewykonaną
  z przyczyną i pozostawia odtwarzalną instrukcję. Nie deklaruje jej zaliczenia.
  Obowiązkowy końcowy odbiór obejmuje oba systemy i wszystkie wymagane próby.
- Niedostępna opcjonalna metoda ma wyjaśnienie w UI. Przy dostępnych wagach
  wykonuje się również rzeczywistą próbę; atrapa nie potwierdza modelu/CUDA.
  Żaden etap nie uruchamia automatycznego pobierania wag.
- Nie zmieniaj zakresu decyzji: nie ma odwracania kolejności, zapisu STP/S94,
  eksportu wycinka AVI ani strojenia algorytmów. WSxM jest dodatkowym testem.

## Praca z lokalnym trackerem

Docelowe miejsce: wersjonowane `docs/stmviewer/implementation/`, zgodnie
z instrukcją repozytorium. Jeden plik na ticket, odrębnie od zamkniętych decyzji.

Status `ready-for-agent` oznacza przygotowany zakres. Rozpocząć można tylko
wtedy, gdy wszystkie pozycje `Blocked by` mają status `done`; na początku
startuje wyłącznie pierwszy obraz STP w działającym oknie. Podjęty ticket otrzymuje
status `in-progress` i wykonawcę. Po implementacji: `ready-for-review`,
z wynikami sprawdzeń i instrukcją GUI. `done` oznacza spełnione kryteria,
zapisany commit i przekazanie. Wymagana przez ticket, lecz niewykonana próba
pozostawia go w `ready-for-review`. Końcowy odbiór wymaga zaliczonych obu
ticketów platformowych; każdy ocenia tylko swój system.

Kryteria nie stają się zaliczone od samego utworzenia ticketu. Dalsze tickety
mogą ruszać z dowolnej gotowej gałęzi zależności. Praca we wspólnych plikach
i scalanie zmian wymagają koordynacji sesji integracyjnej. Blokady środowiskowe odnotuj w tickecie,
a konkretny potrzebny kontrakt/commit wspólnego kodu w przekazaniu.

## Pokrycie specyfikacji

| Decyzja | Etapy implementacji i odbioru |
| --- | --- |
| Seria wejściowa i usuwanie klatek | 01–04, 07; zachowanie aligned po usunięciu również 08 |
| Podgląd, gamma i odtwarzanie serii | 01–02, 05–06, 08; pomiary dużej serii 18 |
| Rejestracja i życie wyniku aligned | 08–10; odbiór zasobów i platform 18, 20–21 |
| Zapis MPP z wartościami i metadanymi | 04, 11–13; pełne serie i odbiorcy 19–21 |
| Opcje filmu AVI | 14–17; duży film i VLC na obu systemach 19–21 |
| Dane i kryteria odbioru pierwszej wersji | Kryteria w każdym etapie, zbiorczy odbiór 18–21 |

Regresje znalezione podczas integracji opisów z aligned obejmuje etap dużych
eksportów, a problemy platform — osobne odbiory Ubuntu i Windows. Nie odkładamy do nich podstawowej
poprawności importu, stanu zadań ani ochrony wcześniejszych plików.
