# 08: Przelicz zakres lub całą serię

**ID:** SD-V4-08

**What to build:** Użytkownik wybiera wspólny model, zakres klatek lub całą serię, uruchamia analizę i przegląda wyniki przy zachowaniu wspólnych klas.

**Blocked by:** [05: Oblicz domeny na bieżącej klatce](05-analyze-current-frame.md).

**Status:** draft — podział oczekuje na zatwierdzenie użytkownika.

Obowiązują [wspólne kryteria odbioru](README.md#wspólne-kryteria-odbioru).

## Kryteria akceptacji

- [ ] Ta sama konfiguracja i wersja modelu są stosowane do wybranego zakresu, bez dopasowywania osobnego modelu dla każdej klatki.
- [ ] UI pokazuje postęp oraz status każdej klatki. Klasy mają wspólny słownik, a domeny lokalne identyfikatory.
- [ ] Anulowanie zachowuje ukończone klatki jako wynik częściowy. Niewykonane klatki pozostają bez wyniku; błąd jednej klatki jest jawny.
- [ ] Nawigacja podczas pracy nie miesza obrazu i wyniku. Pamięć/cache nie rosną bez ograniczenia przy kolejnych przejściach.
- [ ] Wynik klatki obliczonej w serii jest zgodny z analizą tej samej klatki osobno dla tych samych danych, modelu i ustawień.
- [ ] Testy obejmują zakres, puste klatki, anulowanie, błąd i porównanie batch/pojedyncza klatka.
- [ ] Działającą funkcję sprawdzono automatycznie i ręcznie zgodnie z zakresem; przekazanie rozróżnia wykonane sprawdzenia od niewykonanych.
- [ ] Sprawdzono długość nowego i zmienianego kodu oraz testów według wspólnej zasady 1000/1500 linii.

## Test ręczny użytkownika

1. Z modelem v0.4 przeanalizuj 259–268 i przejdź po wszystkich wynikach; porównaj 259 z analizą pojedynczą.
2. Uruchom większy zakres i anuluj; ukończone klatki pozostają dostępne, a reszta jest oznaczona jako niewykonana.
3. Przeanalizuj serię z odcinkiem bez oznaczeń i nawiguj w trakcie pracy; nie powinno być awarii ani nakładania wyniku innej klatki.

## Granice zadania

Model może być wczytany z paczki; ticket nie jest blokowany przez odkrywanie nowych klas.
