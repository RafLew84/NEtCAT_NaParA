# Przegląd ticketu 03 — S94 i mieszane serie

Data: 2026-10-21. Baza zgodnie z zatwierdzonymi zasadami implementacji:
`b904045e7626e97cd924920d9fbb0e52fbdb3bcc`.
Commit implementacji: `d6fbb7dd147ddf94789192b048ab1284a5312e8a`.
Diff: `git diff b904045...d6fbb7d`.

Poniższe ustalenia opisują stan w chwili przeglądu. Później, 2026-10-21,
użytkownik potwierdził testy manualne („testy manualne ok”);
[ticket 03](issues/03-s94-series.md) otrzymał status `done`.

Dwie osie sprawdzili równolegle niezależni agenci zgodnie
ze skillem `code-review`. Przegląd tylko do odczytu, bez ponawiania testów.

## Standards

**0 naruszeń standardów, 0 istotnych zapachów kodu.**

- Odpowiedzialności adaptera, importu pojedynczego obrazu i serii pozostają
  rozdzielone, a oba formaty korzystają ze wspólnego importu serii.
  Lokalny adapter respektuje zakaz zmian modułów wspólnych; uzasadnienie
  oraz potrzebne przyszłe poprawki wspólnego czytnika zapisano w przekazaniu.
- Zmiany GUI zachowują dotychczasową obsługę importu, nawigacji i prezentacji;
  nie wprowadzają zbędnych abstrakcji.
- Testy korzystają z uzgodnionych granic importu i publicznych kontrolek.
  Kontrolowanie opóźnienia na granicy systemu plików sprawdza rzeczywiste
  anulowanie bez zastępowania własnych komponentów atrapami.
- Dokumentacja zawiera uruchomienie, generowane wzorce, kroki i oczekiwane
  wyniki. Rozróżnia automatyczne próby offscreen/xcb od niewykonanego odbioru
  użytkownika i Windows, zgodnie z instrukcją aplikacji.
- Powtórzenie części dekodowania S94 jest uzasadnione ograniczeniem edycji
  wspólnego czytnika i opisane w dokumentacji. Nie stwierdzono istotnych
  przypadków heurystyk Fowler wymagających poprawki.

Źródła: `AGENTS.md`, `stmviewer/AGENTS.md`, `docs/PARALLEL_DEVELOPMENT.md`,
indeks implementacji oraz pełny katalog heurystyk Fowler ze skillu.
Nie znaleziono odrębnych CODING_STANDARDS/CONTRIBUTING.
Wskazane przez recenzenta uzupełnienie końcowego wyniku pełnych testów
oraz identyfikatora commita zostało wykonane w przekazaniu.

## Spec

**0 nowych usterek, 0 brakujących wymagań, 0 rozszerzeń poza zakres.**

- Adapter dekoduje signed little-endian, rozróżnia wartości fizyczne i surowe
  oraz transponuje dane razem z wymiarami, skalą i offsetami.
- Import wspólnie sortuje STP/S94, porównuje wymiary po transformacji
  i zachowuje metadane każdej klatki.
- GUI udostępnia oba formaty i opis braku kalibracji; istniejący przebieg
  importu chroni poprzednią serię przy błędzie lub anulowaniu.
- Zmiana zachowuje wcześniejszą nawigację, zoom i poprawkę pojedynczego
  podświetlenia miniatur. Testy rozszerzają anulowanie na S94.
- Dokumentacja poprawnie rozdziela próby automatyczne od niewykonanego
  odbioru użytkownika i Windows. `ready-for-review` odpowiada temu stanowi.
  Adapter i przekazanie potrzeb wspólnego czytnika respektują granice worktree.

Źródła: [ticket 03](issues/03-s94-series.md) oraz wskazane decyzje
[01](../issues/01-frame-series.md#answer) i
[06](../issues/06-acceptance.md#answer).

Łącznie: Standards — 0 ustaleń; Spec — 0 ustaleń. Brak usterek wymagających poprawki w obu osiach.
