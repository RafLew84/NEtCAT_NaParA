# NEtCAT — praca nad aplikacjami

Zachowuj aplikacje w osobnych katalogach głównych repozytorium. Nowe programy
to `stmviewer` i `stmdomains`; ich zakres określają mapy dostarczone przez użytkownika.

- Na początku sesji sprawdź `git branch --show-current`, `git status --short`
  i `git worktree list`, aby ustalić swój katalog oraz rolę.
- `stm-next` jest gałęzią integracyjną, obsługiwaną przez nadrzędną sesję użytkownika.
  Sesja ta koordynuje wspólny kod i scala gotowe zadania.
- Gałęzie `viewer/*`: przed pracą nad `stmviewer/`, jego testami lub dokumentacją
  przeczytaj [stmviewer/AGENTS.md](stmviewer/AGENTS.md).
- Gałęzie `domains/*`: przed pracą nad `stmdomains/`, jego testami lub dokumentacją
  przeczytaj [stmdomains/AGENTS.md](stmdomains/AGENTS.md).
- Te same instrukcje aplikacji obowiązują podczas jej zmian na gałęzi integracyjnej.
- Przy przygotowaniu środowiska, pracy między gałęziami lub przekazaniu zadania
  użyj [instrukcji współpracy](docs/PARALLEL_DEVELOPMENT.md).
- Kod w `napara/`, `nanotrack/`, `moltrack/` i `stmbrowser/` pozostaje bazą istniejących
  aplikacji. Zmiany współdzielonych modułów oraz konfiguracji głównej prowadź w sesji
  integracyjnej. W sesji aplikacji opisz potrzebną zmianę w jej `handoff.md`
  i kontynuuj niezależne prace.
- Pliki robocze edytuj w worktree przypisanym do tej sesji. Aktualizacje innych
  worktree przenoś commitami i scalaniem po zakończeniu ich bieżących prac.
- Nowe mapy, decyzje i tickety przechowuj w `docs/stmviewer/` lub `docs/stmdomains/`
  i wersjonuj w Git. Dane pomiarowe, modele, środowiska i duże wyniki pozostają lokalne.
- Zakres testów dobieraj do zmiany; zmiana wspólnego modułu obejmuje jego odbiorców.
  W przekazaniu rozróżnij wykonane testy od sprawdzeń wymagających danych lub GUI.
