# Budowa i odbiór szkieletu STM Domains

**Wykonano SD-V4-03 — 2026-11-02:** miniatury, odtwarzanie bez pomijania
klatek, pauza/restart i gamma. [Uruchomienie i test ręczny](interactive-v04/acceptance-03.md).
300 testów PASS, mypy 27 plików PASS; pełne 268 klatek TTMAPP sprawdzone
w GUI. Ręczny odbiór użytkownika 03 pozostaje do wykonania. Następny ticket
nowego planu: SD-V4-04. Historyczny odbiór całego szkieletu pozostaje otwarty.

**Wykonano SD-V4-02 — 2026-11-02:** działają zapisane oznaczenia, maski,
metadane po kliknięciu i geometria raw/aligned. [Uruchomienie i test ręczny](interactive-v04/acceptance-02.md).
279 testów PASS; ręczny odbiór 02 potwierdzony przez użytkownika (`3572b6d`).
Miniatury, gamma i odtwarzanie dodano następnie w 03.

**Wykonano SD-V4-01 — 2026-11-02:** działa otwieranie zapisów MolTrack/MPP
i przeglądanie obrazów oryginalnych w PyQt6. [Uruchomienie, test ręczny i raport](interactive-v04/acceptance-01.md).
To pierwszy działający przekrój nowego planu; historyczne zadania poniżej
nadal obejmują szerszy zakres oznaczeń, geometrii i pełnego odbioru szkieletu.

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
Pierwsza mapa decyzji jest zakończona. **Poniższe historyczne zadania mają
status `todo`; ich zakres jest wdrażany przez nowy podział SD-V4.**
Aktualne wykonanie 01–03 opisano powyżej; nie oznacza ono odbioru całego szkieletu.

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

Do uruchamiania STM Domains, testów oraz prób używamy istniejącego środowiska
Conda **`netcat`**, zgodnie z [instrukcją aplikacji](../../../stmdomains/AGENTS.md).
Z katalogu głównego worktree, przy aktywnym `netcat`, sprawdź interpreter,
a następnie uruchom potrzebne polecenie:

```bash
python -c 'import sys; print(sys.executable); print(sys.prefix)'
python -m stmdomains.main
python -m pytest -q tests/stmdomains
```

Na tym komputerze zweryfikowano interpreter
`/home/rlew/projekty/conda-migration-ubuntu-20261008/envs/netcat/bin/python`.
Można wywołać go bezpośrednio zamiast `python`, gdy powłoka nie aktywowała
środowiska albo `conda run -n netcat` nie działa w piaskownicy. Przy aktywacji
porównaj `CONDA_PREFIX` z `sys.prefix`; przy bezpośrednim wywołaniu sprawdź,
czy `sys.executable` i `sys.prefix` należą do wskazanego `netcat`.

Testy wymagające Qt na maszynie bez ekranu uruchamia się z
`QT_QPA_PLATFORM=offscreen`. Scenariusze pełnych danych i GUI mają być
uruchamiane jawnie i raportowane oddzielnie. Pusty zbiór testów nie jest sukcesem.
Minimalna ścieżka produkcyjna: PyQt6 + NumPy + SciPy. Dla testów: pytest,
pytest-qt. Środowisko, modele i dane nie trafiają do Git.

Główny `requirements/stm-apps.txt` obsługuje na razie puste okno. Potrzebę
uzupełnienia NumPy/SciPy oraz właściwego zakresu CI przekazuje się integratorowi.
Przed deklaracją instalacji z tego pliku trzeba sprawdzić jego aktualizację.
