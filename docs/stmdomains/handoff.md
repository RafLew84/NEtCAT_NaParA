# STM Domains — przekazanie pilotażu metod i dalszych pytań

Data: 2026-10-19.
Gałąź dokumentacji: `domains/method-comparison`, baza `af7888e`.
Docelowa gałąź aplikacji: `domains/start`.
Commit przypisania: `73f31c2`; commit wyniku podany w końcowej wiadomości.
Osobne worktree: `/tmp/netcat-stmdomains-method-comparison` (dokumentacja)
i `/tmp/netcat-stmdomains-method-prototype` (prototyp).

## Zakres i wynik

Zakończono [pilotaż porównania metod w serii](issues/05-stable-types-across-frames.md)
ze wskazaniem konkretnych braków. Użytkownik wybrał katalog wspólny dla całego
zaznaczonego zakresu. Po otrzymaniu prototypu i wniosku polecił dopisać tickety
do dalszej analizy. Nie wybrano ani nie zwalidowano metody do aplikacji.

[Raport pilotażu](method-comparison-pilot.md) zawiera identyfikację wejść,
parametry i wyniki na ośmiu klatkach TTMAPP oraz czterech kontrolach syntetycznych.
Porównano pokrycie z centrów i Chan–Vese oraz cechy sąsiedztwa i lokalnego FFT.
Wykazano m.in. mieszanie różnego rozstawu w jednym typie, nadmierne podziały,
nieprawidłowy podział kontrolnej granicy i wrażliwość na skalę.

Źródła pozostają na `prototype/stmdomains-method-comparison`, commit
`f9ea1d602a8c2bcd1bc5eb410765706d2ae43fca`, w `stmdomains/prototypes/`.
**Nie scalać gałęzi prototypu do aplikacji.** Do `domains/start` trafiają
wyłącznie dokumentacja, rozstrzygnięcie i nowe pytania.

Lokalny plik do otwarcia bez serwera:
`/home/rlew/projekty/NEtCAT-domains/.scratch/method-comparison/pilot.html`.
Obok są wyniki przygotowania, inspekcji i zrzuty. HTML zawiera dane pomiarowe
i pozostaje poza Git; można go odtworzyć generatorem ze wskazanego commitu.

## Dalsze pytania i zależności

Dodano pytania o [pokrycie i skalę](issues/10-coverage-and-scale.md),
[typy struktury](issues/11-structural-type-catalogue.md),
[granice przy tym samym typie i orientacji](issues/12-phase-boundaries.md)
oraz [odbiór metod](issues/13-method-acceptance.md).

[Referencje i jakość](issues/04-reference-and-quality.md) pozostają otwarte
i blokują nowe próby oraz odbiór. Zależność przeniesiono z zakończonego
pilotażu do tych pytań, zgodnie z jego ograniczonym wynikiem. Kontrakt zapisu
zależy teraz od odbioru metod, nie od samego pilotażu wskazującego luki.
Zaktualizowano obie strony zależności w ticketach i diagramie rejestru.

Domyślny następny krok pierwszej mapy nadal stanowi
[podgląd obrazów i oznaczeń w szkielecie](issues/07-browsing-and-comparison.md).
Wcześniejsze wykonanie definicji i pilotażu było bezpośrednim poleceniem
użytkownika, a nie uznaniem szkieletu za odebrany. Nowych pytań nie wykonywano.

## Wykonane sprawdzenia

- Generator uruchomiony w lokalnym `netcat`: odtworzone wejścia, dwie skale
  cech/masek, kontrole syntetyczne, czasy i szczyt RSS procesu. Około 5,54 s
  i 596,5 MiB obejmuje wczytany MPP i JSON, nie samą analizę.
- Lokalna inspekcja QtWebEngine: powtórzenie dało identyczne przypisania
  i komponenty; anulowanie zachowało poprzedni wynik. Zmiana zakresu wymaga
  nowego katalogu, pusty zakres nie uruchamia próby. Sprawdzono raw/aligned,
  gamma, brak oznaczeń, nakładki i scenariusze prowadzone, bez błędów JavaScript.
- Wizualna kontrola zrzutów prototypu. Kontrola lokalnych linków, zależności
  i `git diff --check` przed commitem dokumentacji.

Nie uruchamiano testów produkcyjnej aplikacji, która nie była zmieniana.
Nie badano pamięci przeglądarki, całych 268 klatek, innych akwizycji ani
anulowania przygotowania cech. Bez referencji TTMAPP nie ma oceny trafności.
Chan–Vese nie jest implementacją Gibou–Fedkiwa. Rzadkie typy, defekty, małe
skupiska i ucięcia nadal wymagają kontrolowanych prób.

## Zachowany kontekst wcześniejszych prac i integracji

[Kontrakt importu](issues/01-import-and-geometry.md),
[audyt geometrii](import-geometry-audit.md) oraz
[definicje wysp, typów i domen](issues/02-order-types-and-domains.md) pozostają
aktualne. Poprzednie przekazania są w commitach `3c7c680` i `af7888e`.
Wynik sześciu istniejących testów importu dotyczy tamtego zadania, nie pilotażu.

Aktualne pozostają zgłoszenia: dobór czasów do wybranych klatek w odtwarzaczu
MolTrack, walidacja duplikatów i shape masek, zachowanie przy zmienionym mtime
oraz koszt pełnej materializacji masek. Adapter STM Domains może powstać bez
czekania na zmiany wspólnych modułów. Dawne zgłoszenie odwracania listy STP/S94
w NanoTrack jest poza zakresem importera z jednym MPP.
W obecnym zadaniu nie powstała wymagana zmiana współdzielonego kodu.
