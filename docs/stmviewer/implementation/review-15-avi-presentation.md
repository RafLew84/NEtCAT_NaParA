# Code review — ticket 15

Data: 2026-10-26. Baza: `d6a08e1a1f2f61b13b83f1ce3deb19ebadb74026`.
Implementacja: `3e1fddf`. Zakres: `git diff d6a08e1...3e1fddf`.
Dwie niezależne osie skilla `code-review`, agenci read-only.

Specyfikacja: [ticket 15](issues/15-avi-presentation.md),
[decyzja AVI](../issues/05-avi-export.md) oraz zasady wykonania i odbioru.
Standardy: AGENTS.md, stmviewer/AGENTS.md, PARALLEL_DEVELOPMENT.md,
implementation/README.md, GLOSSARY.md aplikacji i heurystyki skilla.

## Standards

**0 naruszeń, 0 uwag heurystycznych.** Zmiany pozostają w zakresie Viewera,
bez wspólnych modułów. Podział na renderer, eksport i dialog zachowuje
odpowiedzialności. Pliki kodu mają 30–171 linii, poniżej celu 1000 i limitu 1500.

Testy korzystają z zatwierdzonych granic renderowania, publicznego GUI
oraz rzeczywistego eksportu. Instrukcja manualna zawiera generator, start,
kroki i oczekiwane wyniki; rozróżnia próby automatyczne i akceptację użytkownika.
Terminologia odpowiada słownikowi STM Viewer.

## Spec

**0 ustaleń wymagających poprawy.** Wspólny kontrast obejmuje tylko skończone
próbki wybranych klatek. Gamma ma konwencję podglądu, bez wpływu na tło
0/128/255 i dopełnienie. Stały zakres ma u=0,5, a puste klatki pozostają w filmie.
Domyślne ustawienia są zachowane; rozpoczęta operacja ma niezmienne opcje.
Oba kodeki używają tego samego renderera i dotychczasowych zabezpieczeń zapisu.

Wybór aligned w AVI pozostaje zakresem ticketu 16. Renderer działa również
na gotowych pikselach aligned otwartych z MPP jako wejście bieżącej serii.
Nie znaleziono rozszerzenia zakresu. Finalizację statusu i handoff wykonano
po przeglądzie; recenzenci nie ponawiali testów ani prób VLC/GUI.

Łącznie: Standards — 0 ustaleń; Spec — 0 ustaleń. Bez poprawek kodu po przeglądzie.
