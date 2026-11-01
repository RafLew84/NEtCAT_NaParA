# STM Viewer — mapa pierwszej wersji

Label: wayfinder:map
Status: resolved

## Destination

Uzgodniona specyfikacja małej, wewnętrznej przeglądarki STM: wczytanie serii,
podgląd i odtwarzanie, usuwanie klatek, rejestracja oraz eksport MPP/AVI.
Mapa kończy się, gdy decyzje potrzebne do implementacji są rozstrzygnięte.

## Notes

- 2026-11-01: wdrożono [REG-08b](registration/issues/08b-robust-graph.md),
  blokowy Huber na zapisanych relacjach LS, porównanie i wiele wariantów w sesji.
  Status `ready-for-review`, ręczny odbiór oczekuje. [Instrukcja próby](registration/robust-graph-manual.md),
  [wyniki i ograniczenia](registration/robust-graph-results.md).
  Zastosowanie do aligned/eksportu pozostaje REG-08c.

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
