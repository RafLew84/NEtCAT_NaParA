# 13: Zapisz projekt i otwórz wynik bez ponownych obliczeń

**ID:** SD-V4-13

**What to build:** Użytkownik zapisuje pracę do samowystarczalnego pliku STM Domains, zamyka aplikację i odzyskuje obrazy, oznaczenia, ustawienia oraz wybrany wynik bez oryginalnych plików i bez uruchamiania modeli.

**Blocked by:** [05: Oblicz domeny na bieżącej klatce](05-analyze-current-frame.md).

**Status:** draft — podział oczekuje na zatwierdzenie użytkownika.

Obowiązują [wspólne kryteria odbioru](README.md#wspólne-kryteria-odbioru).

## Kryteria akceptacji

- [ ] Zapis realizuje istniejący kontrakt samowystarczalnego projektu: MPP, oznaczenia, geometria, stan widoku, parametry oraz jeden wybrany wynik albo jawny brak analizy.
- [ ] Otwarcie odtwarza zapisany rezultat bez modeli i bez przeliczania. Zasób modelu potrzebny do kontynuowania obliczeń jest odróżniony od danych potrzebnych tylko do podglądu.
- [ ] Zapisz jako pozwala zachować warianty osobno. Nowe ustawienia nie zmieniają metadanych starego wyniku.
- [ ] Zapis jest atomowy i ma kontrolę integralności. Anulowanie lub błąd pozostawia poprzedni plik i otwartą pracę.
- [ ] Format zachowuje częściowe wyniki i ich statusy oraz rzeczywiście dostępne pola analizy. Nie deklaruje pełnego pokrycia lub powierzchni fizycznej na podstawie samych punktów.
- [ ] Testy round-trip obejmują brak wyniku, wynik częściowy, uszkodzenie, brak źródeł i brak zasobów modelu.
- [ ] Działającą funkcję sprawdzono automatycznie i ręcznie zgodnie z zakresem; przekazanie rozróżnia wykonane sprawdzenia od niewykonanych.
- [ ] Sprawdzono długość nowego i zmienianego kodu oraz testów według wspólnej zasady 1000/1500 linii.

## Test ręczny użytkownika

1. Zapisz wynik z 259 do nowego projektu i zamknij aplikację.
2. Otwórz kopię projektu przy niedostępnych oryginalnych MPP/JSON i modelu; obraz oraz przypisania mają się odtworzyć bez analizy.
3. Wykonaj Zapisz jako dla innego wariantu, sprawdź dwa niezależne pliki, anulowanie zapisu oraz kontrolny uszkodzony projekt.

## Granice zadania

To nie sam plik parametrów JSON. Trwała historia wielu wyników w jednym projekcie nie jest wymagana przez obecny kontrakt.
