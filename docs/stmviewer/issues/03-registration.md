# Rejestracja i życie wyniku aligned

Type: grilling
Label: wayfinder:grilling
Status: open
Assignee: none
Parent: [STM Viewer — mapa pierwszej wersji](../map.md)
Blocked by: 01

Zależy od: [Seria wejściowa i usuwanie klatek](01-frame-series.md).

## Question

Jak uruchamiać i prezentować istniejącą rejestrację NanoTrack oraz kiedy jej
wynik pozostaje ważny po zmianie serii?

Do ustalenia: punkt odniesienia i ponowna rejestracja, usunięcie klatki po
dopasowaniu (w tym pierwszej), nieudane dopasowanie, postęp i anulowanie,
zachowanie przy niedostępnym modelu oraz przejście na aligned po sukcesie.
Trzeba ustalić kontrakt powiększonego obszaru i brakujących danych dla eksportu.

## Comments

### 2026-10-14 — wymagania i odpowiedź użytkownika

Użytkownik wybrał jedną metodę z listy i przycisk „Rejestruj”, tak jak
w NanoTrack, domyślnie Phase i obecne ustawienia. Nie uruchamiamy wszystkich
metod jednocześnie. Lista obecnego UI: Phase, Tile+RANSAC, ECC, Optical Flow,
Deep Matcher. Rozwijanie metod i strojenie parametrów jest późniejszym etapem.

Po rejestracji potrzebny jest wspólny powiększony obszar bez obcięcia przesuniętych
klatek i przełączanie original/aligned. Dostępne API oraz ograniczenia wejścia
opisuje [Rozpoznanie istniejącego kodu](../reconnaissance.md).
