# REG-04 — ręczne sprawdzenie Deep Matcher + ECC

Celem jest ocena, czy ECC poprawia wynik Deep na strukturach próbki.
Nie zakładamy poprawy; większy score ECC, mniejsza poprawka lub spokojniejszy
film nie rozstrzygają poprawności. Obowiązuje [wspólny protokół](manual-protocol.md).
[Wyniki wykonanych prób automatycznych](deep-ecc-results.md) są odrębne od
odbioru wizualnego użytkownika.

## Uruchomienie i wzorce

W katalogu `NEtCAT-viewer`, po aktywowaniu `netcat`:

```bash
PYTHONPATH=. python tests/stmviewer/make_deep_ecc_fixtures.py
python -m stmviewer.main
```

Generator zapisuje MPP i `manifest.json` w `/tmp/stmviewer-reg04-fixtures`.
Opcja `--output` zmienia katalog, również na Windows. Filmy mają 3 klatki
192 × 256 px, są wycinkami większej sceny i nie zawijają danych na brzegach.

| Film | Oczekiwane przesunięcie sceny do nałożenia na następną klatkę |
| --- | --- |
| `translation.mpp` | 1→2: (+22,4; −13,25), 2→3: (−41; +24,6) px |
| `periodic.mpp` | Te same przesunięcia sceny, lecz wzór powtarza się co 24 px; wiele dopasowań może mieć podobny score |
| `stationary-artifact.mpp` | Te same przesunięcia sceny z nieruchomymi pasami; jedno XY nie wyrówna jednocześnie sceny i pasów |

Wybierz lokalne wagi LoFTR outdoor i urządzenie Auto, CPU lub CUDA.
Wagi na obecnym stanowisku są w lokalizacji opisanej w
[instrukcji Deep Matcher](../deep-matcher-manual.md#lokalne-wagi-i-dane).
Aplikacja nie pobiera wag. Dla hybrydy Deep używa wybranego urządzenia,
a doprecyzowanie ECC działa na CPU.

## Dokładny start i wynik jednej próby

1. Otwórz `translation.mpp` i okno **Dopasowanie pary klatek**. Wybierz
   klatkę przesuwaną 2, metodę **Deep Matcher + ECC (v1)** i kliknij
   **Dopasuj automatycznie**.
2. Sprawdź **Start Deep**, **Wynik ECC** i **Poprawka ECC − Deep**. Wynik ECC
   jest końcowym XY, a nie poprawką do dodania drugi raz. Status mówi o
   potrzebie oceny; osobne score opisują tylko backendy.
3. Zmień listę **Wynik po ECC / Start Deep tej próby**. Powinien zmieniać się
   wyłącznie wybrany estymowany ruch. Nie następuje nowe obliczanie modelu.
   Kadr, zoom, gamma oraz kontrast pozostają wspólne. Oczekiwany wynik ECC
   na wzorcu jest blisko (+22,4; −13,25) px; tolerancja oględzin 0,2 px.
4. Użyj **Zachowaj do porównania**. Wykonaj kolejną próbę. Przełączanie
   **Wynik bieżący / Wynik zachowany** oraz startu/końca nie może nadpisywać
   zachowanego wyniku. Klatka bazowa, przesuwana i nakładka działają jak wcześniej.
5. Sprawdź parę 2→3 i oba pozostałe wzorce. Zanotuj rozbieżności nawet przy
   wysokim score. Dla wzorca okresowego wynik może być przesunięty o wielokrotność
   okresu; dla artefaktu oceń oddzielnie scenę oraz nieruchome pasy.

## MOVIE_4 i MOVIE_8

W MOVIE_4 usuń pierwszą klatkę dwa razy **przed** uruchomieniem rejestracji.
Zostają źródłowe 3–364. Numery poniżej rozdzielają bieżącą serię od źródła.

| Film | Bieżąca para | Para źródłowa |
| --- | --- | --- |
| MOVIE_4 | 1→2, 31→32, 118→119 | 3→4, 33→34, 120→121 |
| MOVIE_4, wskazania użytkownika | 29→30, 35→36, 44→45→46, 61→62, 94→95→96→97 | 31→32, 37→38, 46→47→48, 63→64, 96→97→98→99 |
| MOVIE_8 | 1→2, 16→17, 56→57 | Te same numery |

Dla każdej pary porównaj dokładny start Deep z końcem ECC przy gamma 1,
proporcjach pikselowych i wspólnym widoku. W co najmniej trzech rozpoznawalnych
fragmentach zanotuj **lepiej / podobnie / gorzej / niejednoznacznie**, początkowe
XY, poprawkę i końcowe XY. Resztkowe tearing opisz oddzielnie. Pełne numery,
pochodzenie i ustawienia są w szczegółach wyniku.

Następnie w głównym oknie wykonaj całą serię samym **Deep Matcher**, zapisz
aligned i powtórz dla **Deep Matcher + ECC (v1)** przy tych samych wagach
oraz urządzeniu. Nie ma potwierdzania każdej pary. Przebieg rozróżnia Deep
od ECC; na koniec pokazuje kompletny aligned. Sprawdź Play, zoom i gamma.
Główne okno pokazuje też historyczne dane automatycznej estymacji wybranej
pary, sprzed ewentualnej późniejszej korekty ręcznej.

## Błąd, anulowanie i eksport

Kontrolowaną odmowę lub opóźnienie ECC można uzyskać bez edycji aplikacji:

```bash
PYTHONPATH=. python tests/stmviewer/diagnostics/deep_ecc_gui_fault.py --fail-at 1
```

Najpierw zarejestruj wzorzec samym Deep, następnie uruchom hybrydę. Pierwsze
wywołanie ECC w tym procesie zwróci kontrolowany błąd. Komunikat ma wskazywać
parę i etap ECC; poprzedni aligned i jego korekty pozostają. Nie powstaje
ukończony wynik hybrydy. Kolejna próba może się udać, bo odmowa jest jednorazowa.

Dla anulowania uruchom osobno z `--delay 5`. Przerwij obliczanie podczas ECC.
Aplikacja czeka na powrót bieżącego wywołania biblioteki, po czym odrzuca całą
próbę. W głównym oknie zostaje poprzedni aligned. Uruchomienie zwykłym
`python -m stmviewer.main` nie ma tych kontrolowanych opóźnień ani odmów.

Sprawdź również brak wag: wyczyść ścieżkę lub wskaż nieistniejący plik.
Hybryda ma podać przyczynę niedostępności bez pobierania lub zmiany metody.

Na `translation.mpp` wykonaj kompletny aligned hybrydą, zapisz MPP z dodatkiem
i mały AVI. Otwórz MPP ponownie: zachowuje nazwę/wersję metody, XY, geometrię,
status i brakujące próbki. Obejrzyj AVI w VLC. W aplikacji popraw ręcznie jedną
parę przez **Popraw dopasowanie z filmu**, **Zakończ korektę**, **Zastosuj do filmu**;
sprawdź zmianę tej i dalszych klatek oraz eksport, zgodnie z
[instrukcją REG-02a](manual-movie-corrections-manual.md).

Decyzję o jakości i zachowaniu hybrydy wpisujemy w [karcie REG-04](reviews/REG-04.md).
