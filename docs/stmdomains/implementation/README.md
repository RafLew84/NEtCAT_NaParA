# Budowa i odbiór szkieletu STM Domains

**Wykonano SD-V4-08 — 2026-11-03 (`1c39ae2`, poprawka `46c274f`):**
menu **Analiza → Analiza serii…**, wspólne klasy i ustawienia domen,
wynik każdej klatki, postęp/statusy i anulowanie zachowujące ukończone
wyniki. [Raport i test ręczny](interactive-v04/acceptance-08.md).
409 testów PASS, mypy 59 modułów PASS; rzeczywiste GUI sprawdzone także
na całych 268 klatkach TTMAPP. **Odbiór ręczny użytkownika 08 oczekuje.**
Następny rekomendowany ticket **12 — Auto**.

**Wykonano SD-V4-07 — 2026-11-02 (`dedd8b8`, poprawki `65e9d2a`):**
**Analiza → Klasy i zakres…**, ręczne K1–8, zakres dopasowania i wspólny
katalog. Przelicza bieżącą klatkę; poprzednie wyniki zachowują własny katalog.
[Raport i test ręczny](interactive-v04/acceptance-07.md). 396 testów PASS,
mypy 54 moduły PASS, GUI X11 sprawdzone przez agenta.
**Ręczny odbiór użytkownika 07 potwierdzony 2026-11-02** dla wersji
`7f79362` („testy manualne ok”). Kolejny etap 08 opisano powyżej.

**Wykonano SD-V4-06 — 2026-11-02 (`98ca8ff`, poprawka `36aea1f`):**
parametry domen w menu **Analiza → Tworzenie domen…**, przeliczenie,
porównanie i przywracanie bazowych ustawień bez ponownego dopasowania klas.
[Raport i test ręczny](interactive-v04/acceptance-06.md). Odbiór ręczny
użytkownika potwierdzony 2026-11-02 dla wersji `a4dcace`
(„testy manualne ok”). Kolejny etap 07 opisano powyżej.

**Wykonano SD-V4-05a — 2026-11-02 (`dfcf392`):** wypełnienie, obrysy,
numery domen i krycie w menu **Obszary…**; centra i ramki można wyłączyć.
Dotychczasowe „Maski / obrysy” nazwano **Maski molekuł**, zgodnie ze źródłem
MolTrack. [Raport i test ręczny](interactive-v04/acceptance-05a.md).
Przypisania i metoda 05 są zachowane. Ręczny odbiór 05a potwierdzony przez
użytkownika 2026-11-02 dla wersji `617b006`.

**Wykonano SD-V4-05 — 2026-11-02 (`fb37431`):** **Analizuj klatkę · K5**
oblicza lokalne klasy i końcowe domeny z bieżącego obrazu MPP i oznaczeń
MolTrack, z kolorami, legendą, odmowami, postępem i anulowaniem.
[Uruchomienie, sprawdzenia i test ręczny](interactive-v04/acceptance-05.md).
Ręczny odbiór użytkownika 05 oczekuje. Aktualny plan ma 19 ticketów:
01–03, 05, 05a, 06, 07 i 08 `done`,
09–10 oraz 12–18 `ready-for-agent` po zależnościach, 19–20 `deferred`.

**Wcześniejsza zmiana kierunku — 2026-11-02:** na polecenie użytkownika wycofano
SD-V4-04 i import jego wyników. Stan aplikacji wrócił wtedy do odebranego 03,
z zachowaniem poprawek układu i wyjścia. **308 testów PASS**, mypy 27 plików
PASS. [Zmieniony plan](interactive-v04/README.md) prowadzi do własnych
obliczeń na wzór metody v0.4, bez ładowania zewnętrznych modeli/wyników.
Ręczne K i zakres dodaje 07, serię 08, Auto 12. Dawny 11 wchłonięto
w 05/07. Obliczenia jednej klatki wdrożono w 05, zgodnie z aktualizacją
powyżej. Poniżej historia poprzednich etapów.

**Wykonano SD-V4-03 — 2026-11-02:** miniatury, odtwarzanie bez pomijania
klatek, pauza/restart i gamma. [Uruchomienie i test ręczny](interactive-v04/acceptance-03.md).
300 testów PASS, mypy 27 plików PASS; pełne 268 klatek TTMAPP sprawdzone
w GUI. Ręczny odbiór 03 wraz z poprawką układu `0745e4e` potwierdzono;
późniejsza [poprawka wyjścia](interactive-v04/acceptance-03.md#poprawka-wyjścia-z-programu)
`3dd8b47` również odebrana ręcznie 2026-11-02. Historyczny odbiór całego
szkieletu pozostaje otwarty; aktualną kolejność nowego planu podano powyżej.

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
Aktualne wykonanie 01–03 i 05 opisano powyżej; nie oznacza ono odbioru całego szkieletu.

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
Minimalna ścieżka produkcyjna: PyQt6 + NumPy + SciPy + scikit-learn +
threadpoolctl. Dla testów: pytest, pytest-qt. Wszystkie te pakiety są
dostępne w istniejącym `netcat`. Środowisko, modele i dane nie trafiają do Git.

Główny `requirements/stm-apps.txt` obsługuje na razie puste okno. Potrzebę
uzupełnienia NumPy/SciPy, scikit-learn/threadpoolctl oraz właściwego zakresu
CI przekazuje się integratorowi.
Przed deklaracją instalacji z tego pliku trzeba sprawdzić jego aktualizację.
