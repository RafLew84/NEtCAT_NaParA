# STM Domains — zapis i eksport w trakcie ustaleń

Data: 2026-10-19.
Gałąź: `domains/save-export-contract`, baza `92e589d`.
Worktree: `/tmp/netcat-stmdomains-save-export-contract`.
Gałąź docelowa: `domains/start`. Claim: `2d5b995`.
Commit bieżących ustaleń podany w wiadomości końcowej.

## Przyjęte ustalenia

Na bezpośrednie polecenie użytkownika podjęto
[kontrakt zapisu i eksportu](issues/08-save-and-export.md) przed odbiorem metod.
Ticket pozostaje **`claimed`**. Odpowiedzi użytkownika zapisano w `Discussion`:

- Jeden samowystarczalny plik zawiera także obrazy MPP; ponowne otwarcie nie
  wymaga osobnego MPP ani pierwotnego zapisu MolTrack.
- Jeden wybrany wynik analizy na plik. Warianty ustawień przez „Zapisz jako”,
  bez historii wielu prób w jednym projekcie.
- Eksport tabel CSV, obrazów z nakładkami PNG i wykresów PNG.

Słownik uzupełniono o zapis pracy STM Domains, wynik analizy i eksport.
Nie zmieniono kodu aplikacji ani wspólnych modułów.

## Pytania oczekujące i dalszy zakres rozmowy

Wysłano pytania o odtwarzanie wyniku bez ponownego uruchamiania metod,
zachowanie poprzedniego wyniku podczas nowej próby oraz wybór pełnego obrazu
lub wycinka przy eksporcie PNG. Odpowiedzi jeszcze nie zapisano; nie należy
traktować rekomendacji jako przyjętych decyzji.

Po tych odpowiedziach pozostają do domknięcia szczegółowość tabel CSV,
powiązanie wyboru typu/tabeli/wykresu z obrazem oraz podsumowanie kontraktu.
Obowiązują wcześniejsze definicje powierzchni, braków danych i korekt
konkretnego konfliktu; nie trzeba ich ustalać od nowa.

Roboczy szkic technicznego kontraktu jest lokalnie w
`/tmp/netcat-stmdomains-save-export-contract/.scratch/save-export-contract-draft.md`.
Nie stanowi zatwierdzonego `Answer`. Zależność od odbioru metod pozostaje
w trackerze do rozstrzygnięcia zakresu końcowego kontraktu; odbiór metod
nadal jest otwarty. Nie przeniesiono prototypów do aplikacji.

## Sprawdzenia

Audyt lokalnego kodu tylko do odczytu: eksport Domain Analysis v9/v10,
identyfikacja źródła w UI, zapis MolTrack i kontener NanoTrack. Wnioski oraz
linki do kodu są w tickecie. Stary eksport M6 nie jest kontraktem Domains.
Hash nazwy/ścieżki nie identyfikuje bajtów obrazu; istniejący ZIP NanoTrack
pokazuje kontener, ale nadal wymaga obrazu zewnętrznego.

Kontrola lokalnych linków i `git diff --check` przed commitem. Nie uruchamiano
testów aplikacji, importera, eksportera ani metod. Nie powstał jeszcze plik
`.stmdomains`, serializer lub nowy interfejs zapisu. Integralność pakietu,
ponowne otwarcie i koszty na pełnej serii wymagają przyszłej implementacji.

## Dalszy tok prac

Dokończyć rozmowę i zapisać jej przyjęty wynik. Następne pytanie pierwszej mapy
nadal dotyczy [przekazania szkieletu do implementacji](issues/09-implementation-handoff.md).
Wcześniejsze podjęcie zapisu nie jest odbiorem szkieletu ani metod.

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
