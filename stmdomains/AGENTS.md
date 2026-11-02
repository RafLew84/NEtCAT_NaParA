# STM Domains

Zakres tej sesji: `stmdomains/`, `tests/stmdomains/`, `docs/stmdomains/`.
Instrukcja startu i status: [docs/stmdomains/README.md](../docs/stmdomains/README.md).

Przed implementacją odczytaj `docs/stmdomains/map.md` i wskazany w niej ticket,
jeśli użytkownik już je dodał. Gdy mapy brakuje, oprzyj zakres na bieżącym zleceniu;
sam szkielet nie wybiera algorytmu ani definicji domeny.

Cel programu: wykrywanie i analiza domen pól molekularnych na obrazach STM.
Dotychczasowe algorytmy i testy w `moltrack/analysis/` oraz `tests/moltrack/`
są materiałem do oceny. Wybór metody i wykorzystanie istniejącego rozwiązania
wynikają z nowej mapy, nie z samych statusów dawnego planu MolTrack.

Przy ocenie metod zapisuj identyfikację wejścia, parametry, sposób przygotowania
referencji i mierzalne kryteria jakości. Oddziel sprawdzenie działania programu
od oceny skuteczności detekcji. Duże dane i modele przechowuj poza Git.
Po zadaniu zaktualizuj własną mapę oraz `docs/stmdomains/handoff.md`: wynik,
commit, wykonane sprawdzenia, ograniczenia i potrzebne wspólne zmiany.

Nowy i zmieniany kod aplikacji oraz jej testów dziel według odpowiedzialności:
cel to najwyżej 1000 fizycznych linii na plik, twardy limit 1500 (łącznie
z komentarzami i pustymi liniami). Przed zakończeniem zadania sprawdź długości
zmienionych plików; dla 1001–1500 linii podaj uzasadnienie w przekazaniu.
Zachowuj czytelny format kodu; dane i wygenerowane artefakty nie są kodem aplikacji.
Zadania implementacji UI kończ działającą funkcją oraz instrukcją testu
ręcznego z oczekiwanym wynikiem. Oddziel faktycznie wykonany odbiór GUI
od przygotowanej instrukcji i testów automatycznych.
