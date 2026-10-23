# Przegląd ticketu 10 — Deep Matcher z lokalnymi wagami

Data: 2026-10-23. Baza zgodnie z zasadami implementacji:
`d899ea0648af2ab507b41fc24d2c2bdcf5c356c2`. Implementacja: `30ddddf`.
Diff: `git diff d899ea0648af2ab507b41fc24d2c2bdcf5c356c2...30ddddf`.

Dwie osie sprawdzili równolegle niezależni agenci zgodnie ze skillem
`code-review`, tylko do odczytu i bez uruchamiania testów. Końcowe statusy,
wyniki testów i przekazanie uzupełniono po przeglądzie; kod się nie zmienił.

## Standards

Nie znaleziono naruszeń udokumentowanych reguł ani istotnych problemów
z katalogu heurystyk Fowlera.

Zmiany pozostają w zakresie Viewera, bez modyfikacji wspólnych backendów
lub konfiguracji głównej. Model i kontrolki mają osobne moduły zgodnie
z podziałem odpowiedzialności w instrukcjach aplikacji. Dokumentacja
rozdziela testy kontrolowane, rzeczywisty model/CUDA, automatyczne GUI
oraz niewykonany odbiór manualny i Windows.

Normalizacja w lokalnym adapterze powtarza fragment prywatnego adaptera
NanoTrack. Jest to uzasadnione zachowaniem algorytmu oraz możliwością
wczytania lokalnych wag bez pobierania i bez zmiany modułu wspólnego.
Refaktoryzacja wspólnego kodu nie jest wymagana w tym tickecie.

Źródła: `AGENTS.md`, `stmviewer/AGENTS.md`, `docs/PARALLEL_DEVELOPMENT.md`,
indeks implementacji, słownik i katalog heurystyk Fowlera ze skillu.
Nie znaleziono odrębnych CODING_STANDARDS/CONTRIBUTING.

**Standards: 0 naruszeń, 0 zgłoszonych heurystyk.**

## Spec

Implementacja spełnia zakres ticketu 10. Lokalny odczyt wag
z `LoFTR(pretrained=None)` zapewnia brak automatycznego pobierania.
Jawne CPU/CUDA/Auto, próba wykonania na CUDA i opis urządzenia wyniku
realizują wymaganie informacji o faktycznym urządzeniu; awaria CUDA
nie uruchamia zastępczego wykonania na CPU.

Ładowanie i obliczenia działają w workerze, zachowując kontrakt anulowania
oraz publikacji kompletnego aligned. Adapter zachowuje normalizację
obrazów i domyślne kryteria konsensusu NanoTrack. Nie zmienia wspólnego
kodu ani zakresu algorytmu.

Testy rozdzielają kontrolowany model od rzeczywistych wag. Instrukcja
opisuje przygotowanie zależności, brak wag, nieprawidłowy checkpoint,
urządzenia i zachowanie poprzedniego wyniku. Nie znaleziono brakującego
wymagania, rozszerzenia zakresu ani defektu implementacji. Windows
i odbiór manualny są jawnie oznaczone jako niewykonane; pełny odbiór
platform należy do późniejszych ticketów.

Źródła: [ticket 10](issues/10-deep-matcher.md),
[decyzja 03](../issues/03-registration.md#answer),
[decyzja 06](../issues/06-acceptance.md#answer), [słownik](../GLOSSARY.md)
i zasady odbioru w indeksie implementacji.

**Spec: 0 ustaleń.**

Wyniki testów i status ręcznego odbioru: [przekazanie](../handoff.md).
