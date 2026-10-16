# Jak przekazać szkielet do implementacji i go odebrać?

ID: 09
Type: grilling
Labels: wayfinder:grilling
Mode: HITL
Status: open
Assignee:
Parent: [STM Domains — etap 1: działający szkielet](../map.md)
Blocked by: 01, 07

## Question

Czy ustalony import i podstawowy podgląd wystarczają, aby rozpisać i zbudować
działający szkielet na rzeczywistym zapisie MolTrack?

Ustalmy lokalne moduły importu, modelu serii i widoku oraz zakres użycia
istniejących czytników, geometrii i widgetów. Wskażmy potrzebne zmiany wspólne
do sesji integracyjnej. Pozostawmy prosty punkt do późniejszego podłączenia
analizy, bez projektowania teraz ogólnego systemu metod lub schematu wyników.

Kryteria odbioru mają obejmować otwarcie rzeczywistego zapisu, odnalezienie
obrazów po poprawieniu ścieżki, nawigację, zoom/gamma oraz sprawdzenie zgodności
oznaczeń w original/aligned. Uwzględnijmy serię jednoklatkową, brak danych
i wyraźne oddzielenie dopełnienia od pola pomiarowego. Określmy osobno testy
automatyczne geometrii/importu oraz kontrolę wymagającą lokalnych danych i GUI.

Rozstrzygnięcie przekazuje zakres i kryteria do zadań implementacyjnych etapu 1.
Po ich wykonaniu i odbiorze można rozpocząć drugą mapę. Wybór metody detekcji,
walidacja naukowa, statystyki i zapis wyników nie są warunkami gotowości szkieletu.
Zamknięcie tego ticketu oznacza gotowość specyfikacji, nie wykonanie programu.

## Dependencies

- [Jak zapis wejściowy odtwarza obrazy, oznaczenia i rejestrację?](01-import-and-geometry.md)
- [Jak przeglądać obrazy i oznaczenia w szkielecie?](07-browsing-and-comparison.md)

## Comments

### 2026-10-16 — podział zakresu zatwierdzony przez użytkownika

Usunięto zależność przekazania szkieletu od wyboru metod, referencji jakości
i eksportu. Pytania o koszt analizy, jej anulowanie i ponowne użycie wyników
pozostają częścią [Jak porównać metody wykrywania wysp i domen w serii?](05-stable-types-across-frames.md)
i [Co zapisujemy i eksportujemy po próbach metod?](08-save-and-export.md) w drugim etapie.

Kontekst: [instrukcje współpracy](../../PARALLEL_DEVELOPMENT.md).
