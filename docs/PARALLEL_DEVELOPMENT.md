# Praca równoległa nad STM Viewer i STM Domains

## Role

| Katalog obok siebie | Gałąź początkowa | Rola |
| --- | --- | --- |
| `NEtCAT_NaParA` | `stm-next` | Nadrzędna sesja: wspólny kod, przygotowanie repo i integracja |
| `NEtCAT-viewer` | `viewer/start` | STM Viewer, jego testy i dokumentacja |
| `NEtCAT-domains` | `domains/start` | STM Domains, jego testy i dokumentacja |

Każdy worktree zawiera całe repozytorium i ma osobne pliki robocze. Układ
aplikacji pozostaje taki sam. Gałęzie aplikacji są gałęziami zadań; ukończone
zmiany trafiają regularnie do `stm-next`.

Sesje w osobnych oknach nie otrzymują automatycznie treści innych rozmów.
Wspólny kontekst stanowią instrukcje, mapy, commity i pliki przekazania.
Użytkownik zgłasza w nadrzędnym czacie, która gałąź jest gotowa do integracji.

## Otwarcie okien

```bash
code -n /home/rlew/projekty/NEtCAT-viewer
code -n /home/rlew/projekty/NEtCAT-domains
```

W każdym oknie rozpocznij nową sesję Codexa. Przykładowe pierwsze polecenie:

> Pracujemy nad STM Viewer. Przeczytaj AGENTS.md, stmviewer/AGENTS.md oraz
> docs/stmviewer/README.md. Ten worktree jest przeznaczony dla przeglądarki.
> Za chwilę dodam mapę; na razie sprawdź środowisko i potwierdź gałąź.

Dla drugiego programu użyj `STM Domains`, `stmdomains/AGENTS.md`
i `docs/stmdomains/README.md`.

## Środowisko

Instrukcja utworzenia `.venv` znajduje się w [README](../README.md).
Środowiska nie są kopiowane przez Git. Na przygotowanym komputerze każde z trzech
worktree ma własne `.venv`; w nowym checkoutcie trzeba je utworzyć ponownie.
W VS Code wybierz interpreter z katalogu bieżącego worktree.

Jeśli systemowy Python nie ma `ensurepip`, można utworzyć środowisko poleceniem
`python3.12 -m venv --without-pip .venv`, a następnie użyć innego Pythona
z pip: `python -m pip --python .venv install pip -r requirements/stm-apps.txt`.
To instaluje pakiety w docelowym `.venv`.

## Mapy i przekazanie

Mapę Viewer dodaj jako `docs/stmviewer/map.md`, a mapę Domains jako
`docs/stmdomains/map.md`. Powiązane zadania umieszczaj w odpowiednim `issues/`.
Mapy należą do Git; `.scratch/` służy lokalnym artefaktom i nie przenosi się
automatycznie między worktree.

Po zadaniu zapisz commit oraz `docs/<aplikacja>/handoff.md` zawierający:

- wykonany zakres i identyfikator zadania z mapy;
- commit albo zakres commitów do scalenia;
- uruchomione testy i sposób odbioru w GUI;
- ograniczenia, nierozwiązane kwestie i potrzebne wspólne zmiany.

Identyfikator commita z plikiem przekazania można podać w końcowej wiadomości;
sam plik może wskazywać wcześniejszy commit implementacji.

## Integracja

Koordynator odczytuje zmiany i przekazanie z gotowej gałęzi, wykonuje właściwe
sprawdzenia i scala ją na `stm-next`. Przykładowo, z głównego katalogu:

```bash
git log --oneline stm-next..viewer/start
git diff stm-next...viewer/start
git merge viewer/start
```

Scalaj zadania kolejno, sprawdzając wynik po każdym. Jeżeli zmienił się wspólny
moduł, sprawdzenie obejmuje wszystkie aplikacje, które z niego korzystają.
Gałąź integracyjna jest jedynym miejscem prowadzenia wspólnych zmian; sesje
aplikacji opisują ich potrzebny zakres w swoim przekazaniu.

Gdy agent zakończy bieżącą operację i zapisze swoje zmiany, może pobrać nowy stan:

```bash
# W katalogu własnego worktree, na jego gałęzi:
git merge stm-next
```

Nadrzędna sesja nie aktualizuje plików drugiego worktree podczas pracy jego agenta.
Lokalne scalanie nie publikuje zmian na GitHub; publikacja jest osobnym działaniem.
