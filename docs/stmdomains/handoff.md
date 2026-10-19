# STM Domains — przekazanie definicji statystyk klatek

Data: 2026-10-19.
Gałąź zadania: `domains/frame-statistics`, baza `ed5da11`.
Docelowa gałąź aplikacji: `domains/start`.
Commit przypisania: `f873363`; commit rozstrzygnięcia podany w końcowej wiadomości.
Praca w osobnym worktree `/tmp/netcat-stmdomains-frame-statistics`;
przeniesienie do worktree Domains przez scalenie commitów po kontroli czystości.

## Zakres i wynik

Rozstrzygnięto [definicje statystyk klatek](issues/06-frame-statistics.md)
na podstawie odpowiedzi użytkownika. Ticket ma status `resolved` i zawiera
kanoniczne definicje, wzory, stany wyniku oraz przykład rachunkowy.

- Dwa udziały powierzchni typu: względem oryginalnego pola klatki i względem
  warstwy molekularnej. Padding pozostaje poza pomiarem; nieznany typ nie
  zmniejsza znanego mianownika warstwy.
- Liczenie molekuł według środka bieżącego bboxa, z typem przejętym z domeny.
  Mianownikiem są wszystkie poprawne oznaczenia ze środkiem w polu, także bez
  typu. Brak maski SAM nie zmienia tej reguły.
- Wyniki częściowe, brak/zero, nieznany typ i przyczyny nieprzypisania pozostają
  jawne. Wyspy i rozpoznane fragmenty domen mają odrębne liczebności; fragmenty
  przy brzegu uwzględniamy w widocznym zakresie.
- Domyślnie sporny wspólny obszar domen jest niejednoznaczny. Użytkownik może
  wskazać jedną z propozycji dla konkretnego konfliktu; korekta jest oznaczona,
  a powierzchnie i przypisania przeliczane.
- Tabela i wykres osobno dla wybranych klatek. Bez średnich/sum serii,
  śledzenia obiektów i zgadywania czasu lub kalibracji.

Zaktualizowano słownik, mapę metod, indeks, README oraz pytania o zapis i odbiór
metod. Odbiór metod zależy teraz także od statystyk; diagram odzwierciedla zmianę.
Dołączono [schemat przykładu](assets/frame-statistics-example.svg).
To specyfikacja etapu 2, nie implementacja obliczeń ani interfejsu.

## Wykonane sprawdzenia

- Audyt tylko do odczytu istniejących statystyk MolTrack. Eksport Domain Analysis
  liczy unię masek/ramek molekuł; starszy footprint orientacyjny używa ograniczonego
  Voronoia. Żadna miara nie stała się automatycznie powierzchnią płata STM Domains.
  Źródła i różnice opisano w tickecie.
- Sprawdzenie rachunków: rozłączność i sumy obszarów schematu, oba udziały,
  liczebności, zachowanie unii przy konflikcie i konwersja px² → nm².
- Kontrola wizualna SVG, lokalnych odnośników, statusów, grafu zależności
  i `git diff --check` przed commitem.

Nie uruchamiano testów aplikacji ani metod wykrywania: kod aplikacji nie był
zmieniany. Nie oceniano powierzchni/klasyfikacji na referencjach TTMAPP.
Kontrolny schemat i rachunki nie są walidacją skuteczności algorytmu.

## Następne kroki

Pierwsza mapa nadal prowadzi do szkieletu, a jej następne pytanie to
[podgląd obrazów i oznaczeń](issues/07-browsing-and-comparison.md). Wcześniejsze
wykonanie definicji, pilotażu i obecnych statystyk wynikało z bezpośrednich
poleceń użytkownika, nie z odbioru szkieletu.

[Referencje jakości](issues/04-reference-and-quality.md),
[pokrycie](issues/10-coverage-and-scale.md),
[katalog typów](issues/11-structural-type-catalogue.md),
[granice domen](issues/12-phase-boundaries.md),
[odbiór metod](issues/13-method-acceptance.md) i
[zapis wyników](issues/08-save-and-export.md) pozostają otwarte.
Manualne rozstrzygnięcie konfliktu jest wymaganiem do późniejszego UI analizy
oraz trwałości wyniku, bez rozszerzania podstawowego podglądu pierwszego etapu.

## Zachowany kontekst poprzednich prac

[Kontrakt importu](issues/01-import-and-geometry.md),
[audyt geometrii](import-geometry-audit.md) i
[definicje wysp/typów/domen](issues/02-order-types-and-domains.md) pozostają aktualne.
Przekazania wcześniejszych zadań są w commitach `3c7c680`, `af7888e` i `ed5da11`.

[Pilotaż metod](method-comparison-pilot.md) nie wybrał algorytmu do aplikacji.
Jego źródła pozostają na `prototype/stmdomains-method-comparison`, commit
`f9ea1d602a8c2bcd1bc5eb410765706d2ae43fca`; nie scalać tej gałęzi do aplikacji.
Lokalny HTML: `/home/rlew/projekty/NEtCAT-domains/.scratch/method-comparison/pilot.html`.
Wynik inspekcji prototypu oraz sześciu dawnych testów importu dotyczy poprzednich
zadań; nie przedstawiamy ich jako sprawdzeń obecnej zmiany.

Zgłoszenia integracyjne pozostają aktualne: dobór czasów do wybranych klatek
MolTrack, walidacja duplikatów i shape masek, zachowanie przy zmienionym mtime
oraz koszt pełnej materializacji masek. Adapter STM Domains może powstać bez
czekania na wspólne poprawki. Dawne zgłoszenie odwracania STP/S94 w NanoTrack
jest poza zakresem importera z jednym MPP. Nie powstała nowa wymagana zmiana
współdzielonego kodu ani konfiguracji.
