# Podgląd, gamma i odtwarzanie serii

Type: prototype
Label: wayfinder:prototype
Status: open
Assignee: none
Parent: [STM Viewer — mapa pierwszej wersji](../map.md)
Blocked by: 01

Zależy od: [Seria wejściowa i usuwanie klatek](01-frame-series.md).

## Question

Jaki prosty układ okna i zachowanie podglądu pozwolą wygodnie przeglądać serię,
regulować gamma, przybliżać oraz odtwarzać i zatrzymywać klatki?

Prototyp ma pomóc uzgodnić listę/suwak klatek, jeden lub więcej obszarów
podglądu, zachowanie zoomu i gamma przy zmianie klatki i original/aligned,
prędkość odtwarzania, koniec serii (stop/pętla), ręczną nawigację podczas Play
oraz wygląd brakujących pikseli po rejestracji. Użytkownik ocenia prototyp;
nie jest on implementacją produkcyjną.

## Comments

### 2026-10-14 — wymagania użytkownika

Punktem odniesienia jest NanoTrack. Potrzebne są zoom, kontrola gamma,
przycisk Play, wybór prędkości i zatrzymanie na klatce. Widok aligned zastępuje
original w podglądzie, z możliwością przełączenia. Gotowy widget zapewnia zoom
i gamma, lecz nie odtwarzanie. Zobacz [rozpoznanie](../reconnaissance.md).
