# 13: Zapisz projekt i otwórz wynik bez ponownych obliczeń

**ID:** SD-V4-13

**What to build:** Użytkownik zapisuje pracę do samowystarczalnego pliku STM Domains, zamyka aplikację i odzyskuje obrazy, oznaczenia, ustawienia oraz wybrany wynik bez oryginalnych plików i bez uruchamiania modeli.

**Blocked by:** [05: Oblicz klasy i domeny bieżącej klatki z danych](05-analyze-current-frame.md).

**Status:** ready-for-agent — plan zaktualizowany na polecenie użytkownika; wykonanie po zależnościach.

Obowiązują [wspólne kryteria odbioru](README.md#wspólne-kryteria-odbioru).

## Kryteria akceptacji

- [ ] Zapis realizuje istniejący kontrakt samowystarczalnego projektu: MPP, oznaczenia, geometria, stan widoku, parametry oraz jeden wybrany wynik albo jawny brak analizy.
- [ ] Otwarcie odtwarza zapisany rezultat bez przeliczania ani zewnętrznego modelu. Podgląd korzysta z przypisań zapisanych w projekcie. Jeżeli do kontynuowania obliczeń potrzebny jest słownik klas, aplikacja korzysta z bezpiecznie zapisanego stanu własnego dopasowania albo jawnie wyznacza nowy z danych projektu; nie żąda paczki v0.4.
- [ ] Zapisz jako pozwala zachować warianty osobno. Nowe ustawienia nie zmieniają metadanych starego wyniku.
- [ ] Zapis jest atomowy i ma kontrolę integralności. Anulowanie lub błąd pozostawia poprzedni plik i otwartą pracę.
- [ ] Format zachowuje częściowe wyniki i ich statusy oraz rzeczywiście dostępne pola analizy. Nie deklaruje pełnego pokrycia lub powierzchni fizycznej na podstawie samych punktów.
- [ ] Testy round-trip obejmują brak wyniku, wynik częściowy, uszkodzenie, brak oryginalnych źródeł i odtworzenie podglądu bez obliczania słownika. Zapis zachowuje pochodzenie rzeczywiście obliczonego wyniku; brak stanu dopasowania nie uprawnia do przypisania starego identyfikatora nowo wyznaczonym klasom.
- [ ] Działającą funkcję sprawdzono automatycznie i ręcznie zgodnie z zakresem; przekazanie rozróżnia wykonane sprawdzenia od niewykonanych.
- [ ] Sprawdzono długość nowego i zmienianego kodu oraz testów według wspólnej zasady 1000/1500 linii.

## Test ręczny użytkownika

1. Otwórz MPP/JSON, oblicz wynik klatki 259 w aplikacji, zapisz go do nowego projektu i zamknij aplikację.
2. Otwórz kopię projektu przy niedostępnych oryginalnych MPP/JSON i bez jakiejkolwiek paczki/modelu v0.4; obraz oraz przypisania mają się odtworzyć bez analizy.
3. Wykonaj Zapisz jako dla innego wariantu, sprawdź dwa niezależne pliki, anulowanie zapisu oraz kontrolny uszkodzony projekt.

## Granice zadania

To samowystarczalny projekt STM Domains, nie import historycznych wyników v0.4 ani sam plik parametrów JSON. Trwała historia wielu wyników w jednym projekcie nie jest wymagana przez obecny kontrakt.
