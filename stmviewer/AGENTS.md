# STM Viewer

Zakres tej sesji: `stmviewer/`, `tests/stmviewer/`, `docs/stmviewer/`.
Instrukcja startu i status: [docs/stmviewer/README.md](../docs/stmviewer/README.md).

Przed implementacją odczytaj `docs/stmviewer/map.md` i wskazany w niej ticket,
jeśli użytkownik już je dodał. Gdy mapy brakuje, oprzyj zakres na bieżącym zleceniu;
sam szkielet nie określa kolejności ani szczegółowych funkcji.

Cel programu: przeglądanie STP/MPP/S94, zapis w tych formatach i rejestracja obrazów.
Istniejące czytniki to `napara/io/`, a algorytmy rejestracji to `nanotrack/registration/`.
Przed użyciem sprawdź ich kontrakt, zależności i testy. Współdzielone zmiany zgłaszaj
sesji integracyjnej zgodnie z głównym AGENTS.md.

Dla zapisu plików kryteria odbioru powinny obejmować wartości, skalę, metadane
i ponowny odczyt, a dla rejestracji również układ współrzędnych i brakujące piksele.
Po zadaniu zaktualizuj własną mapę oraz `docs/stmviewer/handoff.md`: wynik,
commit, wykonane sprawdzenia, ograniczenia i potrzebne wspólne zmiany.
