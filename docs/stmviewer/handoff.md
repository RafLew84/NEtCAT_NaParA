# Przekazanie — mapa pierwszej wersji STM Viewer

Data: 2026-10-14
Gałąź: `viewer/start`
Baza: `0e8bc53`
Commit dokumentacji: identyfikator w końcowej wiadomości sesji.

## Wynik

Utworzono [mapę pierwszej wersji](map.md), sześć otwartych ticketów decyzyjnych,
[słownik](GLOSSARY.md) i [rozpoznanie kodu oraz środowiska](reconnaissance.md).
Zapisano pierwszą rundę odpowiedzi użytkownika. Żaden ticket nie został
rozwiązany ani zamknięty; nie rozpoczęto implementacji aplikacji.

Pierwszy dostępny ticket: **Seria wejściowa i usuwanie klatek**.
Po nim zależności prowadzą do podglądu/rejestracji, eksportu i odbioru.
Reguły wyboru i przejęcia ticketu opisuje [README](README.md).

## Wykonane sprawdzenia

- Przegląd instrukcji, stanu Git, kodu NanoTrack/NaParA oraz istniejących testów.
- Importy wymaganych bibliotek w lokalnej condzie netcat i odczyt fixture STP.
- Kontrola lokalnych linków dokumentacji, kompletności zależności ticketów
  i `git diff --check` przy przygotowaniu przekazania.

Nie wykonywano testów aplikacji, GUI, eksportu ani oceny jakości rejestracji.
Stan i ograniczenia rozpoznania opisuje osobny dokument.

## Wspólne zmiany do rozważenia przez sesję integracyjną

- Czytnik STP pomija warianty nazw pól offsetu i kanału obecne w istniejącej
  fixture. Przed eksportem potrzebne jest uzgodnienie kontraktu metadanych.
- Kontrakt jednostek wartości, orientacji i brakujących pikseli wymaga decyzji
  przed ustaleniem zmian współdzielonych czytników/modeli.
- Zależności nowych funkcji wykraczają poza minimalny szkielet PyQt6.
  W tej sesji nie zmieniono wspólnych modułów ani konfiguracji głównej.
