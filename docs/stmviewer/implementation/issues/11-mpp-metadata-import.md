# 11: Otwarcie MPP z metadanymi towarzyszącymi

**What to build:** Użytkownik otwiera przygotowaną parę MPP i dodatku, widzi właściwe parametry oraz pochodzenie każdej klatki i rozpoznaje brakujący lub niedopasowany dodatek.

**Blocked by:** [04: Otwarcie filmu MPP z czasami i pochodzeniem](04-mpp-series.md)

**Status:** ready-for-review

**Wykonawca:** Codex, `viewer/start`, 2026-10-23.
**Baza code-review:** `b71305bfb2886d734cc087708780f22ea12fd30d`.

**Specyfikacja:** [Zapis MPP z wartościami i metadanymi](../../issues/04-mpp-export.md#answer), [Dane i kryteria odbioru pierwszej wersji](../../issues/06-acceptance.md#answer).

Przed realizacją przeczytaj [zasady wykonania i odbioru](../README.md#zasady-wykonania-i-odbioru).

## Kryteria odbioru

- [x] Dodatek jest odnajdywany automatycznie przy otwieraniu MPP. Przyjęty kontrakt wersji, nazw i powiązania z filmem jest opisany i sprawdzany.
- [x] Dodatek zachowuje pochodzenie, źródłowy numer, czasy z przerwami/brakami, indywidualną kalibrację/kanał/jednostkę oraz źródłowe nagłówki. Poprawne dane są widoczne po zmianie klatki.
- [x] Różne skale/kanały nie są zastępowane wspólnymi metadanymi pierwszej klatki. Przeniesienie kompletnej pary do innego katalogu nie zrywa powiązania.
- [x] Bez dodatku film nadal się otwiera. Dodatek uszkodzony, niedopasowany do treści/kształtu/liczby klatek albo o nieobsługiwanej wersji nie jest nakładany; użytkownik widzi przyczynę.
- [x] Dostarczony mały wzorzec pary pozwala sprawdzić import w GUI bez oczekiwania na eksporter. Formatowe fikstury mają niezależnie znane liczby i metadane.
- [x] Ten etap obejmuje informacje oryginalnej serii i weryfikację dodatku. Pełną geometrię historii rejestracji i jej podgląd domyka etap zapisu aligned.

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


## Realizacja — 2026-10-23

Implementacja: `137655d`. Baza: `b71305b`; końcowy raport zapisany osobnym
commitem. [Kontrakt V1](../../mpp-metadata-format.md) określa nazwę dodatku,
SHA-256 wszystkich bajtów MPP, liczbę/kształt klatek oraz typy pól.
Walidacja całego dodatku poprzedza zastosowanie jakichkolwiek metadanych.
Historyczne pochodzenie jest odrębne od faktycznie otwartego pliku.
Błędny lub brakujący dodatek zachowuje obrazy i dane nagłówka, pokazując
przyczynę. Anulowanie importu zachowuje poprzednią serię.

- **193 testy Viewera zaliczone**, 2 opcjonalne próby wag Deep Matcher
  pominięte, 18.86 s. Ten ticket dodaje 16 przypadków. Mypy strict:
  **21 plików**, bez błędów.
- Pełny zestaw repo: **1979 passed, 14 failed, 16 skipped**, 229.88 s,
  bez błędów zbierania. Wszystkie 14 niepowodzeń MolTrack/NanoTrack jest
  identyczne z listą ticketu 10; brak nowych niepowodzeń.
- Automatyczne GUI Qt xcb z rzeczywistymi dialogami: poprawna para,
  brak dodatku, błędna treść/kształt/liczba/wersja/JSON, przeniesienie
  i zmiana nazwy pary, usuwanie oraz lokalny MOVIE_3 — zaliczone.
  Obejrzano zrzuty; źródła zachowały SHA-256.
- [Przegląd](../review-11-mpp-metadata-import.md): Standards — 0, Spec — 0.
  Największy zmieniony plik kodu: **640 linii**. Generator odtwarza wszystkie
  13 plików wzorców bajtowo; odnośniki dokumentacji i `git diff --check` poprawne.
- [Instrukcja manualna](../../mpp-metadata-manual.md) zawiera dane, kroki
  i oczekiwane wartości. Ręczny odbiór użytkownika jeszcze niewykonany;
  Windows nie był uruchamiany. Status pozostaje `ready-for-review`.

Zmiany wyłącznie w Viewerze, jego testach i dokumentacji; wspólne czytniki
oraz środowisko pozostają bez zmian. Szczegóły: [przekazanie](../../handoff.md).
