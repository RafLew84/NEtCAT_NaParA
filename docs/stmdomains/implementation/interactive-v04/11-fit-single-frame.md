# 11: Odkryj klasy wyłącznie na jednej klatce

**ID:** SD-V4-11

**What to build:** Użytkownik wybiera Odkryj klasy na tej klatce i otrzymuje model oraz domeny wyznaczone wyłącznie z bieżącego obrazu i jego oznaczeń.

**Blocked by:** [07: Odkryj wspólne klasy z ręcznie podanym K](07-fit-shared-classes.md).

**Status:** draft — podział oczekuje na zatwierdzenie użytkownika.

Obowiązują [wspólne kryteria odbioru](README.md#wspólne-kryteria-odbioru).

## Kryteria akceptacji

- [ ] Dopasowanie nie wymaga modelu serii, pierwszych dziesięciu klatek ani ich ukrytego dołączenia.
- [ ] Ręczne K, skala, liczba użytecznych próbek i rozmiar PCA są sprawdzane dla bieżącej klatki. K1 i niewystarczające dane są obsługiwane.
- [ ] Model jest opisany jako lokalny dla klatki. Przejście na inną klatkę nie udaje wspólnego słownika ani automatycznie nie dopasowuje nowego.
- [ ] Użytkownik może wrócić do wspólnego modelu serii i wcześniejszego wyniku bez nadpisania ich.
- [ ] Testy wykazują, że zmiana niewybranych klatek nie wpływa na dopasowanie jednej klatki.
- [ ] Działającą funkcję sprawdzono automatycznie i ręcznie zgodnie z zakresem; przekazanie rozróżnia wykonane sprawdzenia od niewykonanych.
- [ ] Sprawdzono długość nowego i zmienianego kodu oraz testów według wspólnej zasady 1000/1500 linii.

## Test ręczny użytkownika

1. Otwórz serię i wybierz tylko klatkę 259, ustaw K oraz Odkryj klasy na tej klatce.
2. Przejdź do 268; program zachowuje jawny zakres modelu zamiast sugerować, że klasy mają wspólne znaczenie w serii.
3. Otwórz małą serię jednej klatki, sprawdź K1 oraz zbyt małą liczbę oznaczeń; wróć do modelu wspólnego.

## Granice zadania

To niezależne odkrywanie klas, odrębne od segmentacji jednej klatki przy słowniku serii.
