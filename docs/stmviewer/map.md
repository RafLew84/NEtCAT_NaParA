# STM Viewer — mapa pierwszej wersji

Label: wayfinder:map
Status: open

## Destination

Uzgodniona specyfikacja małej, wewnętrznej przeglądarki STM: wczytanie serii,
podgląd i odtwarzanie, usuwanie klatek, rejestracja oraz eksport MPP/AVI.
Mapa kończy się, gdy decyzje potrzebne do implementacji są rozstrzygnięte.

## Notes

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

Brak zamkniętych ticketów. Zebrano wymagania i pierwszą rundę odpowiedzi;
to sesja utworzenia mapy, bez rozwiązywania jej ticketów.

## Not yet specified

Szczegóły podziału implementacji i potrzebnych zmian wspólnych wyłonią się
z kontraktów serii, rejestracji i eksportu. Po ich ustaleniu trzeba sprawdzić,
czy pozostały pytania wymagające osobnych decyzji przed rozpoczęciem budowy.

## Out of scope

- Implementacja produkcyjna podczas tworzenia tej mapy.
- Rozwijanie algorytmów i strojenie parametrów rejestracji — późniejszy etap,
  zgodnie ze zleceniem użytkownika.
- Funkcje analizy domen, detekcji i trackingu z pozostałych aplikacji.
- Zapis STP/S94 w pierwszej wersji: bieżące zlecenie określa eksport MPP/AVI.
