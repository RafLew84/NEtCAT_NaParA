# Przekazanie — rozpoznanie metod wykrywania domen

Data: 2026-10-16
Gałąź przygotowania notatki: `viewer/start`, worktree `NEtCAT-viewer`.
Commit dokumentacji: identyfikator w końcowej wiadomości sesji.

## Zakres i wynik

Na bezpośrednie zlecenie użytkownika, przed dalszą pracą nad mapą STM Viewer,
zbadano metody wykrywania domen i przydatność level set, w tym podejście
Gibou–Fedkiwa. Użytkownik wskazał dwa cele: orientacja/uporządkowanie sieci
molekuł oraz obszary pokrycia materiałem/wyspy.

Wyniki i źródła: [Wykrywanie domen i ocena metod level set](research-domain-detection-level-sets.md).
To osobna notatka badawcza, bez przypisanego ticketu i bez wyboru metody
produkcyjnej. Nie zmieniono mapy STM Viewer ani kodu aplikacji. W tym worktree
nie ma mapy STM Domains; nie tworzono jej w ramach przeglądu literatury.

## Sprawdzenia i ograniczenia

- Sprawdzono publikacje źródłowe oraz odpowiednie fragmenty kodu MolTrack.
- Sprawdzono lokalne linki dokumentacji i formatowanie zmian.
- Nie uruchamiano algorytmów na danych, benchmarków, testów aplikacji ani GUI.
  Nie ma zmierzonej skuteczności detekcji ani wybranych parametrów.
- Dobór danych, przygotowanie niezależnych referencji i kryteria porównania
  opisano jako proponowany eksperyment, który wymaga osobnego wykonania.

## Integracja

Notatkę zapisano w bieżącym worktree zgodnie z miejscem prowadzenia rozmowy.
Nie edytowano worktree `NEtCAT-domains`; przeniesienie dokumentacji należy
uzgodnić przez sesję integracyjną. Przegląd nie wymaga zmian wspólnych modułów.
