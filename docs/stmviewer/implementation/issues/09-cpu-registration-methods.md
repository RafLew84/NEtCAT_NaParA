# 09: Pozostałe metody rejestracji CPU

**What to build:** Użytkownik wybiera Tile+RANSAC, ECC lub Optical Flow i otrzymuje wynik w tym samym podglądzie i cyklu pracy co Phase.

**Blocked by:** [08: Rejestracja Phase i pełny widok aligned](08-phase-registration.md)

**Status:** in-progress

**Wykonawca:** Codex, `viewer/start`, 2026-10-23.
**Baza code-review:** `b8dcc4596988e8a2ee529f60b860f030b1be9749`.

**Specyfikacja:** [Rejestracja i życie wyniku aligned](../../issues/03-registration.md#answer), [Dane i kryteria odbioru pierwszej wersji](../../issues/06-acceptance.md#answer).

Przed realizacją przeczytaj [zasady wykonania i odbioru](../README.md#zasady-wykonania-i-odbioru).

## Kryteria odbioru

- [ ] Lista udostępnia istniejące metody i ustawienia NanoTrack, bez strojenia ani automatycznego wyboru innego algorytmu.
- [ ] Dostępność wynika z lokalnych zależności; brak metody ma widoczny powód. Sama zmiana wyboru nie zmienia gotowego aligned.
- [ ] Każda dostępna metoda obsługuje ten sam postęp, anulowanie, atomową podmianę, geometrię i usuwanie klatek.
- [ ] Kompletne wyniki niskiej pewności pozostają dostępne z oznaczeniem; wyjątek/failed/niepoprawne przesunięcia zachowują poprzedni wynik.
- [ ] Zależności są odtwarzalne w opisanym środowisku obu systemów; brak biblioteki nie uniemożliwia startu całego programu.

## Testy automatyczne

- Integracja każdej metody i normalizacja jej statusów zgodnie z istniejącym kontraktem.
- Brak bibliotek, nieudane/niekompletne wyniki oraz brak cichego zastąpienia metody.

## Publiczne granice testów dla TDD

Zatwierdzenie zestawu obejmuje poniższe granice. Testuj zachowanie przez te interfejsy; prywatne metody i przypadkowy podział klas nie są kontraktem.

- **Rejestracja oryginałów → kompletny wynik** — Sprawdza wynik, status, anulowanie i geometrię aligned; nie stanowi uniwersalnej oceny skuteczności na nowych pomiarach.
- **Publiczne kontrolki GUI → widoczny wynik** — Sprawdza połączenie przycisków, etykiet i podglądu; Qt offscreen nie zastępuje ręcznej oceny ani zewnętrznego odtwarzacza.

Baza code-review: HEAD zapisany przed rozpoczęciem tego ticketu. Specyfikacja przeglądu: ten ticket i wskazane decyzje; standardy: instrukcje repo/aplikacji, w tym limit plików.

## Test manualny programu

Dane i sposób przygotowania nietypowych wzorców dostarcza realizujący ticket. Próba korzysta z rzeczywistej aplikacji oraz funkcji dostępnych po tym etapie.

1. Zarejestruj mały wzorzec Phase, zmień wybór na każdą dostępną metodę CPU i kolejno uruchom dopasowanie.
2. Sprawdź, że samo wybranie innej metody nie zmieniło starego wyniku; po sukcesie obejrzyj aligned.
3. Anuluj kolejną próbę i sprawdź zachowanie poprzedniego wyniku.
4. W środowisku testowym bez opcjonalnej zależności sprawdź powód niedostępności i dalsze działanie Phase.

## Współpraca z integracją

Ewentualne zmiany wspólnych backendów i zależności prowadzi integracja; nowe UI korzysta z ich istniejących parametrów i zachowuje testy odbiorców.
