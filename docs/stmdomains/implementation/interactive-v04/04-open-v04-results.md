# 04: Otwórz wynik v0.4 i zobacz przynależność molekuł

**ID:** SD-V4-04

**What to build:** Użytkownik otwiera dołączony wynik v0.4 i od razu ogląda molekuły pokolorowane według konkretnych domen. Przełącza widok klas i domen bez uruchamiania obliczeń.

**Blocked by:** [02: Pokaż molekuły i poprawną geometrię obrazu](02-molecules-and-geometry.md).

**Status:** done — implementacja i sprawdzenia agenta zakończone;
**ręczny odbiór użytkownika pozostaje do wykonania**.
[Uruchomienie, dokładny test ręczny i raport](acceptance-04.md).

Baza implementacji i przeglądu: `24625f2`, gałąź `domains/interactive-v04-ui`.
Środowisko: `netcat`. Publiczne granice testów wynikające z kryteriów ticketu:
import kompletnej paczki względem otwartej serii (pochodzenie, mapy, ID,
współrzędne i liczniki) oraz pełna ścieżka import–podgląd (kolory, legenda,
przyczyna odmowy, brak wyniku i zero domen). Wstępne etykiety klas pozostają
diagnostyką; widok Klasy używa końcowych przypisań `class_id`.

Obowiązują [wspólne kryteria odbioru](README.md#wspólne-kryteria-odbioru).

## Kryteria akceptacji

- [x] Importer wyniku sprawdza źródło, mapę klatek, ID i współrzędne. Niezgodnego wyniku nie nakłada na przypadkowo podobny obraz.
- [x] Widok Domeny używa końcowego domain_local_id; różne domeny tej samej klasy są rozróżnialne. Nieprzypisane oznaczenia są szare, z dostępną przyczyną.
- [x] Widok Klasy ma własną legendę i jawnie rozróżnia przypisanie klasy od końcowej domeny. Wstępne etykiety nie udają wyniku końcowego.
- [x] Legenda i liczniki zgadzają się z zapisanymi przypisaniami. Zero domen, brak analizy oraz pominięty duplikat zachowują odrębne znaczenie.
- [x] Gotowy wynik obejmuje 56 klatek; poza nimi przeglądarka pokazuje brak wyniku, a nie zero domen. Kolory domen nie sugerują tożsamości między klatkami.
- [x] Testy odczytu i renderowania sprawdzają mapowanie po ID, zgodność liczników, brak wyniku i sprzeczne wejście.
- [x] Działającą funkcję sprawdzono automatycznie i w rzeczywistym GUI; przekazanie rozróżnia test agenta od niewykonanego odbioru użytkownika.
- [x] Sprawdzono długość nowego i zmienianego kodu oraz testów według wspólnej zasady 1000/1500 linii.

## Test ręczny użytkownika

1. Otwórz zapis MolTrack TTMAPP, potem przyciskiem **Otwórz wynik v0.4…** pełny ZIP lub manifest paczki; obejrzyj klatki 7, 120, 259 i 268.
2. Przełącz Klasy/Domeny; np. różne instancje tej samej klasy muszą być rozróżnialne w widoku Domeny. Sprawdź szare molekuły i przyczynę odmowy.
3. Porównaj klatkę 160 z klatką spoza analizowanych 56: pierwsza ma zapisany zerowy wynik, druga brak analizy. Spróbuj dołączyć niezgodny wynik.

## Granice zadania

Kopia wyników i modeli jest lokalnym zasobem wskazywanym w UI. Kod aplikacji nie zależy od przypadkowego katalogu roboczego agenta.
