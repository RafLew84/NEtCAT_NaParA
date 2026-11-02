# 04: Otwórz wynik v0.4 i zobacz przynależność molekuł

**ID:** SD-V4-04

**What to build:** Użytkownik otwiera dołączony wynik v0.4 i od razu ogląda molekuły pokolorowane według konkretnych domen. Przełącza widok klas i domen bez uruchamiania obliczeń.

**Blocked by:** [02: Pokaż molekuły i poprawną geometrię obrazu](02-molecules-and-geometry.md).

**Status:** draft — podział oczekuje na zatwierdzenie użytkownika.

Obowiązują [wspólne kryteria odbioru](README.md#wspólne-kryteria-odbioru).

## Kryteria akceptacji

- [ ] Importer wyniku sprawdza źródło, mapę klatek, ID i współrzędne. Niezgodnego wyniku nie nakłada na przypadkowo podobny obraz.
- [ ] Widok Domeny używa końcowego domain_local_id; różne domeny tej samej klasy są rozróżnialne. Nieprzypisane oznaczenia są szare, z dostępną przyczyną.
- [ ] Widok Klasy ma własną legendę i jawnie rozróżnia przypisanie klasy od końcowej domeny. Wstępne etykiety nie udają wyniku końcowego.
- [ ] Legenda i liczniki zgadzają się z zapisanymi przypisaniami. Zero domen, brak analizy oraz pominięty duplikat zachowują odrębne znaczenie.
- [ ] Gotowy wynik obejmuje 56 klatek; poza nimi przeglądarka pokazuje brak wyniku, a nie zero domen. Kolory domen nie sugerują tożsamości między klatkami.
- [ ] Testy odczytu i renderowania sprawdzają mapowanie po ID, zgodność liczników, brak wyniku i sprzeczne wejście.
- [ ] Działającą funkcję sprawdzono automatycznie i ręcznie zgodnie z zakresem; przekazanie rozróżnia wykonane sprawdzenia od niewykonanych.
- [ ] Sprawdzono długość nowego i zmienianego kodu oraz testów według wspólnej zasady 1000/1500 linii.

## Test ręczny użytkownika

1. Otwórz pełną paczkę wyniku v0.4 w aplikacji i obejrzyj klatki 7, 120, 259 i 268.
2. Przełącz Klasy/Domeny; np. różne instancje tej samej klasy muszą być rozróżnialne w widoku Domeny. Sprawdź szare molekuły i przyczynę odmowy.
3. Porównaj klatkę 160 z klatką spoza analizowanych 56: pierwsza ma zapisany zerowy wynik, druga brak analizy. Spróbuj dołączyć niezgodny wynik.

## Granice zadania

Kopia wyników i modeli jest lokalnym zasobem wskazywanym w UI. Kod aplikacji nie zależy od przypadkowego katalogu roboczego agenta.
