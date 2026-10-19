# Przekazanie — podgląd i odtwarzanie STM Viewer

Data: 2026-10-19
Gałąź dokumentacji: `viewer/start`
Baza bieżącej zmiany: `e46b5e5`
Prototyp: `prototype/stmviewer-preview-playback`, commit `bf8e849`.
Commit dokumentacji: identyfikator w końcowej wiadomości sesji.

## Wynik

Rozstrzygnięto [Podgląd, gamma i odtwarzanie serii](issues/02-preview-playback.md)
po ocenie działającego prototypu. Użytkownik wybrał wariant B z paskiem miniatur
i potwierdził przedstawione zasady odtwarzania, gamma, zoomu i brakujących pikseli.
Ticket ma status `resolved`. Zaktualizowano [mapę](map.md), [słownik](GLOSSARY.md)
oraz kontekst decyzji rejestracji i AVI.

[Źródło prototypu i instrukcja uruchomienia](preview-playback-prototype.md)
pozwalają odtworzyć wszystkie trzy warianty. Kopia dostępna lokalnie w
`.scratch/preview-playback-prototype/preview_playback_prototype.html` została
otwarta w przeglądarce. Gałęzi prototypu nie należy scalać do aplikacji.

Na `viewer/start` zmienia się wyłącznie dokumentacja. Aplikacja PyQt6 nadal
pozostaje szkieletem; implementacja uzgodnionych funkcji jest późniejszym etapem.

Następny dostępny ticket:
[Rejestracja i życie wyniku aligned](issues/03-registration.md).

## Wykonane sprawdzenia

- Uruchomienie HTML w Qt WebEngine, bez błędów JavaScript; podgląd A/B/C,
  aligned i zwężonego okna, z wizualną kontrolą lokalnych zrzutów.
- Sprawdzenie Play na ostatniej klatce, ręcznej pauzy, zachowania pochodzenia
  po odwróceniu, usuwania do pustej serii, ponownego wczytania i Stop na końcu.
- Ocena prototypu przez użytkownika i zapis trzech odpowiedzi.
- Kontrola lokalnych linków, statusów i zależności ticketów oraz `git diff --check`.

Nie dodano testów automatycznych prototypu. Nie uruchamiano produkcyjnego GUI
ani zestawu testów aplikacji. Nie sprawdzano dużych serii, eksportu ani jakości
rejestracji; aligned w prototypie jest kontrolowaną symulacją.

## Wspólne zmiany do rozważenia przez sesję integracyjną

- Obecny `ViewerWidget` wypełnia NaN medianą w kopii do wyświetlania. Przy jego
  ponownym użyciu trzeba zapewnić osobną prezentację maski brakujących pikseli
  (szachownicę) i granic oryginalnej klatki bez zmiany wartości pomiarowych.
  Miejsce realizacji — adapter STM Viewer lub zmiana wspólnego widgetu —
  należy ustalić przy implementacji. Wspólnych modułów nie zmieniono.

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
