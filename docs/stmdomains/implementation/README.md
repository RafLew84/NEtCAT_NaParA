# Budowa i odbiór szkieletu STM Domains

**Rozszerzenie planu — 2026-11-02:** [SD-V4-16–20](interactive-v04/README.md#rozszerzenia)
obejmuje pomiary geometrii, tolerancje domen i próbę freud (`ready-for-agent`
po zależnościach) oraz późniejsze FFT/NMF i katalog typów (`deferred`).
Każdy ticket kończy się funkcją do ręcznego sprawdzenia w aplikacji.

**Nowy podział do uzgodnienia — 2026-11-02:**
[15 ticketów interaktywnego UI v0.4](interactive-v04/README.md), status
`draft`, rozpisuje uruchamialne funkcje z testem ręcznym po każdym zadaniu.
Indeks opisuje zależności i pokrycie historycznych zakresów poniżej.
Dotychczasowe tickety i ich statusy pozostają zachowane.

Specyfikacja: [przekazanie do implementacji](../issues/09-implementation-handoff.md).
Pierwsza mapa decyzji jest zakończona. **Implementacja nie została jeszcze
wykonana; wszystkie poniższe zadania mają status `todo`.**

To zadania wykonawcze, poza rejestrem pytań `wayfinder`. Nie wybierają ponownie
metod ani zakresu. Obowiązują [import](../issues/01-import-and-geometry.md),
[podgląd C](../issues/07-browsing-and-comparison.md) i doprecyzowania przekazania.

| Zadanie | Zależności | Rezultat |
| --- | --- | --- |
| [Import, model serii i geometria](01-import-model.md) | Przyjęta specyfikacja | Zwalidowana seria i poprawny widok danych jednej klatki, bez Qt. |
| [Natywny podgląd i nawigacja](02-browsing-window.md) | Import, model serii i geometria | Działające otwieranie MolTrack i podgląd C w PyQt6. |
| [Odbiór szkieletu](03-acceptance.md) | Oba zadania implementacji | Sprawdzenia automatyczne, pełne dane, GUI i raport ograniczeń. |

Praca obejmuje `stmdomains/`, `tests/stmdomains/` i `docs/stmdomains/` na gałęzi
`domains/*`. Zmiany wspólne i konfiguracja główna trafiają do integratora,
zgodnie z [zasadami współpracy](../../PARALLEL_DEVELOPMENT.md). Każde zadanie
kończy się commitem i aktualizacją [przekazania](../handoff.md).

Statusy wykonawcze: `todo`, `in_progress`, `done`. Rozpoczynając zadanie,
przypisz prowadzącego i ustaw `in_progress`; `done` wymaga spełnienia jego
kryteriów. Nie przenoś wyników sprawdzeń prototypu HTML jako testów natywnej
aplikacji. Raport odbioru wskazuje konkretny commit, środowisko oraz dane.

Kolejność nie blokuje pracy nad niezależnymi testami lub fragmentem UI, ale
odbiór końcowy wymaga spójnego importu i podglądu na tej samej wersji kodu.
Po zakończeniu wszystkich trzech zadań oraz odbiorze przez użytkownika można
kontynuować zwykły tok [drugiej mapy](../map-methods-and-save.md).
Wcześniej rozstrzygnięte pytania o definicje/statystyki/zapis nadal obowiązują.

## Uruchomienie i środowisko

Rozwój może korzystać z lokalnego `netcat`, zgodnie z poleceniem użytkownika.
Z katalogu głównego worktree:

```bash
python -m stmdomains.main
python -m pytest -q tests/stmdomains
```

Testy wymagające Qt na maszynie bez ekranu uruchamia się z
`QT_QPA_PLATFORM=offscreen`. Scenariusze pełnych danych i GUI mają być
uruchamiane jawnie i raportowane oddzielnie. Pusty zbiór testów nie jest sukcesem.
Minimalna ścieżka produkcyjna: PyQt6 + NumPy + SciPy. Dla testów: pytest,
pytest-qt. Środowisko, modele i dane nie trafiają do Git.

Główny `requirements/stm-apps.txt` obsługuje na razie puste okno. Potrzebę
uzupełnienia NumPy/SciPy oraz właściwego zakresu CI przekazuje się integratorowi.
Przed deklaracją instalacji z tego pliku trzeba sprawdzić jego aktualizację.
