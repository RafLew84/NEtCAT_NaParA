# 18: Duża seria: podgląd i rejestracja

**What to build:** Użytkownik otwiera 1000 klatek 512 × 512, płynnie przegląda original/aligned, usuwa klatki i ponawia Phase w przyjętym budżecie zasobów.

**Blocked by:** [08: Rejestracja Phase i pełny widok aligned](08-phase-registration.md)

**Status:** in-progress

**Wykonawca:** Codex
**Baza przeglądu:** `08c1f3c4495a9d15b6632811fe4a99fc76b511fa`

**Specyfikacja:** [Dane i kryteria odbioru pierwszej wersji](../../issues/06-acceptance.md#answer).

Przed realizacją przeczytaj [zasady wykonania i odbioru](../README.md#zasady-wykonania-i-odbioru).

## Kryteria odbioru

- [ ] Duża seria przechodzi import, podgląd, usuwanie, Phase i ponowną rejestrację, również z powiększonym aligned; ten etap nie wymaga jeszcze eksporterów.
- [ ] Oba widoki po wczytaniu osiągają 5 kl./s; wybór/Pause daje widoczny efekt do 250 ms w co najmniej 95% prób według przyjętej metody pomiaru.
- [ ] Wyższe tempo zwalnia bez pomijania klatek. Import i rejestracja zachowują postęp, anulowanie i responsywny podgląd.
- [ ] Powtarzanie otwarcia/usuwania/rejestracji zwalnia niepotrzebne stosy i cache. Błąd zasobów lub anulowanie nie publikuje częściowego nowego stanu.
- [ ] Raport obejmuje dane, wymiary aligned, CPU, dostępny/szczytowy RAM i czasy. Test 1000 klatek nie wprowadza sztywnego limitu importu.
- [ ] Wprowadzone poprawki wynikają z pomiaru i zachowują istniejący kontrakt, a nie stroją jakości algorytmu. Nie planować nieograniczonego refaktoru całej aplikacji.

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
