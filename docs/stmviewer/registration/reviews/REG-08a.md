# REG-08a — karta wykonania i odbioru

Data: 2026-11-01. Status: `in-progress`.
Baza: `e12a79440b806a9f44c3fe5b112212052ae6ce29`.

Implementacja grafu, sesji i GUI jest gotowa. Pełny zestaw repozytorium trwa;
przeglądy Standards i Spec zostaną uzupełnione po lokalnym commicie kodu.

[Ticket](../issues/08a-window-graph.md), [instrukcja manualna](../window-graph-manual.md),
[rzeczywiste próby i ograniczenia](../window-graph-results.md).

## Standards

Przegląd od ustalonej bazy: oczekuje.

## Spec

Przegląd od ustalonej bazy: oczekuje.

## Sprawdzenia

- 28 testów silnika/solvera, 7 nowych testów sesji, 11 testów podglądu/GUI,
  3 testy integracji głównego okna przechodzą w próbach poszczególnych plików.
- Mypy: 66 modułów, bez błędów; Ruff i `git diff --check`: bez błędów.
- Rzeczywisty Outdoor na CUDA: wzorzec oraz pełne MOVIE_4 (bez dwóch pierwszych)
  i MOVIE_8, oba okna; zapis/odczyt wszystkich sesji, render wszystkich klatek.
- Układ obejrzano na zrzutach Qt offscreen. Nie jest to ręczny odbiór aplikacji.

## Odbiór manualny

Niewykonany. Użytkownik ma ocenić jakość na obu filmach oraz przepływ opisany
w instrukcji. Windows 11 i stanowisko GPU 8 GB pozostają niesprawdzone.
