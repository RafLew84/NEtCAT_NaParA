# 03: S94 i mieszane serie STP/S94

**What to build:** Użytkownik otwiera S94 albo wspólnie STP i S94 oraz przegląda je na takich samych zasadach jak serię STP.

**Blocked by:** [02: Otwarcie i przeglądanie serii STP](02-stp-series.md)

**Status:** ready-for-review

**Wykonawca:** Codex, `viewer/start`.

**Baza code-review:** `b904045e7626e97cd924920d9fbb0e52fbdb3bcc`.

**Specyfikacja:** [Seria wejściowa i usuwanie klatek](../../issues/01-frame-series.md#answer), [Dane i kryteria odbioru pierwszej wersji](../../issues/06-acceptance.md#answer).

Przed realizacją przeczytaj [zasady wykonania i odbioru](../README.md#zasady-wykonania-i-odbioru).

## Kryteria odbioru

- [x] Wybór plików dopuszcza S94 i mieszankę STP/S94, z jedną naturalną kolejnością nazw oraz zgodnością wyłącznie wymiarów.
- [x] Każda klatka zachowuje własny kanał, jednostkę sygnału, skalę X/Y i pochodzenie; parametry pierwszej klatki nie zastępują pozostałych.
- [x] Znana kalibracja S94 daje wartości w odpowiedniej jednostce; nieznany tryb lub wzmocnienie pozostaje jawnie nieznane/surowe.
- [x] Właściwe są orientacja, wymiary i metadane po transformacji wejścia, także dla niesymetrycznego obrazu. Sprawdzona jest kolejność bajtów danych.
- [x] Błąd lub anulowanie mieszanego importu nie publikuje częściowej serii. Dotychczasowy podgląd zachowuje stan.

## Testy automatyczne

- Realne dekodowanie małych S94, znana/nieznana kalibracja, orientacja i zgodność z odpowiadającym STP.
- Mieszany import, per-klatkowe metadane i brak częściowej podmiany przy błędzie.

## Publiczne granice testów dla TDD

Zatwierdzenie zestawu obejmuje poniższe granice. Testuj zachowanie przez te interfejsy; prywatne metody i przypadkowy podział klas nie są kontraktem.

- **Otwarcie plików → seria lub błąd** — Sprawdza dekodowanie, orientację i metadane przez publiczny import; nie dowodzi poprawnego malowania obrazu na ekranie.
- **Publiczne kontrolki GUI → widoczny wynik** — Sprawdza połączenie przycisków, etykiet i podglądu; Qt offscreen nie zastępuje ręcznej oceny ani zewnętrznego odtwarzacza.

Baza code-review: HEAD zapisany przed rozpoczęciem tego ticketu. Specyfikacja przeglądu: ten ticket i wskazane decyzje; standardy: instrukcje repo/aplikacji, w tym limit plików.

## Test manualny programu

Dane i sposób przygotowania nietypowych wzorców dostarcza realizujący ticket. Próba korzysta z rzeczywistej aplikacji oraz funkcji dostępnych po tym etapie.

1. Otwórz rzeczywistą parę odpowiadających sobie STP/S94; porównaj orientację i kształt obrazu oraz podane jednostki.
2. Wczytaj mieszankę obu formatów z celowo nieuporządkowanymi nazwami; przejdź przez wszystkie miniatury.
3. Otwórz przygotowany S94 z nieznaną kalibracją; oczekuj jawnego braku jednostki fizycznej, bez wymyślonego nm.
4. Dodaj do nowego wyboru wadliwy S94; poprzednia poprawna seria pozostaje otwarta.

## Współpraca z integracją

Ewentualne poprawki wspólnego czytnika S94, jego kalibracji i metadanych przekazać integracji wraz z testem odbiorców.

## Wynik implementacji — 2026-10-21

Działa otwieranie jednego lub wielu S94 oraz mieszanych STP/S94, ze wspólnym
sortowaniem, kontrolą wymiarów po transpozycji i dotychczasową ochroną stanu.
Adapter S94 odczytuje int16 little-endian do float64, zachowuje źródłowy
nagłówek, rozróżnia kalibrację nm/nA od surowych wartości i opisuje jej brak
w panelu. Zamiana osi obejmuje dane, wymiary, rozmiary i offsety; kąt pozostaje
ustawieniem pomiaru. Wspólne moduły i zależności nie zostały zmienione.

Commit implementacji: `d6fbb7d`.
[Przegląd](../review-03-s94-series.md): Standards — 0 ustaleń; Spec — 0 ustaleń.

54 testy Viewera oraz mypy strict (13 plików) przechodzą. Trzy lokalne pary
STP/S94 mają identyczne wartości macierzy; znaną rozbieżność jednostki w jednym
STP opisano w instrukcji. Automatyczna próba xcb przeszła. Wynik pełnego repo
oraz przeglądu jest zapisany w [przekazaniu](../../handoff.md).

[Scenariusz ręczny, małe wzorce i lokalne pomiary](../../s94-series-manual.md).
Ręczny odbiór użytkownika i Windows pozostają niewykonane, stąd
`ready-for-review`.
