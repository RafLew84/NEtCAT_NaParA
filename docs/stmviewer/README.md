# STM Viewer

Program do przeglądania obrazów i sekwencji STP/S94/MPP, rejestracji
oraz eksportu MPP/AVI. Katalog aplikacji: `stmviewer/`.

## Stan aplikacji

Gotowe są osobny punkt uruchomienia, podstawowe okno PyQt6 i akcja zakończenia.
Okno nie wczytuje ani nie zapisuje jeszcze plików i nie wykonuje rejestracji.
Mapa decyzji jest zamknięta: specyfikacja pierwszej wersji jest gotowa do
implementacji. Nie oznacza to wdrożenia funkcji ani zaliczenia odbioru.

[Kryteria odbioru](issues/06-acceptance.md#answer) obejmują Ubuntu 24.04 i
Windows 11, uruchomienie z repozytorium, 16 GB wolnego RAM, SSD i NVIDIA/CUDA
z minimum 8 GB VRAM. Dane typowe uzupełnia test 1000 klatek 512 × 512;
filmy AVI sprawdzamy w VLC na obu systemach. [Inwentarz lokalny](acceptance-reconnaissance.md)
opisuje dostępne pomiary, sprzęt i granice wykonanych sprawdzeń.

## Mapa

- [STM Viewer — mapa pierwszej wersji](map.md) — cel, zakres i indeks zamkniętych decyzji.
- [Tickety](issues/) — pytania do rozstrzygnięcia, po jednym w pliku.
- [Słownik STM Viewer](GLOSSARY.md) — pojęcia serii i rejestracji.
- [Rozpoznanie istniejącego kodu](reconnaissance.md) — fakty, zależności i ograniczenia.
- [Przekazanie](handoff.md) — wynik sesji i potrzebne wspólne zmiany.

Lokalny tracker adaptuje konwencję `wayfinder` do wymaganych przez repo ścieżek
`docs/stmviewer/`, zamiast `.scratch/`. Pliki wersjonujemy na gałęzi `viewer/*`.
Mapa i tickety mają wyłącznie etykiety `wayfinder:*`.

Ticket ma `Type`, `Status` (`open`, `claimed`, `resolved`), `Assignee`, `Parent`
i `Blocked by`. Brak zależności oznaczamy `none`; pozostałe wskazują numery
plików. Dostępny ticket jest otwarty, nieprzejęty i ma wszystkie blokujące
tickety rozwiązane. Wybieramy pierwszy według numeru.

Przed pracą ustaw `Status: claimed` i `Assignee: rlew` (osoba prowadząca mapę).
Komentarze dopisuj pod `Comments`. Rozstrzygnięcie zapisz jako `Answer`, ustaw
`Status: resolved` i dopisz nazwany link z krótkim wynikiem do mapy. Nie zmieniaj
samego pytania w magazyn decyzji. W sesji rozstrzygamy najwyżej jeden ticket
(wyjątek skillu: research); tworzenie mapy nie zamyka ticketów.

## Uruchomienie

Z katalogu głównego worktree, w jego środowisku:

```bash
python -m stmviewer.main
```

[Przygotowanie środowiska](../../README.md) i
[praca równoległa](../PARALLEL_DEVELOPMENT.md).

## Kod do wykorzystania i testy

- Czytniki: `napara/io/`; dane obrazu: `napara/core/data_models.py`.
- Viewer: `napara/gui/widgets/viewer_widget.py`.
- Rejestracja: `nanotrack/registration/`.
- Testy nowych funkcji: `tests/stmviewer/` (na razie katalog startowy).

Współdzielony kod wymaga dodatkowych zależności poza minimalnym PyQt6 szkieletu.
Ich dobór oraz zmiany wspólnych modułów koordynuje sesja integracyjna.
