# 15: Dostosuj opis otoczenia i bariery obrazu

**ID:** SD-V4-15

**What to build:** W części zaawansowanej użytkownik zmienia zasięg opisu geometrii albo parametry barier, uruchamia właściwy etap obliczeń i porównuje wynik na obrazie.

**Blocked by:** [07: Odkryj wspólne klasy z ręcznie podanym K](07-fit-shared-classes.md).

**Status:** draft — podział oczekuje na zatwierdzenie użytkownika.

Obowiązują [wspólne kryteria odbioru](README.md#wspólne-kryteria-odbioru).

## Kryteria akceptacji

- [ ] Sigma opisu, liczba składowych PCA i obsługiwane parametry histogramu są prawdziwą konfiguracją modelu. Zmiana opisu jawnie wymaga nowych cech i dopasowania.
- [ ] Parametry barier obejmują progi kontrastu, długość fragmentów, dopuszczalną przerwę, nachylenie i poszerzenie w granicach istniejącej metody. Podgląd barier jest opcjonalną warstwą diagnostyczną.
- [ ] Zmiana samych barier zachowuje model klas, a zmiana opisu tworzy nową wersję modelu. Cache i wcześniejsze wyniki zachowują poprawne pochodzenie.
- [ ] Założenia kierunku i znaku kontrastu detektora są opisane w UI. Suwaki nie udają uniwersalnego detektora tarasów ani tolerancji kąta molekuły.
- [ ] Nieobsługiwane kombinacje lub zbyt mało danych są odrzucane przed kosztownym przebiegiem. Obliczenia można anulować.
- [ ] Testy potwierdzają wpływ kontrolek, zgodność wymiarów modelu i właściwy zakres ponownych obliczeń.
- [ ] Działającą funkcję sprawdzono automatycznie i ręcznie zgodnie z zakresem; przekazanie rozróżnia wykonane sprawdzenia od niewykonanych.
- [ ] Sprawdzono długość nowego i zmienianego kodu oraz testów według wspólnej zasady 1000/1500 linii.

## Test ręczny użytkownika

1. Zmień sigma opisu z bazowego 1,25, odkryj klasy ponownie i sprawdź nowy model oraz porównanie wyniku.
2. Przy zachowanym modelu zmień próg barier, włącz ich podgląd i przelicz domeny; sprawdź, że model klas się nie zmienił.
3. Przywróć ustawienia v0.4 i porównaj z punktem odniesienia; przetestuj błędną kombinację oraz anulowanie.

## Granice zadania

To zadanie rozszerza panel po uzyskaniu podstawowej interakcji. Nie zawiera nowego algorytmu detekcji molekuł, barier ani treningu sieci neuronowej.
