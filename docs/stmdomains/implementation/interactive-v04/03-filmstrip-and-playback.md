# 03: Przeglądaj serię przez miniatury i odtwarzanie

**ID:** SD-V4-03

**What to build:** Użytkownik przewija serię przez pasek miniatur i odtwarza kolejne klatki. Może dostosować gamma i zatrzymać obraz do inspekcji.

**Blocked by:** [01: Otwórz zapis i przeglądaj obrazy](01-open-images.md).

**Status:** draft — podział oczekuje na zatwierdzenie użytkownika.

Obowiązują [wspólne kryteria odbioru](README.md#wspólne-kryteria-odbioru).

## Kryteria akceptacji

- [ ] Pasek miniatur, suwak i numer wskazują tę samą klatkę. Działają play/pauza, od początku i szybkości przyjęte w kontrakcie podglądu.
- [ ] Przy wolnym przygotowaniu odtwarzanie zwalnia, zachowując kolejność. Pauza nie powoduje późniejszego dodatkowego kroku; koniec zatrzymuje odtwarzanie.
- [ ] Kontrast jest ustalany na oryginalnej klatce i wspólny dla jej widoków. Gamma, zoom i warstwy są zachowywane podczas nawigacji zgodnie z kontraktem.
- [ ] Miniatury i cache mają ograniczony koszt; stale spóźnione żądania nie mieszają klatek. Po dołączeniu oznaczeń i wyników są publikowane razem z obrazem.
- [ ] Testy obejmują pauzę, koniec, opóźnione przygotowanie, pojedynczą klatkę i niepoprawne próbki obrazu.
- [ ] Działającą funkcję sprawdzono automatycznie i ręcznie zgodnie z zakresem; przekazanie rozróżnia wykonane sprawdzenia od niewykonanych.
- [ ] Sprawdzono długość nowego i zmienianego kodu oraz testów według wspólnej zasady 1000/1500 linii.

## Test ręczny użytkownika

1. Przejdź do wybranej klatki miniaturą, suwakiem i numerem; za każdym razem sprawdź zgodność wskazań.
2. Uruchom odtwarzanie wolno i szybko, zatrzymaj oraz wznów; nie może wystąpić dodatkowy krok po pauzie ani przeskok przy przeciążeniu.
3. Zmień gamma, powiększenie i rozmiar okna, potem otwórz serię jednej klatki; widok pozostaje czytelny, a zbędne sterowanie jest wyłączone.

## Granice zadania

Ten ticket może powstać niezależnie od oznaczeń i analizy. Nie dodaje śledzenia obiektów w czasie.
