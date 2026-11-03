# Przegląd SD-V4-13

Baza `5b2ddc8`; implementacja `4f40c28`, poprawki `1c9c221`.
Dwa niezależne przeglądy skilla `code-review`. Specyfikacja:
[ticket 13](13-save-open-project.md) i [kontrakt projektu](../../issues/08-save-and-export.md).
Zasady: główny `AGENTS.md`, `stmdomains/AGENTS.md`, instrukcje współpracy
oraz wspólne kryteria planu. Nie znaleziono dodatkowych CONTRIBUTING ani
CODING_STANDARDS. Przeglądy dotyczyły kodu i testów; końcową dokumentację
oraz pełną regresję sprawdził agent główny, jak podano w [raporcie](acceptance-13.md).

## Standards

Nie stwierdzono naruszeń udokumentowanych zasad w zmianach
`5b2ddc8...4f40c28`. Zakres pozostaje w aplikacji i jej testach; dane pomiarowe
oraz duże artefakty nie trafiły do commita. Podział na kontener, walidację,
wyniki i obsługę okna jest zgodny z rozdzielaniem odpowiedzialności.
Testy sprawdzają zachowanie publicznych operacji. Nie wskazano zapachu kodu
z listy bazowej uzasadniającego refaktor; `project_view.py` jest adapterem
między kontrolkami i formatem.

Recheck `4f40c28...1c9c221`: 0 nowych ustaleń. Kontrola rastrów ma osobny
moduł i wspólną walidację nagłówka. Test blokujący materializację masek
sprawdza wymagane zachowanie. Normalizacja rozszerzenia pozostaje w dialogu,
przed potwierdzeniem nadpisania; walidacja danych pozostaje na granicy IO.

**0 naruszeń, 0 otwartych sugestii.**

## Spec

Pierwszy przegląd wskazał dwie uwagi P2:

- Pusty `viewport` lub niemapowe `layers` mogły przejść walidację i zgłosić
  wyjątek w slocie Qt po przyjęciu nowej pracy. Kontrakt wymaga odrzucenia
  wadliwego projektu z zachowaniem dotychczasowej pracy. Poprawka sprawdza
  kompletne obecne struktury widoku oraz teksty klas i stanów. Test kontrolera
  potwierdza odrzucenie uszkodzonej paczki przed publikacją.
- Otwieranie materializowało rastry wszystkich wyników kolejno, choć cache
  miał tylko trzy klatki. Kontrakt wymaga odczytu masek na żądanie. Poprawka
  kontroluje nagłówki i ID domen w blokach 1 MiB; do sprawdzenia wejścia używa
  centrów, bez dekodowania segmentacji. Pełny raster powstaje przy pobraniu
  konkretnej klatki. Test blokuje `np.load` i dekodowanie wejściowych masek
  przy otwarciu, potem potwierdza tylko jeden odczyt żądanego wyniku.

Recheck `1c9c221`: obie uwagi zamknięte. Dodatkowo sprawdzono potwierdzenie
nadpisania końcowej nazwy `.stmdomains`; **14 testów ukierunkowanych PASS w netcat**.
Nie stwierdzono rozszerzenia zakresu.

**2 uwagi P2 zamknięte, 0 otwartych uwag.**

Stan końcowy: Standards 0 otwartych ustaleń; Spec 0 otwartych ustaleń.
