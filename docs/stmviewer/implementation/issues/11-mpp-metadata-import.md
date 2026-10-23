# 11: Otwarcie MPP z metadanymi towarzyszącymi

**What to build:** Użytkownik otwiera przygotowaną parę MPP i dodatku, widzi właściwe parametry oraz pochodzenie każdej klatki i rozpoznaje brakujący lub niedopasowany dodatek.

**Blocked by:** [04: Otwarcie filmu MPP z czasami i pochodzeniem](04-mpp-series.md)

**Status:** in-progress

**Wykonawca:** Codex, `viewer/start`, 2026-10-23.
**Baza code-review:** `b71305bfb2886d734cc087708780f22ea12fd30d`.

**Specyfikacja:** [Zapis MPP z wartościami i metadanymi](../../issues/04-mpp-export.md#answer), [Dane i kryteria odbioru pierwszej wersji](../../issues/06-acceptance.md#answer).

Przed realizacją przeczytaj [zasady wykonania i odbioru](../README.md#zasady-wykonania-i-odbioru).

## Kryteria odbioru

- [ ] Dodatek jest odnajdywany automatycznie przy otwieraniu MPP. Przyjęty kontrakt wersji, nazw i powiązania z filmem jest opisany i sprawdzany.
- [ ] Dodatek zachowuje pochodzenie, źródłowy numer, czasy z przerwami/brakami, indywidualną kalibrację/kanał/jednostkę oraz źródłowe nagłówki. Poprawne dane są widoczne po zmianie klatki.
- [ ] Różne skale/kanały nie są zastępowane wspólnymi metadanymi pierwszej klatki. Przeniesienie kompletnej pary do innego katalogu nie zrywa powiązania.
- [ ] Bez dodatku film nadal się otwiera. Dodatek uszkodzony, niedopasowany do treści/kształtu/liczby klatek albo o nieobsługiwanej wersji nie jest nakładany; użytkownik widzi przyczynę.
- [ ] Dostarczony mały wzorzec pary pozwala sprawdzić import w GUI bez oczekiwania na eksporter. Formatowe fikstury mają niezależnie znane liczby i metadane.
- [ ] Ten etap obejmuje informacje oryginalnej serii i weryfikację dodatku. Pełną geometrię historii rejestracji i jej podgląd domyka etap zapisu aligned.

## Testy automatyczne

- Publiczne otwarcie pary z niezależnie przygotowanym wzorcem: wersja, integralność, czas, pochodzenie i kalibracja per klatka.
- Import bez dodatku i z niedopasowaniem/uszkodzeniem, widoczna informacja i brak nakładania cudzych metadanych.

## Publiczne granice testów dla TDD

Zatwierdzenie zestawu obejmuje poniższe granice. Testuj zachowanie przez te interfejsy; prywatne metody i przypadkowy podział klas nie są kontraktem.

- **Otwarcie plików → seria lub błąd** — Sprawdza dekodowanie, orientację i metadane przez publiczny import; nie dowodzi poprawnego malowania obrazu na ekranie.
- **Publiczne kontrolki GUI → widoczny wynik** — Sprawdza połączenie przycisków, etykiet i podglądu; Qt offscreen nie zastępuje ręcznej oceny ani zewnętrznego odtwarzacza.

Baza code-review: HEAD zapisany przed rozpoczęciem tego ticketu. Specyfikacja przeglądu: ten ticket i wskazane decyzje; standardy: instrukcje repo/aplikacji, w tym limit plików.

## Test manualny programu

Dane i sposób przygotowania nietypowych wzorców dostarcza realizujący ticket. Próba korzysta z rzeczywistej aplikacji oraz funkcji dostępnych po tym etapie.

1. Otwórz przygotowaną parę z trzema klatkami o różnych parametrach i czasach. Przejdź przez klatki i sprawdź pochodzenie oraz etykiety.
2. Przenieś kopię pary do innego katalogu i otwórz ponownie; dane pozostają przypisane właściwym obrazom.
3. Na kopiach sprawdź brak dodatku, dodatek innego filmu i nieobsługiwaną wersję; obrazy otwierają się bez zastosowania błędnych informacji.
4. Zmień zawartość MPP we wzorcu przy zachowanych wymiarach, pozostawiając stary dodatek; powiązanie ma zostać odrzucone.

## Współpraca z integracją

Adapter dodatku może pozostać w Viewer. Jeśli trzeba rozszerzyć wspólny odczyt/model metadanych, uzgodnić z integracją zgodność istniejących odbiorców; nie zmieniać interpretacji pomiarów po cichu.
