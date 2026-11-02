# STM Viewer — mapa pierwszej wersji

Label: wayfinder:map
Status: resolved

## Destination

Uzgodniona specyfikacja małej, wewnętrznej przeglądarki STM: wczytanie serii,
podgląd i odtwarzanie, usuwanie klatek, rejestracja oraz eksport MPP/AVI.
Mapa kończy się, gdy decyzje potrzebne do implementacji są rozstrzygnięte.

## Notes

- 2026-11-02: rozszerzono plan okna parametrów na wszystkie 13 obecnych metod.
  [REG-15](registration/issues/15-method-parameters.md) dostarcza edytor
  i AKAZE/LightGlue; [REG-15a](registration/issues/15a-cpu-method-parameters.md)
  dodaje pozostałe metody klasyczne,
  a [REG-15b](registration/issues/15b-model-method-parameters.md) modele i hybrydy.
  Jedno okno, oddzielne profile, zachowane domyślne działanie, sesja/MPP
  i ręczny odbiór po każdym etapie. RoMa zachowa jedno miejsce edycji parametrów.
  To aktualizacja planu, bez implementacji i bez zmiany odbioru REG-14.

- 2026-11-02: na zlecenie użytkownika dodano
  [REG-15: Okno parametrów metod](registration/issues/15-method-parameters.md).
  Menu główne otwiera mały edytor AKAZE/LightGlue, z przygotowaniem kontrastu,
  wspólną konfiguracją pary/filmu/grafu i zapisem parametrów wyniku w sesji/MPP.
  Zakres przygotowany, implementacja niewykonana; status REG-14 bez zmian.

- 2026-11-02: wdrożono [REG-14: AKAZE](registration/issues/14-akaze.md),
  status `ready-for-review`. [Instrukcja](registration/akaze-manual.md),
  [wyniki 72 prób](registration/akaze-results.md), [testy](registration/reviews/REG-14.md).
  Metoda CPU bez wag działa w parze, filmie, grafie, sesji i eksporcie.
  AKAZE odmówił 18/18 wybranych par STM; pełne grafy są rozłączne.
  Kompletny wzorzec przeszedł cały cykl. Odbiór manualny jeszcze niewykonany.
  Poniższe wpisy zachowują historię wcześniejszych zleceń i odbiorów.

- 2026-11-02: użytkownik potwierdził testy manualne [REG-13](registration/issues/13-lightglue-superpoint.md)
  po diagnozie odmowy 2/32. Status `done`; ograniczenia LightGlue na MOVIE_4/MOVIE_8
  pozostają zapisane. REG-14 odblokowany, czeka na osobne zlecenie.

- 2026-11-02: wdrożono [REG-13](registration/issues/13-lightglue-superpoint.md),
  status `ready-for-review`. [Instrukcja](registration/lightglue-manual.md),
  [wyniki](registration/lightglue-results.md), [testy](registration/reviews/REG-13.md).
  Para, łańcuch, graf, sesja i eksport działają; 814 testów Viewera zaliczonych.
  LightGlue dał wynik dla 12/18 par; oba pełne grafy STM pozostały rozłączne.
  Manualny odbiór użytkownika niewykonany, REG-14 czeka. Poniższe wpisy
  zachowują historię przygotowania i wcześniejszych decyzji.

- 2026-11-02: na osobne zlecenie pobrano [kod i wagi LightGlue/SuperPoint](registration/lightglue-environment.md).
  Próby CPU/CUDA na znanym XY zaliczone, bez zmian pakietów `netcat`.
  REG-13 nadal `ready-for-agent`; funkcja w aplikacji i manualny odbiór przed nami.

- 2026-11-02: na zlecenie użytkownika rozszerzono osobny plan rejestracji o
  [REG-13: LightGlue + SuperPoint](registration/issues/13-lightglue-superpoint.md)
  i [REG-14: AKAZE](registration/issues/14-akaze.md). Status `ready-for-agent`;
  REG-14 czeka na odbiór manualny REG-13. Każdy etap obejmuje użycie metody
  w parze, filmie i grafie oraz sesję/eksport. To przygotowanie ticketów,
  bez implementacji i zmiany historycznych odbiorów pierwszej wersji.

- 2026-11-02: użytkownik potwierdził „testy manualne ok” dla
  [REG-12](registration/issues/12-matchanything.md). Status `done`;
  zamknięto odbiór MatchAnything-ELoFTR. Wyniki pomiarów i ograniczenia
  pozostają bez zmian; brak osobnego potwierdzenia Windows, VLC i karty 8 GB.

- 2026-11-02: na zlecenie `implement 12` wdrożono
  [MatchAnything-ELoFTR](registration/issues/12-matchanything.md), commit `b4d9441`.
  Status `ready-for-review`; [wyniki](registration/matchanything-results.md)
  obejmują oba filmy i ograniczenia jakości, [odbiór ręczny](registration/matchanything-manual.md)
  pozostaje niewykonany. Przeglądy standardów/specyfikacji bez uwag.

- 2026-11-02: na zlecenie użytkownika pobrano kod i wagi
  [MatchAnything-ELoFTR](registration/matchanything-environment.md).
  Próby CPU/CUDA zaliczone w niezmienionym `netcat`; nie potrzeba instalacji
  dodatkowych bibliotek dla sprawdzonego importu modelu. REG-12 pozostaje
  `ready-for-agent`, bez rozpoczęcia integracji aplikacji.

- 2026-11-02: użytkownik potwierdził „testy manualne ok” dla
  [REG-11](registration/issues/11-roma-v2.md). Status `done`;
  REG-12 odblokowany, lecz jego implementacja wymaga osobnego zlecenia.
  Wyniki prób i ograniczenia RoMa pozostają zapisane bez zmian.

- 2026-11-02: na kolejne zlecenie wdrożono [REG-11](registration/issues/11-roma-v2.md)
  z procesem RoMa w osobnym środowisku. Po przeglądzie poprawiono zachowanie
  konfiguracji RoMa przy zapisie innej wybranej metody. Status `ready-for-review`;
  [wyniki](registration/roma-results.md) i [ręczna próba](registration/roma-manual.md).
  REG-12 pozostaje zablokowany odbiorem. Jakość modelu nie jest założona z góry.

- 2026-11-02: użytkownik wybrał osobne środowisko `netcat-romav2` i proces
  dla modelu, przy zachowaniu GUI i reszty programu w `netcat`. Zlecił tylko
  przygotowanie środowiska i aktualizację [REG-11](registration/issues/11-roma-v2.md).
  [Środowisko, lokalne zasoby i próby CPU/CUDA](registration/roma-environment.md)
  są gotowe; integracja aplikacji pozostaje do realizacji, status `ready-for-agent`.

- 2026-11-02: użytkownik potwierdził „testy manualne ok” po poprawce
  [REG-10](registration/issues/10-efficient-loftr.md). Etap zamknięto jako
  `done`; REG-11 jest odblokowany, lecz wymaga osobnego zlecenia.

- 2026-11-02: po zgłoszeniu odmów rzeczywistych MPP użytkownik zaakceptował
  pokazywanie niepewnych wyników EfficientLoFTR. [Poprawka REG-10](registration/efficient-loftr-weak-results.md)
  zachowuje słabe oszacowania z ostrzeżeniem; brak punktów nadal oznacza odmowę.
  Nowe próby dają kompletny graf LS MOVIE_4/MOVIE_8 i cały łańcuch MOVIE_8.
  Przed późniejszym odbiorem użytkownika status wynosił `ready-for-review`.

- 2026-11-02: na zlecenie użytkownika wdrożono
  [REG-10: EfficientLoFTR](registration/issues/10-efficient-loftr.md).
  W chwili wdrożenia status wynosił `ready-for-review`; testy i przeglądy
  były zakończone, ręczny odbiór nastąpił po poprawce. [Wyniki](registration/efficient-loftr-results.md) obejmują
  pełne oba filmy: przed poprawką graf nowej metody był rozłączny. REG-11/12 nie rozpoczęto.

- 2026-11-02: użytkownik odłożył [REG-09](registration/issues/09-scanline-diagnostics.md)
  („pomińmy na razie ten etap”). Status `planned`, implementacja nierozpoczęta;
  wznowienie wymaga osobnego zlecenia. Etap nie blokuje REG-10.

- 2026-11-02: na osobne zlecenie użytkownika rozpoczęto implementację REG-08e.
  Osiem istniejących metod zasila wspólny LS/Huber; przygotowano
  [sesje i instrukcję ręcznej próby](registration/multiframe-methods-manual.md).
  Testy i przeglądy zakończono; użytkownik potwierdził „testy manualne ok”
  2026-11-02. Status `done`. Wtedy REG-10 pozostawał nierozpoczęty.
- 2026-11-02: dodano [REG-08e](registration/issues/08e-multiframe-methods.md),
  wybór istniejących metod dopasowania par w obecnym oknie wieloklatkowym
  z LS/Huberem. Status `ready-for-agent`, bez implementacji; w planie po
  REG-08c i przed REG-10. Oddzielnie zapisano wycofanie implementacji REG-08d
  commitem `c8e9141` na życzenie użytkownika. REG-08e nie przywraca dalszych odniesień.

- 2026-11-01: wdrożono [REG-08c](registration/issues/08c-graph-movie-application.md),
  jawne zastosowanie LS/Hubera, ręczne poprawki i eksport aktywnego filmu,
  zapis w sesji oraz przywrócenie poprzednika. Użytkownik potwierdził
  „testy manualne ok”; status `done`. Na jego życzenie dodano dialog
  informujący o niekompletnym wyniku Hubera.
  [Instrukcja](registration/graph-application-manual.md),
  [wyniki i przegląd](registration/reviews/REG-08c.md). Wtedy REG-10 czekał na zlecenie.

- 2026-11-01: wdrożono [REG-08b](registration/issues/08b-robust-graph.md),
  blokowy Huber na zapisanych relacjach LS, porównanie i wiele wariantów w sesji.
  Użytkownik potwierdził „testy manualne ok”; status `done`. [Instrukcja próby](registration/robust-graph-manual.md),
  [wyniki i ograniczenia](registration/robust-graph-results.md).
  Wtedy odblokowano REG-08c; późniejszą realizację opisano powyżej.

- 2026-11-01: użytkownik potwierdził „testy manualne ok” dla
  [REG-08a](registration/issues/08a-window-graph.md). Etap ma status `done`;
  Wtedy odblokowano REG-08b; jego późniejszą realizację opisano powyżej. Zastosowanie grafu do filmu
  i eksportu nadal należy do REG-08c.

- 2026-11-01: na zlecenie użytkownika usunięto z [planu trudnych filmów](registration/README.md)
  osobny REG-08 — diagnostykę trójek. Po odebranym zapisie sesji REG-07 następuje
  REG-08a — graf dopasowań. Pozostała numeracja i statusy odbiorów pozostają.

- 2026-10-31: rozszerzono [plan trudnych filmów](registration/README.md) o graf
  dopasowań wielu klatek oraz osobne próby EfficientLoFTR, RoMa v2 i
  MatchAnything-ELoFTR. Każdy etap ma ręczny odbiór; zmiana dotyczy późniejszego
  rozwoju metod i nie oznacza wykonania ani odbioru tych funkcji.

- 2026-10-28: użytkownik zlecił osobny [plan rozwoju rejestracji
  trudnych filmów](registration/README.md), z ręcznym odbiorem po każdym
  tickecie REG. Rozpoczyna on późniejszy etap rozwoju metod; nie zmienia
  zamkniętych decyzji ani statusów odbioru pierwszej wersji.

- Pracujemy w `NEtCAT-viewer`, na gałęzi `viewer/*`. Zakres:
  `stmviewer/`, `tests/stmviewer/`, `docs/stmviewer/`.
- Jest to mapa decyzji według `wayfinder`, nie lista zadań implementacyjnych.
  Przy rozmowie o decyzjach stosujemy `grilling` i `domain-modeling`;
  ticket o podglądzie korzysta z `prototype`.
- Aplikacja dla kilku osób z małej grupy. Preferujemy prostą obsługę i mały
  zakres; bez rozbudowy do platformy analitycznej.
- Wymagania wejściowe: STP/S94/MPP; zoom i gamma; Play/Pause i regulowana
  prędkość; usuwanie klatki; rejestracja na bazie NanoTrack; przełączanie
  original/aligned; powiększony obszar po rejestracji; zapis MPP i AVI.
- Wynik rejestracji zajmuje miejsce oryginału w podglądzie. Możliwość powrotu
  do widoku original wymaga zachowania oryginalnych danych w programie.
- Zgłoszone przez użytkownika wybory oraz pytania szczegółowe znajdują się
  w komentarzach odpowiednich ticketów. Otwarte tickety nie są decyzjami
  zamkniętymi; utworzenie mapy nie rozstrzyga ich automatycznie.
- Stan kodu i środowiska: [Rozpoznanie istniejącego kodu](reconnaissance.md).
  Terminologia: [Słownik STM Viewer](GLOSSARY.md).
- Można używać lokalnego środowiska conda `netcat`. Modele, dane i środowiska
  pozostają poza Git. Wspólne zmiany zgłaszamy sesji integracyjnej.
- Lokalny tracker: ta mapa i osobne pliki w `issues/`, zgodnie z instrukcjami
  repozytorium. Reguły statusów i zależności opisuje [README](README.md).

## Decisions so far

Aktualizacja po implementacji: użytkownik zlecił [ujednolicenie zapisu
oraz białe tło braków](implementation/issues/13-white-background.md).
Ta decyzja zastępuje wcześniejszą szachownicę i dodatkowe warianty GUI
WSxM/NaN. Rejestracja i zachowanie braków w parze MPP+JSON pozostają.

- [Seria wejściowa i usuwanie klatek](issues/01-frame-series.md): ustalono kolejność,
  zastępowanie całej serii, zgodność wymiarów oraz usuwanie z zachowaniem pochodzenia klatek.
- [Podgląd, gamma i odtwarzanie serii](issues/02-preview-playback.md): wybrano wariant B
  z paskiem miniatur oraz zasady Play/Pause, wspólnej gamma, zoomu i szachownicy poza pomiarem.
- [Rejestracja i życie wyniku aligned](issues/03-registration.md): ustalono dopasowanie
  NanoTrack, podmianę wyniku po sukcesie, zachowanie po usuwaniu oraz geometrię i brakujące dane.
- [Zapis MPP z wartościami i metadanymi](issues/04-mpp-export.md): ustalono zapis
  całej serii, towarzyszące metadane, zachowanie NaN i niejednorodnej kalibracji
  oraz zasady ponownego odczytu i rejestracji.
- [Opcje filmu AVI](issues/05-avi-export.md): ustalono pełne obrazy, zakres klatek,
  gamma/FPS, tła i opisy, kontrast, proporcje oraz wybór MJPG/FFV1.
- [Dane i kryteria odbioru pierwszej wersji](issues/06-acceptance.md): ustalono
  platformy i sprzęt, zestaw pomiarów i dużą serię, płynność oraz odbiór MPP/AVI i GUI.

## Not yet specified

Brak otwartych decyzji potrzebnych do rozpoczęcia implementacji.
Rozstrzygnięto wszystkie sześć ticketów. Specyfikacja jest gotowa; aplikacja pozostaje
szkieletem, a odbiór działającego programu będzie wykonany po implementacji.
Potrzeby wspólnych zmian i ograniczenia sprawdzeń: [przekazanie](handoff.md).

## Out of scope

- Odwracanie kolejności klatek — wycofane przez użytkownika 2026-10-19 w
  [decyzji o rejestracji](issues/03-registration.md#answer); wcześniejsze odpowiedzi skorygowano.
- Automatyczne pobieranie wag modeli z aplikacji — poza zakresem pierwszej wersji.

- Implementacja produkcyjna podczas tworzenia tej mapy.
- Przygotowanie instalatora lub samodzielnego pliku wykonywalnego pierwszej wersji.
- Wymaganie zgodności z WSxM jako warunek pierwszego odbioru — pozostaje próbą
  dodatkową według [kryteriów odbioru](issues/06-acceptance.md#answer).
- Rozwijanie algorytmów i strojenie parametrów rejestracji — późniejszy etap,
  zgodnie ze zleceniem użytkownika.
- Funkcje analizy domen, detekcji i trackingu z pozostałych aplikacji.
- Zapis STP/S94 w pierwszej wersji: bieżące zlecenie określa eksport MPP/AVI.
