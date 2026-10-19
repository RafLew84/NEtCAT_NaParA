# 03: S94 i mieszane serie STP/S94

**What to build:** Użytkownik otwiera S94 albo wspólnie STP i S94 oraz przegląda je na takich samych zasadach jak serię STP.

**Blocked by:** [02: Otwarcie i przeglądanie serii STP](02-stp-series.md)

**Status:** ready-for-agent

**Specyfikacja:** [Seria wejściowa i usuwanie klatek](../../issues/01-frame-series.md#answer), [Dane i kryteria odbioru pierwszej wersji](../../issues/06-acceptance.md#answer).

Przed realizacją przeczytaj [zasady wykonania i odbioru](../README.md#zasady-wykonania-i-odbioru).

## Kryteria odbioru

- [ ] Wybór plików dopuszcza S94 i mieszankę STP/S94, z jedną naturalną kolejnością nazw oraz zgodnością wyłącznie wymiarów.
- [ ] Każda klatka zachowuje własny kanał, jednostkę sygnału, skalę X/Y i pochodzenie; parametry pierwszej klatki nie zastępują pozostałych.
- [ ] Znana kalibracja S94 daje wartości w odpowiedniej jednostce; nieznany tryb lub wzmocnienie pozostaje jawnie nieznane/surowe.
- [ ] Właściwe są orientacja, wymiary i metadane po transformacji wejścia, także dla niesymetrycznego obrazu. Sprawdzona jest kolejność bajtów danych.
- [ ] Błąd lub anulowanie mieszanego importu nie publikuje częściowej serii. Dotychczasowy podgląd zachowuje stan.

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
