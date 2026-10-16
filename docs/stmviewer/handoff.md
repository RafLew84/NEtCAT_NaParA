# Przekazanie — seria wejściowa STM Viewer

Data: 2026-10-16
Gałąź: `viewer/start`
Baza bieżącej zmiany: `1f28b63`
Commit dokumentacji: identyfikator w końcowej wiadomości sesji.

## Wynik

Rozstrzygnięto [Serię wejściową i usuwanie klatek](issues/01-frame-series.md)
na podstawie dwóch rund odpowiedzi użytkownika. Ticket ma status `resolved`;
odpowiedź zawiera kontrakt i przykłady do późniejszej weryfikacji implementacji.
Zaktualizowano indeks decyzji w [mapie](map.md), [słownik](GLOSSARY.md)
i [rozpoznanie istniejącego kodu](reconnaissance.md#uzupełnienie-seria-i-usuwanie-klatek).
W ticketach rejestracji i MPP dopisano konsekwencje importu różnych metadanych.

Zmiana obejmuje wyłącznie dokumentację STM Viewer. Nie wdrożono wczytywania,
odwracania ani usuwania klatek; aplikacja pozostaje szkieletem.

Kolejne dostępne decyzje:
[Podgląd, gamma i odtwarzanie serii](issues/02-preview-playback.md) oraz
[Rejestracja i życie wyniku aligned](issues/03-registration.md).
Reguły wyboru i przejęcia ticketu opisuje [README](README.md).

## Wykonane sprawdzenia

- Przegląd instrukcji, stanu Git, loaderów, modeli, zapisu sesji i istniejących
  testów NanoTrack/MolTrack.
- Trzy próby w pamięci: metadane po usunięciu klatki, ponowne odwrócenie
  podczas odtwarzania sesji NanoTrack oraz import różnych skal i kanałów.
  Wyniki i odnośniki zapisano w rozpoznaniu kodu.
- Kontrola lokalnych linków dokumentacji, statusów i zależności ticketów
  oraz `git diff --check`.

Nie uruchamiano zestawu testów ani GUI. Przykłady w odpowiedzi ticketu są
kryteriami przyszłej implementacji, a nie raportem działającej funkcji.
Nie sprawdzano eksportu ani jakości rejestracji na danych pomiarowych.

## Wspólne zmiany do rozważenia przez sesję integracyjną

- Przed ponownym użyciem modeli należy zapewnić powiązanie metadanych z klatką:
  MolTrack nie usuwa czasów razem z obrazem i przy odtwarzaniu podzbioru zachowuje
  pełne metadane źródła; loader serii STP/S94 używa wspólnych pól pierwszej klatki.
- Zapis/odtworzenie sesji NanoTrack odwraca ponownie odwróconą serię STP/S94.
  Warto poprawić ten błąd i objąć go testem integracyjnym, jeśli kod ma być
  ponownie używany. Ten ticket nie dodaje zapisu sesji do zakresu STM Viewer.
- Czytnik STP pomija warianty nazw pól offsetu i kanału obecne w istniejącej
  fixture. Przed eksportem potrzebny jest poprawny kontrakt metadanych.
- Jednostki wartości, orientacja i brakujące piksele wymagają dalszych decyzji.
  Zależności przyszłych funkcji wykraczają poza minimalny szkielet PyQt6.

Szczegóły faktów: [rozpoznanie kodu](reconnaissance.md). W tej sesji nie zmieniono
wspólnych modułów ani konfiguracji głównej.
