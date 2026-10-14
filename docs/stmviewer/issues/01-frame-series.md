# Seria wejściowa i usuwanie klatek

Type: grilling
Label: wayfinder:grilling
Status: open
Assignee: none
Parent: [STM Viewer — mapa pierwszej wersji](../map.md)
Blocked by: none

## Question

Jak działa jedna otwarta seria: kolejność klatek, kolejne wczytanie plików,
wymagana zgodność wymiarów i skali oraz usuwanie klatki z analizy?

Do ustalenia pozostają: sposób sortowania, zastąpienie/dodanie serii przy kolejnym
otwarciu, obsługa niezgodnych klatek i błędnego pliku, usunięcie ostatniej klatki
oraz zachowanie identyfikacji i metadanych po usunięciu. Wpływ na gotową
rejestrację rozstrzygnie [Rejestracja i życie wyniku aligned](03-registration.md)
po ustaleniu modelu serii.

## Comments

### 2026-10-14 — wymagania i odpowiedź użytkownika

Jedna seria to dowolna liczba plików STP/S94 (także mieszanka obu formatów)
albo dokładnie jeden MPP zawierający wiele klatek. Nie łączymy MPP z STP/S94.
Usunięcie usuwa zaznaczoną klatkę z bieżącej analizy; bez funkcji cofania.
Nie jest to polecenie kasowania źródła z dysku. W MPP operacja dotyczy klatki,
nie wszystkich klatek pliku.

Istniejący loader spełnia regułę formatów i wymaga identycznych wymiarów,
ale nie sprawdza zgodności skali ani kanału. Fakty i odnośniki:
[Rozpoznanie istniejącego kodu](../reconnaissance.md).
