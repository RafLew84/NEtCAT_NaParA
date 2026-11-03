# 15: Dostosuj opis otoczenia i bariery obrazu

**ID:** SD-V4-15

**What to build:** W części zaawansowanej użytkownik zmienia zasięg opisu geometrii albo parametry barier, uruchamia właściwy etap obliczeń i porównuje wynik na obrazie.

**Blocked by:** [07: Wybierz liczbę klas i zakres ich odkrywania](07-fit-shared-classes.md).

**Status:** done — implementacja `1b0c1de`, poprawki `9fe24a6` i `9bf767a`; odbiór ręczny użytkownika oczekuje.

[Raport i test ręczny](acceptance-15.md), [parametry i znaczenie](advanced-settings.md),
[przegląd](review-15.md). Zakładka **Zaawansowane** we wspólnym oknie analizy.

Obowiązują [wspólne kryteria odbioru](README.md#wspólne-kryteria-odbioru).

## Kryteria akceptacji

- [x] Sigma opisu, liczba składowych PCA i obsługiwane parametry histogramu są prawdziwą konfiguracją modelu. Zmiana opisu jawnie wymaga nowych cech i dopasowania.
- [x] Parametry barier obejmują progi kontrastu, długość fragmentów, dopuszczalną przerwę, nachylenie i poszerzenie w granicach istniejącej metody. Podgląd barier jest opcjonalną warstwą diagnostyczną.
- [x] Zmiana samych barier zachowuje model klas, a zmiana opisu tworzy nową wersję modelu. Cache i wcześniejsze wyniki zachowują poprawne pochodzenie.
- [x] Cechy, słownik i bariery są obliczane z otwartych danych. Nazwy klas, skala, parametry PCA ani maski barier nie są pobierane z paczki dawnego eksperymentu; ustawienia bazowe należą do metody zaimplementowanej w aplikacji.
- [x] Założenia kierunku i znaku kontrastu detektora są opisane w UI. Suwaki nie udają uniwersalnego detektora tarasów ani tolerancji kąta molekuły.
- [x] Nieobsługiwane kombinacje lub zbyt mało danych są odrzucane przed kosztownym przebiegiem. Obliczenia można anulować.
- [x] Testy potwierdzają wpływ kontrolek, zgodność wymiarów modelu i właściwy zakres ponownych obliczeń.
- [x] Działającą funkcję sprawdzono automatycznie i ręcznie zgodnie z zakresem; przekazanie rozróżnia wykonane sprawdzenia od niewykonanych.
- [x] Sprawdzono długość nowego i zmienianego kodu oraz testów według wspólnej zasady 1000/1500 linii.

## Test ręczny użytkownika

1. Otwórz MPP/JSON, wybierz zakres i K, oblicz wynik bazowy. Zmień sigma opisu z bazowego 1,25, odkryj klasy ponownie i sprawdź nowy model oraz porównanie wyniku.
2. Przy zachowanym modelu zmień próg barier, włącz ich podgląd i przelicz domeny; sprawdź, że model klas się nie zmienił.
3. Przywróć ustawienia bazowe aplikacji i oblicz wynik ponownie na tym samym zakresie z tym samym ziarnem; porównaj z wynikiem zachowanym w punkcie 1. Przetestuj błędną kombinację oraz anulowanie.

## Granice zadania

To zadanie rozszerza panel po uzyskaniu podstawowej interakcji. Nie zawiera nowego algorytmu detekcji molekuł, barier ani treningu sieci neuronowej. Kod v0.4 jest wzorem metody; przywrócenie ustawień nie wczytuje jego gotowych modeli lub przypisań.
