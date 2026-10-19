# STM Domains — przekazanie prototypu podglądu

Data: 2026-10-19.
Gałąź dokumentacji: `domains/browsing-contract`, baza `1a81bc7`.
Docelowa gałąź aplikacji: `domains/start`.
Commit przypisania: `d44c859`; commit dokumentacji podany w końcowej wiadomości.
Worktree dokumentacji: `/tmp/netcat-stmdomains-browsing-contract`.
Przeniesienie dokumentacji do Domains przez scalenie commitów po kontroli czystości.

## Zakres i stan decyzji

Przygotowano [prototyp podstawowego podglądu](issues/07-browsing-and-comparison.md):
trzy układy na rzeczywistych obrazach, ramkach, maskach i zapisanej rejestracji
TTMAPP. **Ticket pozostaje `claimed`; czeka na reakcję i wybór użytkownika.**
Nie przyjęto jeszcze układu ani nowych zasad nawigacji. Obowiązuje wcześniej
uzgodniony kontrakt importu.

- A: boczna lista klatek i jeden przełączany podgląd.
- B: oryginał i zapisane wyrównanie tej samej klatki obok siebie.
- C: jeden podgląd i dolny pasek miniatur.

Wspólne funkcje prototypu: zoom, gamma, ramki/maski/granica pola, nawigacja,
play/pauza ze zmianą szybkości oraz jawne stany braków danych. Dialogi
otwierania i naprawy ścieżki symulują zaakceptowany wcześniej kontrakt.
Zaktualizowano ticket, README i mapę o stan prac oraz materiał do wyboru.

## Artefakty i sposób obejrzenia

Źródła prototypu: gałąź `prototype/stmdomains-browsing`, commit
`d9c7eb8f22724fcd0a5dd6517bdbceb19078dfbd`, katalog `stmdomains/prototypes/`.
Instrukcja odtworzenia jest w `README.md` tego katalogu. Worktree źródeł:
`/tmp/netcat-stmdomains-browsing-prototype`.
**Nie scalać gałęzi prototypu do aplikacji.**

Lokalny HTML do otwarcia w przeglądarce:
`/home/rlew/projekty/NEtCAT-domains/.scratch/browsing-prototype/index.html`.
Dolne strzałki wybierają wariant; lista „Przykład stanu” wybiera brak masek,
ramek, rejestracji, pojedynczą klatkę lub pusty start. Przycisk „Otwórz zapis…”
pokazuje symulowane przejścia importu. Bez serwera i połączenia z siecią.
Metadane, zrzuty i log inspekcji są obok HTML; dane i wyniki poza Git.

## Wykonane sprawdzenia i ograniczenia

- Generator uruchomiono na pełnej parze TTMAPP: 268 klatek, 52 494 ramki,
  11 993 maski. SHA-256 zgadzają się z audytem importu. Maski dekodowane
  pojedynczo. Przygotowanie około 5,72 s, szczyt RSS 554,2 MiB, HTML 53,5 MiB.
- Inspekcja QtWebEngine w oknie 1100 × 760: A/B/C, nakładki i braki,
  pojedyncza klatka, pusty start, przejścia symulowanego importu, gamma/zoom,
  podświetlenie ramki, play/pauza i zatrzymanie na końcu. Anulowanie i błędny
  zapis zachowują poprzednią serię oraz klatkę. Brak błędów JS i poziomego
  przepełnienia; kontrola wizualna zrzutów trzech wariantów.
- Kontrola lokalnych linków dokumentacji i `git diff --check` przed commitem.

Nie zmieniono kodu aplikacji ani współdzielonych modułów; nie uruchamiano
ich testów. Nie jest to odbiór natywnego GUI ani importera. Symulacja dialogów
nie sprawdza prawdziwego wskazywania i walidowania nowych źródeł. Nie oceniano
jakości rejestracji ani metod wykrywania. Normalizacja percentylami 2–98 na
klatkę i PNG 8-bit służą szkicowi; nie ustanawiają polityki intensywności
programu. Miary kosztu generatora nie opisują wydajności aplikacji.

## Co pozostało

Najpierw reakcja użytkownika na prototyp, ewentualna korekta, a następnie
zapis przyjętego układu i zachowań w `Answer` pytania o podgląd. Dopiero wtedy
można zamknąć tę decyzję i przejść do
[przekazania szkieletu do implementacji](issues/09-implementation-handoff.md).
Kod produkcyjny nadal zawiera tylko startowe okno PyQt6.

Dalsze referencje i próby metod oraz zapis wyników pozostają w etapie 2.
Ten prototyp nie obejmuje domen, statystyk ani ręcznej korekty ich konfliktów.

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
