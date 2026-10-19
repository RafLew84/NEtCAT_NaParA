# 19: Duże eksporty i wspólna praca funkcji

**What to build:** Użytkownik zapisuje pełną dużą serię do MPP i AVI, również po usunięciu i ponownej rejestracji, z poprawnym połączeniem aligned, kontrastu, teł i opisów.

**Blocked by:** [13: Zapis aligned do MPP z pełną geometrią](13-aligned-mpp.md), [16: Film AVI z aligned i pełnym obszarem](16-aligned-avi.md), [17: Podziałka, numer i czas w AVI](17-avi-annotations.md), [18: Duża seria: podgląd i rejestracja](18-large-series-preview.md)

**Status:** ready-for-agent

**Specyfikacja:** [Dane i kryteria odbioru pierwszej wersji](../../issues/06-acceptance.md#answer).

Przed realizacją przeczytaj [zasady wykonania i odbioru](../README.md#zasady-wykonania-i-odbioru).

## Kryteria odbioru

- [ ] Pełne 1000 klatek przechodzi zapis/ponowny odczyt original i aligned w MPP oraz zapis i odtworzenie MJPG/FFV1. Test nie ogranicza się do małego wycinka dużego filmu.
- [ ] Aligned, opisy, oba tryby kontrastu, gamma i tła działają razem, także po usunięciu odniesienia/skrajnej klatki i po nowej rejestracji.
- [ ] Eksporter nie buforuje niepotrzebnie całego wyrenderowanego AVI. Powtarzanie eksportu zwalnia dane robocze i pozwala nadal przeglądać serię.
- [ ] Postęp i anulowanie działają, a błąd zasobów/zapisu zachowuje wcześniejsze pliki. Dodatki MPP pozostają powiązane z właściwym filmem.
- [ ] Raport podaje rozmiary, pełną liczbę klatek, czasy i szczytowe użycie zasobów całej aplikacji; wartości MPP i raster FFV1 przechodzą wymagane porównania.
- [ ] Etap zawiera poprawki usterek połączenia funkcji i skali eksportu. Podstawowy renderer, formaty i zabezpieczenia muszą być już działające po zależnych ticketach.

## Testy automatyczne

- Pełny eksport/odczyt dużej serii oraz integracja aligned, opisów, teł i kontrastu przez publiczne operacje.
- Kontrolowane awarie i anulowanie zapisu dużych plików, brak narastającego zatrzymywania danych i pełna zgodność MPP/FFV1.

## Publiczne granice testów dla TDD

Zatwierdzenie zestawu obejmuje poniższe granice. Testuj zachowanie przez te interfejsy; prywatne metody i przypadkowy podział klas nie są kontraktem.

- **Pełny przebieg użytkownika → pomiar zasobów** — Sprawdza płynność, pamięć i czas na wskazanych danych/sprzęcie; nie uogólnia wyniku na dowolną stację.
- **Zapis pary MPP i ponowny odczyt** — Sprawdza wartości, metadane i bezpieczeństwo plików; sam odczyt własnym importerem nie dowodzi zgodności innych czytników.
- **Eksport AVI → rzeczywiście odczytany film** — Sprawdza liczbę, kolejność, FPS, rozmiar i raster kodeka oraz błędy zapisu; nie zastępuje odtworzenia w VLC.

Baza code-review: HEAD zapisany przed rozpoczęciem tego ticketu. Specyfikacja przeglądu: ten ticket i wskazane decyzje; standardy: instrukcje repo/aplikacji, w tym limit plików.

## Test manualny programu

Dane i sposób przygotowania nietypowych wzorców dostarcza realizujący ticket. Próba korzysta z rzeczywistej aplikacji oraz funkcji dostępnych po tym etapie.

1. Otwórz przygotowany duży wzorzec, wykonaj Phase i usuń wybrane klatki; zachowaj manifest i parametry wyniku.
2. Zapisz całą pozostałą serię w obu wariantach MPP i obu kodekach AVI, wybierając aligned z opisami i wspólnym kontrastem.
3. Otwórz MPP w aplikacji, AVI w VLC i porównaj wartości/rastry raportem; sprawdź liczbę klatek i pełne krawędzie.
4. Powtórz eksport po nowej rejestracji, anuluj kolejny zapis i sprawdź poprzedni film oraz zużycie/zwalnianie pamięci.

## Współpraca z integracją

Optymalizacje wspólnych loaderów/backendów/materializatora i zależności prowadzi integracja z testami odbiorców. Zachować zewnętrzne kontrakty i unikać szerokiego refaktoru niezwiązanego z pomiarem problemu.
