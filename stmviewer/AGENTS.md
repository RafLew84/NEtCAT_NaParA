# STM Viewer

Zakres tej sesji: `stmviewer/`, `tests/stmviewer/`, `docs/stmviewer/`.
Instrukcja startu i status: [docs/stmviewer/README.md](../docs/stmviewer/README.md).

Przed implementacją odczytaj `docs/stmviewer/map.md` i wskazany w niej ticket,
jeśli użytkownik już je dodał. Gdy mapy brakuje, oprzyj zakres na bieżącym zleceniu;
sam szkielet nie określa kolejności ani szczegółowych funkcji.
Przed realizacją ticketu implementacyjnego przeczytaj
[zasady wykonania i odbioru](../docs/stmviewer/implementation/README.md):
statusy, uzgodnione granice testów, przegląd kodu i wymagania ręcznej próby.

Cel programu: przeglądanie STP/MPP/S94, zapis w tych formatach i rejestracja obrazów.
Istniejące czytniki to `napara/io/`, a algorytmy rejestracji to `nanotrack/registration/`.
Przed użyciem sprawdź ich kontrakt, zależności i testy. Współdzielone zmiany zgłaszaj
sesji integracyjnej zgodnie z głównym AGENTS.md.

Dla zapisu plików kryteria odbioru powinny obejmować wartości, skalę, metadane
i ponowny odczyt, a dla rejestracji również układ współrzędnych i brakujące piksele.
Po zadaniu zaktualizuj status właściwego ticketu oraz `docs/stmviewer/handoff.md`:
wynik, commit, wykonane sprawdzenia, ograniczenia i potrzebne wspólne zmiany.

## Wielkość plików i odbiór kolejnych etapów

- Kod aplikacji i jej testy dziel według odpowiedzialności. Celuj w pliki
  do 1000 linii; każdy nowy lub zmieniany plik kodu może mieć najwyżej
  1500 linii fizycznych, łącznie z komentarzami i pustymi wierszami.
  Przed przekroczeniem limitu wydziel spójny moduł; zachowaj czytelne
  formatowanie. Sprawdź długość zmienionych plików przed zakończeniem ticketu.
- Każdy ticket implementacyjny kończy się uruchamialną aplikacją z funkcją
  możliwą do ręcznego sprawdzenia. Dołącz sposób uruchomienia, dane wejściowe,
  kroki w GUI i oczekiwane wyniki, korzystające wyłącznie z już dostępnych funkcji.
- W przekazaniu każdego ticketu podaj wyniki testów automatycznych oraz
  osobno status prób ręcznych: wykonane i ich wynik albo niewykonane z przyczyną.
  Sprawdzenia Qt offscreen opisuj jako automatyczne, oddzielnie od ręcznego odbioru GUI.
