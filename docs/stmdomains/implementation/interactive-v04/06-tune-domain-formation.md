# 06: Strojenie tworzenia domen i porównanie wyniku

**ID:** SD-V4-06

**What to build:** Użytkownik zmienia minimum molekuł, odległość łączenia i zgodność geometrii, przelicza bieżącą klatkę oraz porównuje ją z poprzednim wynikiem.

**Blocked by:** [05: Oblicz domeny na bieżącej klatce](05-analyze-current-frame.md).

**Status:** draft — podział oczekuje na zatwierdzenie użytkownika.

Obowiązują [wspólne kryteria odbioru](README.md#wspólne-kryteria-odbioru).

## Kryteria akceptacji

- [ ] UI steruje rzeczywistymi parametrami minimum domeny, odległości łączenia, trybu geometrii, progu krawędzi, średnicy regionu oraz zasięgu maski.
- [ ] Minimum domeny jest spójne po budowie grafu i po rasteryzacji. Walidacja wymaga poprawnych zakresów i progu krawędzi nie większego od średnicy regionu.
- [ ] Zmiany dotyczą tworzenia domen; słownik klas i jego zakres pozostają zachowane. Cache jest używany wyłącznie dla zgodnych danych i ustawień.
- [ ] Działa przełączenie poprzedni/nowy wynik na tej samej klatce oraz Przywróć v0.4. Edycja ustawień sama nie przemalowuje starego wyniku.
- [ ] Zapisane metadane pokazują wartości faktycznie użyte. Testy na kontrolowanym układzie potwierdzają wpływ każdej kontrolki, bez wymagania monotonicznych zmian zachłannego podziału.
- [ ] Działającą funkcję sprawdzono automatycznie i ręcznie zgodnie z zakresem; przekazanie rozróżnia wykonane sprawdzenia od niewykonanych.
- [ ] Sprawdzono długość nowego i zmienianego kodu oraz testów według wspólnej zasady 1000/1500 linii.

## Test ręczny użytkownika

1. Na 259 przelicz średnicę regionu 0,50, 0,55 i 0,60 przy pozostałych ustawieniach stałych; porównaj wyniki w tej samej pozycji obrazu.
2. Osobno zmień minimum 8 na 6 i odległość łączenia; sprawdź liczniki, zachowany model klas i dane użytych ustawień.
3. Wprowadź błędną relację progów, potem przywróć v0.4; walidacja zatrzymuje błędny start, a ustawienia bazowe odtwarzają bazowy wynik.

## Granice zadania

Więcej przypisań lub mniej fragmentów nie oznacza automatycznie lepszej jakości. Wartości łagodniejsze od v0.4 są ustawieniami eksperymentalnymi.
