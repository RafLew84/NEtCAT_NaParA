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
