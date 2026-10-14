# STM Viewer

Program do przeglądania obrazów i sekwencji STM, zapisu STP/MPP/S94
oraz rejestracji obrazów. Katalog aplikacji: `stmviewer/`.

## Stan początkowy

Gotowe są osobny punkt uruchomienia, podstawowe okno PyQt6 i akcja zakończenia.
Okno nie wczytuje ani nie zapisuje jeszcze plików i nie wykonuje rejestracji.
Zakres dalszej implementacji określi nowa mapa użytkownika.

## Mapa

Dodaj mapę jako `docs/stmviewer/map.md`, a zadania do `docs/stmviewer/issues/`.
Pliki wersjonuj na gałęzi `viewer/*`. Plik `handoff.md` powstaje przy przekazaniu
zadania do sesji integracyjnej.

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
