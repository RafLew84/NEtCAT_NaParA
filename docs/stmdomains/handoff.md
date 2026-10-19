# STM Domains — przekazanie kontraktu zapisu i eksportu

Data: 2026-10-19.
Gałąź: `domains/save-export-contract`, baza `92e589d`.
Worktree: `/tmp/netcat-stmdomains-save-export-contract`.
Gałąź docelowa: `domains/start`. Claim: `2d5b995`; pierwsze odpowiedzi: `560b00e`.
Commit rozstrzygnięcia podany w wiadomości końcowej. Przeniesienie przez
fast-forward do Domains po kontroli gałęzi, HEAD i czystości worktree.

## Przyjęty wynik

[Kontrakt zapisu i eksportu](issues/08-save-and-export.md) ma status `resolved`.
Jego `Answer` jest kanoniczną specyfikacją, opartą na trzech rundach odpowiedzi:

- Jeden samowystarczalny `.stmdomains` zawiera oryginalny MPP, oznaczenia,
  geometrię i podgląd. Zero lub jeden wynik; zapis także przed analizą.
- Otwarcie odtwarza zapisany wynik, automatyczną podstawę i korekty bez
  uruchamiania metod. Nowa próba zachowuje poprzedni wynik do zastąpienia;
  „Zapisz jako” pozwala zachować wariant. Korekty nie przechodzą na nową analizę.
- CSV: klatki, typy na klatkach, wyspy, fragmenty domen i przypisania molekuł.
  Jawne jednostki, liczniki/mianowniki, braki i korekty; bez sum/średnich serii.
- PNG: całość bieżącego widoku lub wycinek z gammą i nakładkami, oraz wykresy.
  Wybór typu podświetla obszary, a tabela i wykres wskazują klatkę podglądu.

Techniczna postać kontenera: wersjonowany ZIP z JSON, oryginalnym MPP i danymi
wyniku; identyfikacja rzeczywistych bajtów źródła i zapis przez podmianę gotowej
paczki. Dokładny schemat pól/tablic i adaptery powstaną przy implementacji.
Wymagane znaczenia danych i kryteria odtworzenia są już zapisane w tickecie.

Zaktualizowano słownik, README, mapę metod i indeks zależności. Uzgodnienie
kontraktu przed odbiorem metod wynika z bezpośredniego polecenia użytkownika.
Usunięto zależność pytania o zapis od odbioru metod i dodano odwrotną: odbiór
sprawdza kompletność/odtwarzalność danych metod względem przyjętego kontraktu.
Ticket odbioru metod pozostaje otwarty; nie wybrano algorytmu.

## Wykonane sprawdzenia

- Audyt lokalnego kodu tylko do odczytu: eksport Domain Analysis v9/v10,
  identyfikacja źródła w UI, zapis MolTrack i kontener NanoTrack. Wnioski
  i linki są w tickecie. Stary eksport M6 nie jest kontraktem Domains.
- Kontrola spójności z uzgodnioną geometrią/statystykami, lokalnych linków,
  statusów, zależności oraz diagramu, a także `git diff --check` przed commitem.

Nie zmieniono kodu aplikacji ani wspólnych modułów. Nie uruchamiano testów
aplikacji, importera, eksportera ani metod. Nie powstał serializer lub UI zapisu.
Kryteria przyszłego odbioru obejmują otwarcie przeniesionego pliku bez źródeł,
wynik bez modeli i bez przeliczania, geometrię/korekty/statystyki, zapisy przed
analizą, błędy/anulowanie, CSV/PNG oraz koszty na pełnej serii TTMAPP.
To wymagane sprawdzenia przyszłej implementacji, nie wyniki obecnych testów.

## Następne kroki

Pierwsza mapa nadal prowadzi do
[przekazania szkieletu do implementacji i jego odbioru](issues/09-implementation-handoff.md).
Własny zapis, analiza i powiązanie statystyk z podglądem rozwijają etap 2;
samo dopuszczenie zapisu przed analizą nie rozszerza obowiązków pierwszego etapu.

Pozostają referencje jakości, próby pokrycia/katalogu/granic oraz odbiór metod.
Próby mogą uzupełnić metadane konkretnego algorytmu, nie zastępują przyjętych
pojęć ani nie pozwalają gubić braków, korekt lub mianowników w zapisie.
Nie ma nowej wymaganej zmiany współdzielonego kodu ani konfiguracji.

## Zachowany kontekst poprzednich prac

[Kontrakt importu](issues/01-import-and-geometry.md),
[audyt geometrii](import-geometry-audit.md) i
[definicje wysp/typów/domen](issues/02-order-types-and-domains.md) pozostają aktualne.
Przekazania wcześniejszych zadań są w commitach `3c7c680`, `af7888e`, `ed5da11` i `1a81bc7`.
[Definicje statystyk](issues/06-frame-statistics.md) pozostają aktualne;
ręczne rozstrzyganie konfliktów domen należy do późniejszego UI analizy,
bez rozszerzania podglądu pierwszego etapu.

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

Wybór podglądu jest zakończony: [jeden obraz i pasek miniatur](issues/07-browsing-and-comparison.md),
commit dokumentacji `92e589d`. Źródła jego prototypu pozostają na
`prototype/stmdomains-browsing`, commit `cb51fbf04802620637dd7d10acc19863717de083`;
nie scalać do aplikacji. Lokalny HTML:
`/home/rlew/projekty/NEtCAT-domains/.scratch/browsing-prototype/index.html`.
