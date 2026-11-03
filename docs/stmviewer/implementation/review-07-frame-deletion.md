# Przegląd ticketu 07 — usuwanie klatek

Data: 2026-10-23. Baza zgodnie z zatwierdzonymi zasadami implementacji:
`e8102e9d21924c8d661e72df223a46343e0183ff`.
Commit implementacji: `bfffd83`.
Diff: `git diff e8102e9d21924c8d661e72df223a46343e0183ff...bfffd83`.

Poniższy raport zachowuje stan z chwili przeglądu. Następnie, 2026-10-23,
użytkownik potwierdził ręczny odbiór („testy manualne ok”).
[Ticket 07](issues/07-frame-deletion.md) ma status `done`. Nie wskazano systemu;
potwierdzenie nie zamyka odrębnych odbiorów platform.

Dwie osie sprawdzili równolegle niezależni agenci zgodnie ze skillem
`code-review`. Przegląd był tylko do odczytu, bez ponawiania testów przez
recenzentów. Statusy i końcowe wyniki uzupełniono po otrzymaniu raportów.

## Standards

**0 naruszeń udokumentowanych zasad; 0 istotnych code smells.**

Przejrzano cały diff, kod otaczający zmiany oraz wskazane standardy.

- Zmiany pozostają w zakresie aplikacji, testów i dokumentacji Viewera,
  zgodnie z `stmviewer/AGENTS.md` i zasadami współpracy. Nie ingerują we
  wspólne moduły.
- Podział odpowiedzialności jest zachowany: okno koordynuje usunięcie
  i wybór klatki, model miniatur aktualizuje pary obraz–miniatura, podgląd
  sam czyści swój stan. Delegacja `Filmstrip.remove_frame()` utrzymuje
  granicę komponentu; nie stanowi niepotrzebnego Middle Man.
- Kod rozróżnia pozycję w serii od pochodzenia i czasu pomiaru, zgodnie
  z `GLOSSARY.md`. Zachowanie istniejących obiektów `ImageFrame` pozwala
  uniknąć kopiowania i ponownego przypisywania metadanych.
- Nowe testy sprawdzają zachowanie przez publiczne kontrolki oraz widoczny
  wynik. Atrapy obejmują dialog wyboru i granicę odczytu pliku, zgodnie
  z uzgodnionymi granicami testowania.
- Instrukcja manualna zawiera uruchomienie, dostępne wzorce, kroki
  i oczekiwane rezultaty. Dokumentacja odróżnia automatyczne próby Qt
  od niewykonanego odbioru ręcznego, zgodnie z `stmviewer/AGENTS.md`.

Nie wskazano poprawek wymaganych przed odbiorem. Źródła: `AGENTS.md`,
`stmviewer/AGENTS.md`, `docs/PARALLEL_DEVELOPMENT.md`, indeks implementacji,
słownik oraz pełny katalog heurystyk Fowler ze skillu. Nie znaleziono
odrębnych CODING_STANDARDS/CONTRIBUTING.

## Spec

**0 usterek implementacji; 0 rozszerzeń zakresu.**

- Usunięcie zatrzymuje Play, wybiera następną albo poprzednią klatkę;
  usunięcie jedynej czyści podgląd i dezaktywuje odpowiednie kontrolki.
- Pozostałe obiekty `ImageFrame` zachowują obrazy, pochodzenie, parametry
  i czasy. Zmieniają się wyłącznie bieżące pozycje w serii.
- Miniatury są usuwane razem z odpowiadającymi im klatkami, a wybór
  synchronizowany po przebudowie modelu.
- Gamma, zoom, przesunięcie i proporcje pozostają zachowane przy przejściu
  na pozostały obraz.
- Usuwanie podczas importu dotyczy starej serii. Anulowanie lub błąd
  pozostawia jej aktualny stan, a sukces zastępuje ją nową serią.
- Operacja nie zapisuje ani nie usuwa źródeł. Nie dodano cofania ani
  odwracania kolejności.

Testy obejmują wymagane przypadki, w tym `[10,20,35] → [10,35]`, nieznane
czasy, opróżnienie i ponowne otwarcie oraz import w tle. Instrukcja manualna
zawiera przygotowane wzorce i oczekiwane wyniki. Ręczny odbiór użytkownika
oraz Windows pozostają osobnymi, niewykonanymi sprawdzeniami. Obsługa aligned
należy do ticketu 08.

Źródła: [ticket 07](issues/07-frame-deletion.md), [decyzja 01](../issues/01-frame-series.md#answer),
[decyzja 02](../issues/02-preview-playback.md#answer), [decyzja 06](../issues/06-acceptance.md#answer),
[słownik](../GLOSSARY.md) oraz zasady odbioru w indeksie implementacji.
Wyniki wykonanych testów i ograniczenia: [przekazanie](../handoff.md).

Łącznie: Standards — 0 ustaleń; Spec — 0 usterek kodu. W żadnej osi nie ma wymaganej poprawki.
