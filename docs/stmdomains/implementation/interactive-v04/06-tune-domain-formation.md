# 06: Strojenie tworzenia domen i porównanie wyniku

**ID:** SD-V4-06

**What to build:** Użytkownik zmienia minimum molekuł, odległość łączenia i zgodność geometrii, przelicza bieżącą klatkę oraz porównuje ją z poprzednim wynikiem.

**Blocked by:** [05: Oblicz klasy i domeny bieżącej klatki z danych](05-analyze-current-frame.md).

**Status:** ready-for-agent — wymaga ukończenia zależności.

Obowiązują [wspólne kryteria odbioru](README.md#wspólne-kryteria-odbioru).

## Kryteria akceptacji

- [ ] UI steruje rzeczywistymi parametrami minimum domeny, odległości łączenia, trybu geometrii, progu krawędzi, średnicy regionu oraz zasięgu maski.
- [ ] Minimum domeny jest spójne po budowie grafu i po rasteryzacji. Walidacja wymaga poprawnych zakresów i progu krawędzi nie większego od średnicy regionu.
- [ ] Zmiany dotyczą tworzenia domen; słownik klas i jego zakres pozostają zachowane. Cache jest używany wyłącznie dla zgodnych danych i ustawień.
- [ ] Działa przełączenie poprzedni/nowy wynik na tej samej klatce oraz Przywróć ustawienia bazowe. Bazowy wynik jest przeliczany w aplikacji przy tym samym wewnętrznie dopasowanym modelu; nie jest importowany z v0.4. Edycja ustawień sama nie przemalowuje starego wyniku.
- [ ] Zapisane metadane pokazują wartości faktycznie użyte. Testy na kontrolowanym układzie potwierdzają wpływ każdej kontrolki, bez wymagania monotonicznych zmian zachłannego podziału.
- [ ] Ustawienia przekazywane do obliczeń i raportowane w wyniku mają jedno źródło. Wspólna konfiguracja zastępuje powtórzone stałe bazowej wersji 05; oba etapy sprawdzania minimum domeny korzystają z tej samej wartości.
- [ ] Działającą funkcję sprawdzono automatycznie i ręcznie zgodnie z zakresem; przekazanie rozróżnia wykonane sprawdzenia od niewykonanych.
- [ ] Sprawdzono długość nowego i zmienianego kodu oraz testów według wspólnej zasady 1000/1500 linii.

## Test ręczny użytkownika

1. Wykonaj analizę 259 z 05. Przelicz średnicę regionu 0,50, 0,55 i 0,60 przy pozostałych ustawieniach stałych; porównaj wyniki w tej samej pozycji obrazu.
2. Osobno zmień minimum 8 na 6 i odległość łączenia; sprawdź liczniki, zachowany model klas i dane użytych ustawień.
3. Wprowadź błędną relację progów, potem przywróć ustawienia bazowe; walidacja zatrzymuje błędny start, a ponowne obliczenie odtwarza bazowy wynik aplikacji.

## Granice zadania

Więcej przypisań lub mniej fragmentów nie oznacza automatycznie lepszej jakości. Punktem porównania jest bazowa metoda zaimplementowana w 05 na wzór v0.4, dopasowana do tych samych danych. Nie jest potrzebny zewnętrzny model ani wynik.
