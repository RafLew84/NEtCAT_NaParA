# 10: Deep Matcher z lokalnymi wagami

**What to build:** Użytkownik widzi rzeczywistą dostępność Deep Matcher i przy obecnych lokalnych wagach wykonuje rejestrację, również na CUDA, bez pobierania plików przez aplikację.

**Blocked by:** [08: Rejestracja Phase i pełny widok aligned](08-phase-registration.md)

**Status:** ready-for-agent

**Specyfikacja:** [Rejestracja i życie wyniku aligned](../../issues/03-registration.md#answer), [Dane i kryteria odbioru pierwszej wersji](../../issues/06-acceptance.md#answer).

Przed realizacją przeczytaj [zasady wykonania i odbioru](../README.md#zasady-wykonania-i-odbioru).

## Kryteria odbioru

- [ ] Sprawdzenie dostępności i start obliczeń nie pobierają wag ani bibliotek. Brak/nieprawidłowe wagi lub zależności dają czytelny powód.
- [ ] Przy poprawnym lokalnym środowisku wybrany Deep Matcher tworzy aligned zgodnie ze wspólnym cyklem rejestracji.
- [ ] Jawna informacja o faktycznym urządzeniu rozróżnia CPU/CUDA. Zachowanie wyboru urządzenia nie jest cichą zamianą wybranej metody na inny backend.
- [ ] Błąd inicjalizacji/modelu, brak zasobów lub anulowanie zachowuje poprzedni wynik; okno pozostaje responsywne.
- [ ] Instrukcja wyjaśnia lokalne przygotowanie zależności/wag poza aplikacją i sposób sprawdzenia CUDA. Dostępność GPU nie jest wnioskowana tylko z jego nazwy.
- [ ] Odbiór zawiera próbę braku wag oraz rzeczywistą próbę modelu/CUDA, gdy środowisko jest dostępne. FakeMatcher nie zastępuje raportu tej próby; brak środowiska jest zapisany jawnie.

## Testy automatyczne

- Dostępność bez sieci, lokalne ładowanie, błąd wag/urządzenia oraz zachowanie stanu.
- Kontrolowane testy integracji matchera i osobno oznaczona próba rzeczywistych wag, bez automatycznego pobierania.

## Publiczne granice testów dla TDD

Zatwierdzenie zestawu obejmuje poniższe granice. Testuj zachowanie przez te interfejsy; prywatne metody i przypadkowy podział klas nie są kontraktem.

- **Rejestracja oryginałów → kompletny wynik** — Sprawdza wynik, status, anulowanie i geometrię aligned; nie stanowi uniwersalnej oceny skuteczności na nowych pomiarach.
- **Publiczne kontrolki GUI → widoczny wynik** — Sprawdza połączenie przycisków, etykiet i podglądu; Qt offscreen nie zastępuje ręcznej oceny ani zewnętrznego odtwarzacza.

Baza code-review: HEAD zapisany przed rozpoczęciem tego ticketu. Specyfikacja przeglądu: ten ticket i wskazane decyzje; standardy: instrukcje repo/aplikacji, w tym limit plików.

## Test manualny programu

Dane i sposób przygotowania nietypowych wzorców dostarcza realizujący ticket. Próba korzysta z rzeczywistej aplikacji oraz funkcji dostępnych po tym etapie.

1. Uruchom aplikację bez udostępnionych wag; wybierz Deep Matcher i sprawdź komunikat oraz brak prób pobierania.
2. Udostępnij przygotowane lokalnie wagi, ponownie sprawdź dostępność i zarejestruj mały wzorzec.
3. Sprawdź wskazane urządzenie i aligned; na stanowisku CUDA zapisz wynik rzeczywistej próby GPU.
4. Przy istniejącym wyniku zasymuluj uszkodzone wagi w odrębnym środowisku testowym lub anuluj próbę; wcześniejszy aligned pozostaje.

## Współpraca z integracją

Wspólna inicjalizacja LoFTR wymaga ścieżki bez automatycznego pobierania; zmiany backendu i stosu Torch/Kornia/CUDA wykonuje integracja.
