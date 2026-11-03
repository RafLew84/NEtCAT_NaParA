# STM Domains

Program do wykrywania i analizy domen pól molekularnych na obrazach STM.
Katalog aplikacji: `stmdomains/`.

## Stan początkowy

Gotowe są osobny punkt uruchomienia, podstawowe okno PyQt6 i akcja zakończenia.
Wczytywanie, metody wykrywania, definicja domeny i kryteria oceny będą ustalone
w nowej mapie użytkownika. Szkielet nie wybiera modelu ani algorytmu.

## Mapa

Dodaj mapę jako `docs/stmdomains/map.md`, a zadania do `docs/stmdomains/issues/`.
Pliki wersjonuj na gałęzi `domains/*`. Plik `handoff.md` powstaje przy przekazaniu
zadania do sesji integracyjnej.

## Uruchomienie

Z katalogu głównego worktree, w jego środowisku:

```bash
python -m stmdomains.main
```

[Przygotowanie środowiska](../../README.md) i
[praca równoległa](../PARALLEL_DEVELOPMENT.md).

## Kod do oceny i testy

- Istniejąca analiza molekularna: `moltrack/analysis/` oraz `tests/moltrack/`.
- Czytniki i model obrazu: `napara/io/`, `napara/core/data_models.py`.
- Viewer: `napara/gui/widgets/viewer_widget.py`.
- Testy nowych funkcji: `tests/stmdomains/` (na razie katalog startowy).

Współdzielony kod i modele mogą wymagać dodatkowych zależności poza PyQt6 szkieletu.
Nowe metody będą oceniane na danych i kryteriach wskazanych w mapie.

## Rozpoznanie metod

- [Wykrywanie domen i ocena metod level set](research-domain-detection-level-sets.md)
  — przegląd źródeł z 2026-10-16 dla dwóch celów: pokrycie/wyspy oraz orientacja
  i uporządkowanie sieci molekuł. Zawiera propozycję eksperymentu porównawczego;
  nie stanowi wyboru algorytmu ani walidacji na danych projektu.
