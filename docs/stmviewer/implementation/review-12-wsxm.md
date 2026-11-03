# Przegląd poprawki WSxM — ticket 12

Data: 2026-10-23. Baza: `7eab8e9903dea84bbb31768efebc6310ed8f5044`.
Zakres: `git diff 7eab8e9...0cb6644`, commity `b887b2b`, `0cb6644`.
Obie osie wykonane równolegle przez niezależnych recenzentów, wyłącznie
odczytowo. Specyfikacja: [ticket 12](issues/12-original-mpp.md) oraz dodatkowe
zgłoszenie błędnego wyglądu i paska przy lewej krawędzi w WSxM.
Standardy: główne i aplikacyjne AGENTS.md, instrukcja współpracy, mapa,
zasady implementacji oraz heurystyki `code-review`.

## Standards

Brak naruszeń udokumentowanych wymagań. Zmiany pozostają w zakresie
aplikacji. Test używa publicznego eksportera i niezależnego wzorca bajtów
zweryfikowanego w WSxM. Dokumentacja odróżnia automatykę od ręcznego odbioru
i wyjaśnia ograniczenia Windows. Nie znaleziono potrzeby refaktoru.

Jedna uwaga heurystyczna niskiej istotności: opis wcześniejszego testu
przypisywał błąd clippingowi, mimo skorygowanej diagnozy. Opis zmieniono na
sprawdzanie deklaracji zakresu bez transformowania próbek. Kod testu i
aplikacji nie wymagały dalszej zmiany po przeglądzie.

## Spec

Brak brakujących wymagań, nadmiarowego zakresu i błędnej implementacji
w zakresie poprawki. Zachowano wartości, orientację, przypisanie czasów do
indeksów, pochodzenie, indywidualne metadane i powiązanie JSON z MPP.
Skanowanie zakresu ma ograniczone zużycie pamięci i obsługuje anulowanie.

Recenzent niezależnie porównał `test-wsxm-v2.mpp` z kopią zapisaną przez
WSxM: **24 182 784 / 24 182 784 próbek zgodnych**, przesunięcie 0.
Nie uruchamiał GUI ani pytest. Raport poprawnie odróżnia historię pierwszej
niepełnej poprawki od końcowego rozwiązania oraz podaje ograniczenia
Windows, NaN, kodowania nagłówków i indywidualnych metadanych.

Standards: 0 naruszeń, 1 poprawiona uwaga heurystyczna, 0 otwartych;
Spec: 0 ustaleń.
