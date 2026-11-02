# 12: Wybierz liczbę klas automatycznie

**ID:** SD-V4-12

**What to build:** Użytkownik wybiera Auto zamiast K, analizuje zakres lub jedną klatkę i widzi wybraną liczbę klas wraz z wynikiem oraz informacją o nierozstrzygnięciu.

**Blocked by:** [11: Odkryj klasy wyłącznie na jednej klatce](11-fit-single-frame.md).

**Status:** draft — podział oczekuje na zatwierdzenie użytkownika.

Obowiązują [wspólne kryteria odbioru](README.md#wspólne-kryteria-odbioru).

## Kryteria akceptacji

- [ ] Tryb Auto jest przekazywany przez dopasowanie, wybór modelu i segmentację; zapisane selected_classes nie nadpisuje go po drodze.
- [ ] Program porównuje dopuszczalnych kandydatów do wskazanego maksimum, z kontrolą liczby próbek. Pokazuje wybrane K i krótkie uzasadnienie.
- [ ] Jawna reguła odróżnia jedną klasę, K>=2 i brak podstaw do oceny. Reguła jest zapisana przed oceną TTMAPP; samo silhouette nie jest stosowane do K1.
- [ ] Kontrole obejmują pojedynczą sieć, dwa odróżnialne otoczenia, szum oraz brak/słabe dane. Program nie wymusza co najmniej dwóch klas.
- [ ] Użytkownik może przełączyć na ręczne K i porównać wynik. Obecny ranking paczki preferujący K2 nie jest potajemnie zastępowany ręcznym K5.
- [ ] Testy obejmują obie skale zakresu, powtarzalność, K1, nierozstrzygnięcie i pełne przejście trybu Auto przez obliczenia.
- [ ] Działającą funkcję sprawdzono automatycznie i ręcznie zgodnie z zakresem; przekazanie rozróżnia wykonane sprawdzenia od niewykonanych.
- [ ] Sprawdzono długość nowego i zmienianego kodu oraz testów według wspólnej zasady 1000/1500 linii.

## Test ręczny użytkownika

1. Wybierz Auto dla zakresu 259–268 oraz dla pojedynczej klatki; sprawdź wybrane K i przypisany do niego wynik.
2. Na dostarczonych kontrolach jednej sieci i dwóch otoczeń sprawdź zachowanie Auto, następnie otwórz przykład z niewystarczającymi danymi.
3. Przełącz z Auto na K5 i z powrotem; widok oraz metadane muszą pokazywać faktycznie użyty model, bez nadpisania wcześniejszego wyniku.

## Granice zadania

Auto jest wyborem w ograniczonym zakresie, nie gwarancją liczby fizycznych faz. Nowy klasteryzator bez K nie jest wymagany do realizacji tego ticketu.
