# 18: Duża seria: podgląd i rejestracja

**What to build:** Użytkownik otwiera 1000 klatek 512 × 512, płynnie przegląda original/aligned, usuwa klatki i ponawia Phase w przyjętym budżecie zasobów.

**Blocked by:** [08: Rejestracja Phase i pełny widok aligned](08-phase-registration.md)

**Status:** done

**Wykonawca:** Codex
**Baza przeglądu:** `08c1f3c4495a9d15b6632811fe4a99fc76b511fa`

**Specyfikacja:** [Dane i kryteria odbioru pierwszej wersji](../../issues/06-acceptance.md#answer).

Przed realizacją przeczytaj [zasady wykonania i odbioru](../README.md#zasady-wykonania-i-odbioru).

## Kryteria odbioru

- [x] Duża seria przechodzi import, podgląd, usuwanie, Phase i ponowną rejestrację, również z powiększonym aligned; ten etap nie wymaga jeszcze eksporterów.
- [x] Oba widoki po wczytaniu osiągają 5 kl./s; wybór/Pause daje widoczny efekt do 250 ms w co najmniej 95% prób według przyjętej metody pomiaru.
- [x] Wyższe tempo zwalnia bez pomijania klatek. Import i rejestracja zachowują postęp, anulowanie i responsywny podgląd.
- [x] Powtarzanie otwarcia/usuwania/rejestracji zwalnia niepotrzebne stosy i cache. Błąd zasobów lub anulowanie nie publikuje częściowego nowego stanu.
- [x] Raport obejmuje dane, wymiary aligned, CPU, dostępny/szczytowy RAM i czasy. Test 1000 klatek nie wprowadza sztywnego limitu importu.
- [x] Wprowadzone poprawki wynikają z pomiaru i zachowują istniejący kontrakt, a nie stroją jakości algorytmu. Nie planować nieograniczonego refaktoru całej aplikacji.

## Testy automatyczne

- Powtarzalny generator, publiczne operacje dużej serii, pomiar rzeczywistych zmian obrazu i reakcji, oddzielnie od szybkich testów.
- Regresje cache/zwalniania zasobów i transakcyjnego stanu po błędzie lub anulowaniu.

## Publiczne granice testów dla TDD

Zatwierdzenie zestawu obejmuje poniższe granice. Testuj zachowanie przez te interfejsy; prywatne metody i przypadkowy podział klas nie są kontraktem.

- **Pełny przebieg użytkownika → pomiar zasobów** — Sprawdza płynność, pamięć i czas na wskazanych danych/sprzęcie; nie uogólnia wyniku na dowolną stację.
- **Działanie na serii → obserwowalny stan** — Sprawdza wybór, odtwarzanie, usuwanie i transakcyjną podmianę; nie mierzy fizycznej płynności ekranu.
- **Publiczne kontrolki GUI → widoczny wynik** — Sprawdza połączenie przycisków, etykiet i podglądu; Qt offscreen nie zastępuje ręcznej oceny ani zewnętrznego odtwarzacza.

Baza code-review: HEAD zapisany przed rozpoczęciem tego ticketu. Specyfikacja przeglądu: ten ticket i wskazane decyzje; standardy: instrukcje repo/aplikacji, w tym limit plików.

## Test manualny programu

Dane i sposób przygotowania nietypowych wzorców dostarcza realizujący ticket. Próba korzysta z rzeczywistej aplikacji oraz funkcji dostępnych po tym etapie.

1. Wygeneruj deterministyczną serię 1000 × 512 × 512 i zapisz jej manifest, następnie otwórz w programie.
2. Odtwarzaj oryginały przez co najmniej 30 s; wykonaj uzgodnione próby wyboru/Pause i pomiar pamięci.
3. Wykonaj Phase i powtórz pomiary na pełnym aligned; usuń klatki i ponów dopasowanie.
4. Powtórz otwieranie/rejestrację, anulując wybrane próby. Sprawdź zachowanie starego wyniku i zwalnianie niepotrzebnych danych.

## Współpraca z integracją

Optymalizacje wspólnych loaderów/backendów/materializatora i zależności prowadzi integracja z testami odbiorców. Zachować zewnętrzne kontrakty i unikać szerokiego refaktoru niezwiązanego z pomiarem problemu.

## Wynik — 2026-10-28

Implementacja narzędzi i testów `fb6b4e4`; poprawki po przeglądzie `ae06831`.
Kod aplikacji nie wymagał zmian. Kryteria sprawdzono w automatycznym przebiegu
GUI na X11. Użytkownik potwierdził ręczną akceptację 2026-10-28:
„testy manualne ok”. Odbiór obejmuje `fb6b4e4`, `ae06831`
i przekazanie `0edaef6`.

[Instrukcja i dane do próby ręcznej](../../large-series-manual.md),
[raport pomiarów](../../large-series-results.md),
[przegląd Standards/Spec](../review-18-large-series-preview.md),
[przekazanie i ograniczenia](../../handoff.md).

Duża seria: 1000 × 512 × 512, aligned 640 × 640, szczyt RSS 10,331 GB.
Oba widoki dały około 4,95–4,96 kl./s przy nominalnych 5, bez pomijania;
łącznie 400 prób wyboru/Pause na dużej i typowej serii: wszystkie do 250 ms.
Sprawdzono usuwanie, ponowną rejestrację, anulowanie odczytu/miniatur i obu
etapów Phase oraz zwalnianie starych tablic. Stanowisko ma więcej RAM niż
minimalne; cache plików i Xvfb ograniczają zakres wniosków (szczegóły w raporcie).

Szybki zestaw: 46 passed; 4 testy generatora/zasobów ponowione po poprawieniu
wzorca. Mypy: 33 pliki bez błędów. Pełny zestaw: 2154 passed, 15 failed,
16 skipped; błędy poza Viewerem i ich porównanie z bazą opisano w przekazaniu.
