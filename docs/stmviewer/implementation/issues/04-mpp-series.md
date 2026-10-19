# 04: Otwarcie filmu MPP z czasami i pochodzeniem

**What to build:** Użytkownik otwiera jeden film MPP, przegląda wszystkie jego klatki i widzi ich źródłową kolejność oraz dostępny czas pomiaru.

**Blocked by:** [02: Otwarcie i przeglądanie serii STP](02-stp-series.md)

**Status:** ready-for-agent

**Specyfikacja:** [Seria wejściowa i usuwanie klatek](../../issues/01-frame-series.md#answer), [Zapis MPP z wartościami i metadanymi](../../issues/04-mpp-export.md#answer), [Dane i kryteria odbioru pierwszej wersji](../../issues/06-acceptance.md#answer).

Przed realizacją przeczytaj [zasady wykonania i odbioru](../README.md#zasady-wykonania-i-odbioru).

## Kryteria odbioru

- [ ] Jeden MPP zastępuje serię po pełnym sukcesie; interfejs nie łączy kilku MPP ani MPP z STP/S94.
- [ ] Klatki zachowują kolejność z filmu, orientację, wartości, metadane i źródłowy numer, odrębny od pozycji w serii.
- [ ] Znane czasy są poprawnie interpretowane z jednostką, a częściowe braki nie usuwają pozostałych czasów. FPS nie tworzy czasu pomiaru; brak pozostaje brakiem.
- [ ] Nagłówek z ponad 1000 liniami i film o 1000 klatkach są obsługiwane bez ukrytego limitu liczby klatek.
- [ ] Niepełne/uszkodzone dane, brak uprawnień i anulowanie nie zastępują poprzedniej serii. Postęp oraz kontrolki wyboru działają dla wieloklatkowego filmu.
- [ ] Obsługa własnego dodatku MPP będzie częścią zapisu original i ponownego odczytu; ten etap umożliwia rzeczywiste oglądanie istniejących filmów.

## Testy automatyczne

- Dekodowanie prawdziwego małego MPP, orientacja, jednostki/częściowe braki czasu i walidacja długości danych.
- Długi nagłówek, kolejność 1000 klatek i transakcyjna zmiana stanu; nie ograniczać się do mocka czytnika.

## Publiczne granice testów dla TDD

Zatwierdzenie zestawu obejmuje poniższe granice. Testuj zachowanie przez te interfejsy; prywatne metody i przypadkowy podział klas nie są kontraktem.

- **Otwarcie plików → seria lub błąd** — Sprawdza dekodowanie, orientację i metadane przez publiczny import; nie dowodzi poprawnego malowania obrazu na ekranie.
- **Publiczne kontrolki GUI → widoczny wynik** — Sprawdza połączenie przycisków, etykiet i podglądu; Qt offscreen nie zastępuje ręcznej oceny ani zewnętrznego odtwarzacza.

Baza code-review: HEAD zapisany przed rozpoczęciem tego ticketu. Specyfikacja przeglądu: ten ticket i wskazane decyzje; standardy: instrukcje repo/aplikacji, w tym limit plików.

## Test manualny programu

Dane i sposób przygotowania nietypowych wzorców dostarcza realizujący ticket. Próba korzysta z rzeczywistej aplikacji oraz funkcji dostępnych po tym etapie.

1. Otwórz mały rzeczywisty MPP i przejdź do pierwszej, środkowej i ostatniej klatki; porównaj liczbę klatek i ich pochodzenie.
2. Otwórz mały wzorzec z czasami w sekundach/milisekundach i brakującym czasem jednej klatki; sprawdź etykiety.
3. Otwórz niewielki wymiarowo film z 1000 klatkami i długim nagłówkiem; wybierz ostatnią klatkę.
4. Przy aktywnej serii otwórz ucięty MPP lub anuluj import; zachowany zostaje dotychczasowy podgląd.

## Współpraca z integracją

Wspólne czytniki/loader wymagają uzgodnienia obrotu, jednostek czasu, częściowych braków i limitu nagłówka. Ich poprawki realizuje integracja z testami dotychczasowych odbiorców.
