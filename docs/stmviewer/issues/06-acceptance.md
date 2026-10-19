# Dane i kryteria odbioru pierwszej wersji

Type: grilling
Label: wayfinder:grilling
Status: open
Assignee: none
Parent: [STM Viewer — mapa pierwszej wersji](../map.md)
Blocked by: 04, 05

Zależy od: [Zapis MPP z wartościami i metadanymi](04-mpp-export.md)
oraz [Opcje filmu AVI](05-avi-export.md).

## Question

Na jakich danych, platformach i mierzalnych kryteriach odbierzemy pierwszą wersję
przeglądarki, nie uzależniając jej od późniejszego strojenia rejestracji?

Do ustalenia: typowy i największy rozmiar serii, docelowe systemy grupy,
przykładowe STP/S94/MPP i odtwarzacz AVI, oczekiwana płynność, tolerancje
ponownego odczytu MPP oraz ręczny scenariusz GUI. Oddzielamy poprawne wykonanie
istniejącego algorytmu od jakości dopasowania nowych danych.

Po uzgodnieniu kontraktów należy wskazać pozostałe blokady implementacji,
w tym potrzebne zmiany wspólnych modułów do sesji integracyjnej.

## Comments

### 2026-10-14 — punkt wyjścia

Program będzie używany wewnętrznie przez kilka osób. Użytkownik dopuścił
lokalne środowisko conda netcat do rozwoju. Nie określił jeszcze systemów
docelowych ani wielkości serii. Lokalizacja środowiska i dostępne sprawdzenia:
[Rozpoznanie istniejącego kodu](../reconnaissance.md).

### 2026-10-19 — konsekwencje kontraktu MPP

[Zapis MPP z wartościami i metadanymi](04-mpp-export.md#answer) jest rozstrzygnięty.
Odbiór ma sprawdzić parę filmu i dodatku, zapis original/aligned, niezależność
od podglądu, liczby i orientację, NaN, geometrię, usuwanie klatek, czasy,
niejednorodną kalibrację oraz brakujący/niedopasowany dodatek. Zachowanie
liczb przy samej serializacji jest odrębne od dokładności wcześniejszej
interpolacji rejestracji.

Użytkownik wskazał WSxM jako program do późniejszego otwierania pliku;
nie tworzymy osobnego trybu eksportu i nie blokujemy z tej przyczyny
mieszanych serii. Potrzebna jest próba w docelowej wersji WSxM na małym
asymetrycznym filmie o znanych liczbach, skali i NaN. Należy oddzielić
otwarcie pliku od poprawnego wyświetlenia i interpretacji danych.
[Rozpoznanie](../wsxm-mpp-compatibility.md) nie potwierdza jeszcze NaN w WSxM.
Wynik próby nie może prowadzić do cichego zerowania lub kadrowania aligned.

Nie oceniono jeszcze docelowej wydajności, dużych serii ani właściwej wersji
WSxM. Obecny limit 1000 linii nagłówka nie może zostać ukrytym limitem liczby
klatek nowej aplikacji; zapis/odczyt ma go obsłużyć lub wykryć przed zapisem.
