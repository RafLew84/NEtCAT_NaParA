# Przegląd ticketu 12 — zapis original MPP

Data: 2026-10-23. Baza:
`7756c3d6e018ad1820f7400dc2d606b49d0975f2`.
Implementacja `678269f`, poprawki przeglądu `e24e560`.
Początkowy diff: `git diff 7756c3d...678269f`; ponowny przegląd:
`git diff 678269f..e24e560`.

Dwie osie sprawdzili równolegle niezależni agenci skillu `code-review`,
tylko do odczytu, bez uruchamiania testów. Poniżej ustalenia i osobno wynik
sprawdzenia poprawek. Końcowe statusy i wyniki dopisano po przeglądzie.

## Standards

Twarde naruszenia udokumentowanych standardów: brak.

Zmiany pozostają w zakresie `stmviewer/`, jego testów i dokumentacji,
zgodnie z `stmviewer/AGENTS.md`. Kod eksportera, obsługa wątku i integracja
GUI mają osobne odpowiedzialności. Testy sprawdzają publiczny eksport/import
oraz kontrolki GUI; obejmują niezależne oczekiwania bajtowe. Instrukcja ręczna
podaje dostępne dane i odróżnia automatyczne próby Qt od odbioru użytkownika.

Potencjalny zapach — **Duplicated Code**, drobna heurystyka: reguła
`path.with_name(path.name + '.stmviewer.json')` była powtórzona w importerze,
eksporterze i GUI. Zalecenie: jeden helper w module metadanych, aby odczyt,
zapis i potwierdzenie nadpisania korzystały z tej samej reguły.
Nie był to blocker ani stwierdzony błąd zachowania.

Ponowny przegląd `e24e560`: uwaga zamknięta. Wszystkie miejsca używają
`mpp_sidecar_path`. Brak nowych naruszeń standardów lub istotnych zapachów.
Ograniczenie tekstu nagłówka jest uzasadnione kontraktem czytnika, a test
obejmuje publiczny zapis i odczyt z zachowaniem pełnego tekstu w JSON.

Źródła: `AGENTS.md`, `stmviewer/AGENTS.md`, `docs/PARALLEL_DEVELOPMENT.md`,
indeks implementacji, słownik i katalog heurystyk Fowlera ze skillu.
Nie znaleziono odrębnych CODING_STANDARDS/CONTRIBUTING.

**Standards: początkowo 0 naruszeń i 1 drobna heurystyka; 0 otwartych uwag.**

## Spec

Początkowy przegląd: **1 ustalenie P2**.

Poprawne metadane V1 mogły dać film, którego Viewer nie otworzy.
Wymagania: „Eksporter wytwarza parę zgodną z już działającym importerem
dodatku” oraz „Ponowny odczyt w STM Viewer ma dawać tę samą orientację,
wymiary, wartości”. Eksporter kopiował wspólny kanał/jednostkę do pojedynczych
linii nagłówka bez limitu, choć czytnik odrzuca linie powyżej 65 536 bajtów.
Importer JSON dopuszcza dłuższy tekst w limicie dodatku 64 MiB. Eksport
mógł więc zakończyć się sukcesem, a ponowne otwarcie błędem długości nagłówka.

Poprawka `e24e560`: do nagłówka trafia tekst do 65 000 bajtów UTF-8, z zapasem
na prefiks i koniec linii. Dłuższy tekst dostaje wartość umowną w nagłówku;
pełna treść pozostaje w JSON. Test z 40 000 znaków Ω w obu polach (80 000
bajtów UTF-8) odtworzył błąd przed poprawką i przeszedł po niej.

Ponowny przegląd: ustalenie P2 zamknięte; brak nowych problemów Spec.
Wydzielenie ścieżki dodatku zachowuje dotychczasowy kontrakt. Poza powyższym
nie znaleziono brakujących wymagań ani rozszerzenia zakresu etapu 12.
Ochrona wcześniejszej pary, wartości/metadane, cała seria original oraz
blokady GUI odpowiadają specyfikacji.

Źródła: [ticket 12](issues/12-original-mpp.md),
[decyzja 04](../issues/04-mpp-export.md#answer),
[decyzja 06](../issues/06-acceptance.md#answer),
[kontrakt V1](../mpp-metadata-format.md), słownik i zasady odbioru.

**Spec: początkowo 1 P2; 0 otwartych ustaleń.**

Wyniki testów i status ręcznego odbioru: [przekazanie](../handoff.md).
