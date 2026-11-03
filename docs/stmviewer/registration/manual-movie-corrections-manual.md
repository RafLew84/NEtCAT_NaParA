# REG-02a — ręczna korekta filmu: próba w GUI

Status: `done`; użytkownik potwierdził „testy manualne ok” 2026-10-31.
Poniższe kroki służą powtórzeniu próby; potwierdzenie nie wymienia osobno
każdego kroku ani platformy. [Ticket](issues/02a-manual-movie-corrections.md),
[karta sprawdzeń](reviews/REG-02a.md).

## Uruchomienie i podstawowy workflow

W katalogu `NEtCAT-viewer`, w środowisku `netcat`:

```bash
python -m stmviewer.main
```

1. Otwórz film i wykonaj **Rejestruj** w głównym oknie. Ręczne zastosowanie
   wymaga kompletnego aligned bieżącej serii.
2. Wybierz klatkę przesuwaną i **Porównaj parę…**. W lewym panelu znajdziesz
   sekcję **Korekta całego filmu**; przy małym oknie przewiń panel pionowo.
3. Kliknij **Popraw dopasowanie z filmu**. Punkt startu to aktualne XY tej
   pary, a nie skumulowane przesunięcie klatki względem pierwszej.
4. Użyj strzałek ±1 px. Nakładka, przełączanie obrazów, gamma i zoom służą
   ocenie przesunięcia. Ułamkowa część początkowego XY zostaje.
5. Kliknij **Zakończ korektę**. Powstaje wynik bieżący do porównania; film
   nadal ma dotychczasowe przesunięcia.
6. Sprawdź stare/nowe XY oraz zakres klatek w sekcji filmu i kliknij
   **Zastosuj do filmu**. Po sukcesie poprawiony aligned jest aktywny
   w głównym oknie i w eksporcie. Możesz zamknąć okno pary bez utraty korekty.
7. **Usuń korektę tej pary z filmu** przywraca automatyczne XY tej pary,
   zachowując pozostałe korekty. **Cofnij wszystkie ruchy** dotyczy wyłącznie
   bieżącego szkicu ręcznego.

Zmiana XY pary przesuwa jej drugą klatkę i wszystkie następne. Wcześniejsze
XY względem odniesienia nie zmieniają się. Nowy padding może przesunąć wszystkie
obrazy na płótnie. Przeliczanie korzysta z original, z jedną interpolacją.
Nowy aligned jest dopasowany do okna; gamma i wybrana klatka pozostają.

## Mały wzorzec z niezależnie znanymi liczbami

Otwórz `tests/stmviewer/fixtures/registration/cpu.mpp`, wykonaj Phase.
W głównym oknie sprawdzaj skumulowane XY dla kolejnych klatek:

| Działanie | Klatka 1 | Klatka 2 | Klatka 3 |
| --- | --- | --- | --- |
| Bazowe Phase | (0,0) | (2,−1) | (−1,1) |
| Para 1→2: X+ i zastosowanie | (0,0) | (3,−1) | (0,1) |
| Następnie para 2→3: Y+ i zastosowanie | (0,0) | (3,−1) | (0,2) |
| Usuń tylko korektę 1→2 | (0,0) | (2,−1) | (−1,2) |
| Usuń również korektę 2→3 | (0,0) | (2,−1) | (−1,1) |

Punkt startu pary 2→3 po pierwszej korekcie musi być `(−3,+2)`.
Powtórne zastosowanie zakończonej próby jest nieaktywne; aby edytować ponownie,
pobierz nowe **Popraw dopasowanie z filmu**. Sprawdź także wzorzec
`tests/stmviewer/fixtures/registration/subpixel.mpp`: po Phase zanotuj
ułamkowe XY, dodaj 1 px w jednej osi, zastosuj i usuń korektę. Część ułamkowa
pozostaje, a usunięcie odtwarza pierwotny wynik.

Zastosuj jedną korektę, zamknij okno pary, sprawdź Play, gamma i original/aligned.
Zapisz **MPP aligned** oraz **AVI aligned**, np. FFV1, 7 kl./s, pełną serię.
Otwórz MPP ponownie: próbki, geometria, białe braki i historia korekt są zachowane.
MPP zawiera już wyrównane piksele; nie odtwarza edytowalnej sesji z oryginałami.
Sprawdź AVI w VLC. Eksport original w pierwotnej sesji nadal zapisuje oryginały.

## MOVIE_4 — ocena jakości przez użytkownika

Otwórz `data/MOVIE_4.mpp`, usuń pierwszą klatkę dwukrotnie **przed** rejestracją.
Zostaje 362 klatek, źródłowe 3–364. Wykonaj Deep Matcher z lokalnymi wagami.
Jeśli nie uzyska kompletnego wyniku, zapisz błąd; funkcję można sprawdzić inną
metodą, ale nie jest to ocena jakości pełnego Deep Matcher.

Zacznij od bieżącej pary **29→30** (źródłowe **31→32**), dobierz XY wzrokowo,
zastosuj i obejrzyj przejście oraz dalszy film. Potem sprawdź bieżące
**35→36, 44–46, 61→62 i 94–97**. Odpowiadają źródłowym
**37→38, 46–48, 63→64 i 96–99**. Zanotuj poprawę/pogorszenie oraz tearing,
którego pojedyncze przesunięcie XY nie usuwa. Kierunek dryfu może się zmieniać.

## Anulowanie, błąd i aktualność korekty

- Podczas przeliczania użyj **Anuluj korektę filmu** w oknie pary lub głównym
  oknie. Poprzedni kompletny film i zastosowane korekty mają zostać; próbę można
  ponowić. Zmiany serii, obliczenia i eksport są zablokowane, podgląd dostępny.
- Przy rozpoczętym szkicu wykonaj nową pełną rejestrację. Po zakończeniu starej
  próby **Zastosuj do filmu** jest nieaktywne z wyjaśnieniem. Rozpocznij świeżą.
- Usuń klatkę po zastosowaniu korekt. Gotowy aligned i eksport pozostałych
  klatek zostają, a kolejna ręczna korekta wymaga nowej pełnej rejestracji.
- Udana rejestracja zastępuje ręczne poprawki; nieudana/anulowana zachowuje je.
  Nieudane otwarcie pliku także zachowuje film, udany import czyści jego stan.

Do powtarzalnej próby anulowania na małym CPU można uruchomić diagnostycznie:

```bash
PYTHONPATH=. python tests/stmviewer/diagnostics/manual_movie_gui_fault.py --delay 0.3
```

Do jednorazowego błędu przy renderowaniu drugiej klatki:

```bash
PYTHONPATH=. python tests/stmviewer/diagnostics/manual_movie_gui_fault.py --delay 0.3 --fail-at 2
```

Otwórz CPU, zarejestruj Phase i zastosuj ręczną korektę. Oczekuj błędu
alokacji, zachowania poprzedniego aligned i działającego ponowienia.
Skrypt zmienia wyłącznie interpolator tego procesu podczas ręcznej korekty;
normalny start aplikacji oraz pliki źródłowe pozostają bez zmian.
