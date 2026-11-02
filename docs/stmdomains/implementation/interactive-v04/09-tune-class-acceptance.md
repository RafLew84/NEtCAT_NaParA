# 09: Reguluj akceptację klasy i zobacz przyczynę odmowy

**ID:** SD-V4-09

**What to build:** Użytkownik zmienia dopuszczalną niejednoznaczność przypisania klasy, przelicza klatkę i sprawdza, które molekuły odzyskały lub utraciły końcową domenę.

**Blocked by:** [05: Oblicz domeny na bieżącej klatce](05-analyze-current-frame.md).

**Status:** draft — podział oczekuje na zatwierdzenie użytkownika.

Obowiązują [wspólne kryteria odbioru](README.md#wspólne-kryteria-odbioru).

## Kryteria akceptacji

- [ ] Kontrolki minimalnego marginesu i mnożnika promienia klasy rzeczywiście sterują akceptacją; confidence nie jest przedstawiane jako skalibrowane prawdopodobieństwo.
- [ ] Słownik, centroidy i wstępna najbliższa klasa pozostają zachowane. Zmiana akceptacji nie jest ukrytym ponownym dopasowaniem.
- [ ] UI odróżnia klasę wstępną, akceptację klasy, potwierdzenie porządku i końcową domenę; szczegóły są dostępne po wskazaniu molekuły.
- [ ] Przy K1 stosuje się jawny właściwy warunek zamiast marginesu dwóch klas. Nowe ustawienia mają walidację i zapis w wyniku.
- [ ] Kontrolowane testy wykazują wpływ progów i zachowanie tożsamości słownika.
- [ ] Działającą funkcję sprawdzono automatycznie i ręcznie zgodnie z zakresem; przekazanie rozróżnia wykonane sprawdzenia od niewykonanych.
- [ ] Sprawdzono długość nowego i zmienianego kodu oraz testów według wspólnej zasady 1000/1500 linii.

## Test ręczny użytkownika

1. Przy zamrożonym K5 zmień margines 0,075 na 0,06 i przelicz tę samą klatkę.
2. Sprawdź kilka szarych i kolorowych molekuł: powód odmowy oraz końcowy wynik muszą odpowiadać ustawieniom.
3. Zmień mnożnik promienia klasy, przywróć wartości bazowe i porównaj wynik; model nie został ponownie dopasowany.

## Granice zadania

Ten ticket nie wymaga nowych modeli ani wyboru Auto; obsługuje model już dostępny użytkownikowi.
