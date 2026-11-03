# 14: Wyeksportuj przypisania i widok do CSV oraz PNG

**ID:** SD-V4-14

**What to build:** Użytkownik eksportuje wynik obliczony w aplikacji dla wybranej klatki lub dostępnych wyników zakresu: czytelne tabele przypisań oraz obrazy zgodne z oglądanym wynikiem.

**Blocked by:** [05: Oblicz klasy i domeny bieżącej klatki z danych](05-analyze-current-frame.md).

**Status:** done — implementacja `a20e14b`, poprawka `361a7d0`; testy i natywne GUI sprawdzone przez agenta. Odbiór ręczny użytkownika do wykonania. [Raport i instrukcja](acceptance-14.md), [format eksportu](export-format-v1.md), [przegląd](review-14.md).

Obowiązują [wspólne kryteria odbioru](README.md#wspólne-kryteria-odbioru).

## Kryteria akceptacji

- [x] CSV zachowuje ID molekuł, numery klatek, klasy, konkretne domeny i powody nieprzypisania; zakres i mianowniki są jawne.
- [x] Podsumowania dotyczą rzeczywiście dostępnych danych. Brak analizy nie staje się zerem, a suma klatek nie udaje liczby śledzonych molekuł.
- [x] Eksport zakresu korzysta wyłącznie z dostępnych wyników aplikacji, z jawnymi statusami pozostałych klatek. Nie uruchamia dopasowania/analizy ani nie doczytuje wyników v0.4. Można go sprawdzić na zakresie z pojedynczą obliczoną klatką, bez zależności od wykonania analizy serii w 08.
- [x] PNG odwzorowuje wybrany tryb Klasy/Domeny, legendę, zakres obrazu i ustawienia widoku. Eksport nie zmienia predykcji.
- [x] Eksportowane metadane identyfikują wynik, model i faktyczne ustawienia. Powierzchnie przybliżonych masek nie są nazywane zwalidowaną powierzchnią domeny.
- [x] Błąd zapisu jest czytelny; eksport nie zastępuje samowystarczalnego projektu. Testy porównują eksport z wynikiem i stanem widoku.
- [x] Działającą funkcję sprawdzono automatycznie i ręcznie zgodnie z zakresem; przekazanie rozróżnia wykonane sprawdzenia od niewykonanych.
- [x] Sprawdzono długość nowego i zmienianego kodu oraz testów według wspólnej zasady 1000/1500 linii.

## Test ręczny użytkownika

1. Otwórz MPP/JSON i oblicz klatkę 259 metodą bazową aplikacji. Wyeksportuj ją do PNG i CSV; otwórz pliki poza aplikacją i porównaj kolorowanie, ID, liczniki i szare oznaczenia.
2. Wyeksportuj zakres 259–260 po obliczeniu tylko 259; 260 ma pozostać bez analizy. Osobno oblicz i wyeksportuj dostarczony przykład zerowego wyniku; jego stan musi różnić się od braku analizy.
3. Powtórz dla widoku Klasy i Domeny oraz sprawdź zachowanie przy błędnym miejscu zapisu.

## Granice zadania

Eksport dotyczy wyników obliczonych przez STM Domains. Nie wymaga importu v0.4, zapisania projektu ani ukończenia analizy całej serii. Działanie metody i trafność domen mają odrębny odbiór.

Eksport ręcznych korekt 21–23 dodaje osobno [25](25-export-manual-corrections.md),
bez blokowania podstawowego eksportera 14. Jeśli edycja jest już dostępna,
UI nie może przedstawiać bazowego automatu jako eksportu poprawionego widoku;
obowiązują [zasady edycji ręcznej](README.md#edycja-ręczna-klas-i-domen).
