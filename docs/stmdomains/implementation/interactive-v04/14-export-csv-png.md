# 14: Wyeksportuj przypisania i widok do CSV oraz PNG

**ID:** SD-V4-14

**What to build:** Użytkownik eksportuje wybraną klatkę lub zakres: czytelne tabele przypisań oraz obrazy zgodne z oglądanym wynikiem.

**Blocked by:** [04: Otwórz wynik v0.4 i zobacz przynależność molekuł](04-open-v04-results.md).

**Status:** draft — podział oczekuje na zatwierdzenie użytkownika.

Obowiązują [wspólne kryteria odbioru](README.md#wspólne-kryteria-odbioru).

## Kryteria akceptacji

- [ ] CSV zachowuje ID molekuł, numery klatek, klasy, konkretne domeny i powody nieprzypisania; zakres i mianowniki są jawne.
- [ ] Podsumowania dotyczą rzeczywiście dostępnych danych. Brak analizy nie staje się zerem, a suma klatek nie udaje liczby śledzonych molekuł.
- [ ] PNG odwzorowuje wybrany tryb Klasy/Domeny, legendę, zakres obrazu i ustawienia widoku. Eksport nie zmienia predykcji.
- [ ] Eksportowane metadane identyfikują wynik, model i faktyczne ustawienia. Powierzchnie przybliżonych masek nie są nazywane zwalidowaną powierzchnią domeny.
- [ ] Błąd zapisu jest czytelny; eksport nie zastępuje samowystarczalnego projektu. Testy porównują eksport z wynikiem i stanem widoku.
- [ ] Działającą funkcję sprawdzono automatycznie i ręcznie zgodnie z zakresem; przekazanie rozróżnia wykonane sprawdzenia od niewykonanych.
- [ ] Sprawdzono długość nowego i zmienianego kodu oraz testów według wspólnej zasady 1000/1500 linii.

## Test ręczny użytkownika

1. Wyeksportuj 259 do PNG i CSV; otwórz pliki poza aplikacją i porównaj kolorowanie, ID, liczniki i szare oznaczenia.
2. Wyeksportuj zakres zawierający klatki z wynikiem, zerowym wynikiem i bez analizy; sprawdź rozróżnienie stanów.
3. Powtórz dla widoku Klasy i Domeny oraz sprawdź zachowanie przy błędnym miejscu zapisu.

## Granice zadania

Eksport można wykonać już na wczytanych wynikach v0.4, bez czekania na nowe modele lub zapis projektu.
