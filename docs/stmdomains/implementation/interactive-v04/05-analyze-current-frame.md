# 05: Oblicz domeny na bieżącej klatce

**ID:** SD-V4-05

**What to build:** Użytkownik wczytuje wspólny model v0.4, klika Analizuj klatkę i ogląda świeżo obliczony wynik przy ustawieniach bazowych. Działa postęp i anulowanie.

**Blocked by:** [04: Otwórz wynik v0.4 i zobacz przynależność molekuł](04-open-v04-results.md).

**Status:** draft — podział oczekuje na zatwierdzenie użytkownika.

Obowiązują [wspólne kryteria odbioru](README.md#wspólne-kryteria-odbioru).

## Kryteria akceptacji

- [ ] Obliczenia korzystają z bieżącego obrazu i oznaczeń oraz jawnie wybranego modelu. Nie kopiują gotowych etykiet wyniku zamiast wykonywać analizy.
- [ ] Wydzielono potrzebne operacje v0.4 z uruchamiania skryptów; model, dane i katalog wyniku są jawne. Nie wykonuje się niepotrzebnie całego historycznego pipeline'u.
- [ ] Domyślne ustawienia odtwarzają zapisany punkt odniesienia na klatkach 7, 120, 259 i 268; porównanie opiera się na członkostwie domen, nie samych numerach etykiet.
- [ ] Obliczenia działają poza GUI. Błąd, anulowanie, przejście do innej klatki lub otwarcie nowej serii nie podmieniają widoku spóźnionym wynikiem.
- [ ] Brak oznaczeń albo niewystarczające wsparcie daje jawny wynik/odmowę. Ustawienia, zakres, identyfikacja modelu i źródła są związane z obliczonym wynikiem.
- [ ] Testy obejmują rzeczywistą ścieżkę obliczeń, zgodność punktów i domen, anulowanie oraz powrót do poprzedniego poprawnego wyniku.
- [ ] Działającą funkcję sprawdzono automatycznie i ręcznie zgodnie z zakresem; przekazanie rozróżnia wykonane sprawdzenia od niewykonanych.
- [ ] Sprawdzono długość nowego i zmienianego kodu oraz testów według wspólnej zasady 1000/1500 linii.

## Test ręczny użytkownika

1. Otwórz dane i model v0.4, wybierz 259, kliknij Analizuj klatkę; zobacz nowy wynik i jego ustawienia.
2. Przelicz te same ustawienia ponownie oraz klatkę 268; sprawdź powtarzalność i zgodność z zapisanym punktem odniesienia.
3. Uruchom i anuluj analizę lub zmień serię w trakcie; poprzedni poprawny wynik pozostaje dostępny. Klatka bez oznaczeń nie powoduje awarii.

## Granice zadania

Model klas pozostaje zamrożony. To pierwszy działający przekrój obliczeń, a nie osobny refaktor backendu.
