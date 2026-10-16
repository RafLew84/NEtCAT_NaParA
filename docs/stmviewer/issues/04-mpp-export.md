# Zapis MPP z wartościami i metadanymi

Type: grilling
Label: wayfinder:grilling
Status: open
Assignee: none
Parent: [STM Viewer — mapa pierwszej wersji](../map.md)
Blocked by: 03

Zależy od: [Rejestracja i życie wyniku aligned](03-registration.md).

## Question

Jaki kontrakt eksportu MPP zachowa właściwe wartości, orientację, skalę,
metadane i brakujące piksele dla serii original oraz aligned?

Do ustalenia: wybór eksportowanej wersji i klatek; niezależność danych MPP od
gamma; jednostki wartości STP/S94; metadane po połączeniu plików i usunięciu
klatek; sposób kodowania brakujących pikseli; wymagane czytniki odbiorcze.
Ponowny odczyt ma obejmować wartości, orientację, rozmiar piksela, offset,
liczbę i kolejność klatek. Osobno trzeba określić możliwość ponownej rejestracji
zapisanego aligned.

## Comments

### 2026-10-14 — stan rozpoznania

Eksport MPP jest wymaganiem użytkownika. Zaproponowano zapis danych niezależny
od gamma; odpowiedź użytkownika dotyczyła opcji AVI, więc szczegółowy kontrakt
MPP pozostaje do uzgodnienia.

Nie znaleziono istniejącego eksportera MPP. Obecny czytnik obsługuje float64,
ale brakujące piksele aligned to NaN, a rejestracja wymaga skończonych wartości.
Istotne są także różne miejsca obrotu danych i różne jednostki wejścia.
Zobacz [rozpoznanie czytników](../reconnaissance.md).

### 2026-10-16 — konsekwencje kontraktu serii

[Seria wejściowa i usuwanie klatek](01-frame-series.md) dopuszcza różne skale
i kanały przy jednakowych wymiarach. Każda klatka zachowuje własne metadane,
pochodzenie i dostępny czas pomiaru, również po usunięciu innych lub odwróceniu
kolejności. Kontrakt MPP musi rozstrzygnąć zapis takiej serii, w tym różnych
metadanych, przerw w czasach pomiaru i ich odwróconej kolejności. Nie można
zakładać, że metadane pierwszej klatki opisują wszystkie pozostałe.
