# 03: Przeglądaj serię przez miniatury i odtwarzanie

**ID:** SD-V4-03

**What to build:** Użytkownik przewija serię przez pasek miniatur i odtwarza kolejne klatki. Może dostosować gamma i zatrzymać obraz do inspekcji.

**Blocked by:** [01: Otwórz zapis i przeglądaj obrazy](01-open-images.md).

**Status:** done — implementacja i odbiór ręczny funkcji 03 zakończone.
Późniejsza poprawka błędu przy wyjściu czeka na ręczne sprawdzenie.

Baza implementacji i przeglądu: `d862333`, gałąź `domains/interactive-v04-ui`.
Środowisko: `netcat`. Testy przez publiczne interfejsy renderera, paska miniatur,
kontrolera i pełną ścieżkę import–widok, zgodnie z kryteriami podglądu.
Implementacja: `93701af`; commit `c5deb59` zawiera poprawki pauzy/zaznaczenia
i [raport z instrukcją testu ręcznego](acceptance-03.md).
Po wstępnym sprawdzeniu użytkownika poprawiono skakanie układu podczas
ładowania; [raport poprawki](acceptance-03.md#poprawka-po-zgłoszeniu-użytkownika--stabilny-układ-okna)
zawiera scenariusz ponownego sprawdzenia. **Użytkownik potwierdził pomyślny
ręczny odbiór 03 i poprawki `0745e4e` 2026-11-02: „testy manualne ok”.**
Następnie usunięto zgłoszony błąd wyjścia podczas pracy w tle;
[scenariusz sprawdzenia zamknięcia](acceptance-03.md#poprawka-wyjścia-z-programu)
pozostaje do wykonania przez użytkownika.

Obowiązują [wspólne kryteria odbioru](README.md#wspólne-kryteria-odbioru).

## Kryteria akceptacji

- [x] Pasek miniatur, suwak i numer wskazują tę samą klatkę. Działają play/pauza, od początku i szybkości przyjęte w kontrakcie podglądu.
- [x] Przy wolnym przygotowaniu odtwarzanie zwalnia, zachowując kolejność. Pauza nie powoduje późniejszego dodatkowego kroku; koniec zatrzymuje odtwarzanie.
- [x] Kontrast jest ustalany na oryginalnej klatce i wspólny dla jej widoków. Gamma, zoom i warstwy są zachowywane podczas nawigacji zgodnie z kontraktem.
- [x] Miniatury i cache mają ograniczony koszt; stale spóźnione żądania nie mieszają klatek. Po dołączeniu oznaczeń i wyników są publikowane razem z obrazem.
- [x] Testy obejmują pauzę, koniec, opóźnione przygotowanie, pojedynczą klatkę i niepoprawne próbki obrazu.
- [x] Sprawdzono automatycznie, w rzeczywistym GUI sterowanym Qt i przez ogląd zrzutów. Użytkownik potwierdził odbiór ręczny 03 i poprawki układu; późniejsza poprawka zamknięcia ma osobny scenariusz.
- [x] Sprawdzono długość nowego i zmienianego kodu oraz testów według wspólnej zasady 1000/1500 linii.

## Test ręczny użytkownika

1. Przejdź do wybranej klatki miniaturą, suwakiem i numerem; za każdym razem sprawdź zgodność wskazań.
2. Uruchom odtwarzanie wolno i szybko, zatrzymaj oraz wznów; nie może wystąpić dodatkowy krok po pauzie ani przeskok przy przeciążeniu.
3. Zmień gamma, powiększenie i rozmiar okna, potem otwórz serię jednej klatki; widok pozostaje czytelny, a zbędne sterowanie jest wyłączone.

## Granice zadania

Ten ticket może powstać niezależnie od oznaczeń i analizy. Nie dodaje śledzenia obiektów w czasie.
