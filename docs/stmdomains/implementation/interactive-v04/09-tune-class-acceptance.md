# 09: Reguluj akceptację klasy i zobacz przyczynę odmowy

**ID:** SD-V4-09

**What to build:** Użytkownik zmienia dopuszczalną niejednoznaczność przypisania klasy, przelicza klatkę i sprawdza, które molekuły odzyskały lub utraciły końcową domenę.

**Blocked by:** [07: Wybierz liczbę klas i zakres ich odkrywania](07-fit-shared-classes.md).

**Status:** done — implementacja `494ab9d`, ukończono 2026-11-03; ręczny odbiór użytkownika potwierdzony 2026-11-03 dla wersji `9dd934d` („testy manualne ok”).

[Uruchomienie, wykonane sprawdzenia i test ręczny](acceptance-09.md).
Baza `b34e862`, gałąź `domains/interactive-v04-ui`, środowisko netcat.
427 testów PASS, mypy 63 moduły PASS, przegląd Standards/Spec bez uwag.

Obowiązują [wspólne kryteria odbioru](README.md#wspólne-kryteria-odbioru).

Zakres testów zgodny z kryteriami poniżej: publiczne obliczenia przy
zachowanym katalogu oraz kontrolki UI → przeliczenie, porównanie i szczegóły
oznaczenia. Testy i uruchomienie w netcat; odbiór użytkownika oddzielnie.

## Kryteria akceptacji

- [x] Kontrolki minimalnego marginesu i mnożnika promienia klasy rzeczywiście sterują akceptacją; confidence nie jest przedstawiane jako skalibrowane prawdopodobieństwo.
- [x] Słownik, centroidy i wstępna najbliższa klasa pozostają zachowane. Zmiana akceptacji nie jest ukrytym ponownym dopasowaniem.
- [x] Słownik pochodzi z wcześniejszego obliczenia w tej aplikacji na jawnym zakresie otwartych danych. Nie wymaga zewnętrznego modelu, etykiet ani wyników paczki v0.4.
- [x] UI odróżnia klasę wstępną, akceptację klasy, potwierdzenie porządku i końcową domenę; szczegóły są dostępne po wskazaniu molekuły.
- [x] Przy K1 stosuje się jawny właściwy warunek zamiast marginesu dwóch klas. Nowe ustawienia mają walidację i zapis w wyniku.
- [x] Kontrolowane testy wykazują wpływ progów i zachowanie tożsamości słownika.
- [x] Działającą funkcję sprawdzono automatycznie i ręcznie zgodnie z zakresem; przekazanie rozróżnia wykonane sprawdzenia od niewykonanych.
- [x] Sprawdzono długość nowego i zmienianego kodu oraz testów według wspólnej zasady 1000/1500 linii.

## Test ręczny użytkownika

1. Otwórz MPP/JSON, dopasuj K5 na wybranym zakresie i oblicz klatkę 259. Zachowując ten słownik, zmień margines 0,075 na 0,06 i przelicz tę samą klatkę; porównaj z zapisanym w aplikacji wynikiem sprzed zmiany.
2. Sprawdź kilka szarych i kolorowych molekuł: powód odmowy oraz końcowy wynik muszą odpowiadać ustawieniom.
3. Zmień mnożnik promienia klasy, przywróć wartości bazowe i porównaj wynik; model nie został ponownie dopasowany. Na dostarczonej kontroli utwórz K1 i sprawdź jawny warunek akceptacji bez marginesu dwóch klas.

## Granice zadania

Ten ticket reguluje akceptację przy zachowanym słowniku obliczonym przez aplikację. Nie obejmuje ponownego odkrywania klas ani wyboru Auto. Wartości progów zaczerpnięte z v0.4 są punktem startowym metody, a nie wczytywanym zasobem.
