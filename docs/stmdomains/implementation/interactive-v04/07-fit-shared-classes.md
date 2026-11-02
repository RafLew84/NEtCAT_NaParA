# 07: Odkryj wspólne klasy z ręcznie podanym K

**ID:** SD-V4-07

**What to build:** Użytkownik wybiera zakres do odkrywania klas, wpisuje K i otrzymuje nowy wspólny model oraz wynik bieżącej klatki. Nie potrzebuje historycznego słownika q/w.

**Blocked by:** [05: Oblicz domeny na bieżącej klatce](05-analyze-current-frame.md).

**Status:** draft — podział oczekuje na zatwierdzenie użytkownika.

Obowiązują [wspólne kryteria odbioru](README.md#wspólne-kryteria-odbioru).

## Kryteria akceptacji

- [ ] Można wybrać zakres niezawierający pierwszych dziesięciu klatek. Dopasowanie korzysta tylko z jawnie wybranego zakresu i identyfikowalnej skali.
- [ ] Ręczne K obsługuje 1–8, z ograniczeniem przez liczbę użytecznych próbek. PCA i miary akceptacji poprawnie obsługują małe dane oraz K1.
- [ ] Nowy słownik ma własną wersję i wspólne znaczenie klas w swoim zakresie. Zmiana modelu nie przemianowuje historycznych wyników.
- [ ] Po dopasowaniu bieżąca klatka dostaje wynik z nowym modelem. Wyniki na pozostałych klatkach mają jawny status: wcześniejszy model albo jeszcze nieprzeliczone.
- [ ] Skala i nazewnictwo nie zależą od ukrytych plików pierwszego eksperymentu. Refaktor wymagany do tego zachowania jest częścią ticketu.
- [ ] Testy potwierdzają zakres dopasowania, K1, zbyt duże K, brak danych, powtarzalność i prawidłowe zastosowanie zapisanego modelu.
- [ ] Działającą funkcję sprawdzono automatycznie i ręcznie zgodnie z zakresem; przekazanie rozróżnia wykonane sprawdzenia od niewykonanych.
- [ ] Sprawdzono długość nowego i zmienianego kodu oraz testów według wspólnej zasady 1000/1500 linii.

## Test ręczny użytkownika

1. Wybierz zakres 259–268, podaj K5, dopasuj i obejrzyj wynik; pierwsze dziesięć klatek nie jest wymagane.
2. Powtórz z K4 i porównaj klasy na tej samej klatce. Wróć do wcześniejszego modelu, który zachowuje własne znaczenie etykiet.
3. Na przygotowanym prostym przykładzie wybierz K1; dla zbyt dużego K lub braku danych program pokazuje zrozumiały komunikat zamiast awarii.

## Granice zadania

K określa liczbę roboczych klas opisu, nie liczbę domen ani potwierdzonych faz fizycznych.
