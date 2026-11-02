# 07: Wybierz liczbę klas i zakres ich odkrywania

**ID:** SD-V4-07

**What to build:** Użytkownik wybiera bieżącą klatkę albo zakres do odkrywania klas, wpisuje K i otrzymuje nowy wynik bieżącej klatki. Program sam dopasowuje klasy z wybranych danych; przy zakresie tworzy wspólny katalog klas. Nie ma obowiązku wczytywania ani ręcznego przygotowania pliku modelu.

**Blocked by:** [05: Oblicz klasy i domeny bieżącej klatki z danych](05-analyze-current-frame.md).

**Status:** ready-for-agent — wymaga ukończenia zależności.

Obowiązują [wspólne kryteria odbioru](README.md#wspólne-kryteria-odbioru).

## Kryteria akceptacji

- [ ] Wybór Bieżąca klatka / Wybrany zakres / Cała seria określa dane do odkrywania klas. Dopasowanie korzysta tylko z tego wejścia i identyfikowalnej skali; nie wymaga paczki, modelu ani pierwszych dziesięciu klatek. Zakres dopasowania jest odrębny od klatki aktualnie analizowanej.
- [ ] Ręczne K obsługuje 1–8, z ograniczeniem przez liczbę użytecznych próbek. PCA i miary akceptacji poprawnie obsługują małe dane oraz K1.
- [ ] Nowy słownik ma własną wersję i wspólne znaczenie klas w swoim zakresie. Dopasowanie jednej klatki pozostaje jawnie lokalne, niezależne od pozostałych obrazów. Zmiana modelu nie przemianowuje wcześniejszych wyników ani nie przenosi automatycznie lokalnego słownika na inne klatki.
- [ ] Po dopasowaniu bieżąca klatka dostaje wynik z nowym modelem. Wyniki na pozostałych klatkach mają jawny status: wcześniejszy model albo jeszcze nieprzeliczone.
- [ ] K można zmienić bezpośrednio w UI i uruchomić nowe dopasowanie. Można wrócić do wcześniejszego poprawnego wyniku oraz jego lokalnego/wspólnego słownika. Nie utożsamiamy etykiet dwóch niezależnych dopasowań.
- [ ] Testy potwierdzają zakres dopasowania, K1, zbyt duże K, brak danych, powtarzalność i prawidłowe zastosowanie zachowanego wewnętrznego słownika.
- [ ] Działającą funkcję sprawdzono automatycznie i ręcznie zgodnie z zakresem; przekazanie rozróżnia wykonane sprawdzenia od niewykonanych.
- [ ] Sprawdzono długość nowego i zmienianego kodu oraz testów według wspólnej zasady 1000/1500 linii.

## Test ręczny użytkownika

1. Na klatce 259 wybierz Bieżąca klatka, podaj K5, dopasuj i obejrzyj wynik. Powtórz z K4: widok i ustawienia pokazują nowe, lokalne klasy.
2. Wybierz zakres 259–268, podaj K5 i uruchom. Bieżąca klatka dostaje wynik ze wspólnym słownikiem wyznaczonym z tego zakresu; pozostałe klatki nie udają już przeliczonych. Pierwsze dziesięć klatek ani żaden plik modelu nie są wymagane.
3. Wróć do wcześniejszego lokalnego wyniku klatki 259. Nazwy/kolory i metadane opisują jego własny słownik. Przejście do 268 nie tworzy samo nowego lokalnego modelu.
4. Otwórz przygotowaną serię jednej klatki i wybierz K1; dla zbyt dużego K lub braku danych program pokazuje zrozumiały komunikat zamiast awarii. Dostarczona para kontroli różniących się tylko niewybranymi klatkami daje identyczny lokalny wynik.

## Granice zadania

K określa liczbę roboczych klas opisu, nie liczbę domen ani potwierdzonych faz fizycznych. Podstawowe dopasowanie jednej klatki istnieje już w 05; ten ticket dodaje ręczne K, K1, wspólny zakres i zachowanie wersji słownika. Wchłania pozostały zakres dawnego 11. Przeliczanie wszystkich domen zakresu dodaje 08, Auto dodaje 12.
