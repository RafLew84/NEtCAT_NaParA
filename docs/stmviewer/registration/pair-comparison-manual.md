# REG-01 — ręczna próba porównania par

Uruchom w środowisku `netcat`, z katalogu `NEtCAT-viewer`:

```bash
python -m stmviewer.main
```

Ticket: [REG-01](issues/01-pair-comparison.md).
Wspólne zasady oceny i stałe pary: [protokół](manual-protocol.md).
To narzędzie porównania; metody rejestracji zachowują dotychczasowe algorytmy.

## Podgląd i przełączniki

1. Otwórz `tests/stmviewer/fixtures/registration/cpu.mpp`.
   Wykonaj zwykłe **Rejestruj → Phase**, aby istniał pełny aligned.
2. Wybierz klatkę 2 i naciśnij **Porównaj parę…**. Osobne okno pokazuje
   źródła pary 1→2. Numer w oknie oznacza klatkę dopasowywaną do poprzedniej;
   przy wybranej pierwszej klatce głównego okna startujemy od pary 1→2.
3. Przed obliczeniem obejrzyj **Odniesienie**, **Dopasowywana** i
   **Nakładka 50/50**. Przycisk **Przełącz obrazy**
   umożliwia ręczne naprzemienne oglądanie dwóch obrazów.
4. Wybierz Phase i **Oblicz parę**. Oczekuj ΔX=+2 px i ΔY=−1 px.
   Przełącz **Przed dopasowaniem / Po dopasowaniu**: po dopasowaniu kontury
   znaczników we wspólnym obszarze powinny się pokrywać.
5. Sprawdź parę 2→3: ΔX=−3 px, ΔY=+2 px. Są to przesunięcia nałożone na
   następną klatkę względem poprzedniej, a nie skumulowane względem pierwszej.

Kadr porównania zawsze obejmuje **pole oryginalnej klatki odniesienia**.
Część przesuniętej klatki poza tym polem jest w tym podglądzie niewidoczna.
Nie jest usuwana z pełnego aligned ani eksportu. Stały kadr zapobiega
pozornemu ruchowi powodowanemu zmianą paddingu lub dopasowaniem każdego wyniku
osobno do okna. Można używać kółka, przeciągania oraz przycisków +/−/Dopasuj.

Kontrast jest wspólnym zakresem minimum–maksimum skończonych próbek obu
oryginałów, zamrożonym dla pary. Gamma i proporcje są wspólne dla A/B.
Domyślnie włączone są proporcje pikselowe; po wyłączeniu podgląd korzysta
z proporcji fizycznych klatki odniesienia, jeśli są znane.
Nakładka 50/50 obejmuje tylko wspólne ważne próbki; reszta jest biała.
Panel podaje ich liczbę/udział i wyjaśnia całkowity brak części wspólnej.

## Porównanie A/B

1. Dla tej samej pary wykonaj Phase i kliknij **Przypnij B jako A**.
2. Przybliż rozpoznawalną strukturę, przesuń widok i ustaw gamma, np. 1,7.
3. Wybierz Optical Flow lub inną dostępną metodę i kliknij **Oblicz parę**.
   Sam wybór metody nie zastępuje wcześniejszego wyniku.
4. Przełącz **A — przypięta / B — ostatnia**. Przy warstwie Odniesienie
   obraz ma pozostawać nieruchomy i identyczny; nie zmieniają się zoom,
   punkt zakotwiczenia ani kontrast. Przy Dopasowywana/Nakładka zmienia się
   jedynie dopasowanie wynikające z wybranej próby.
5. Sprawdź nazwę metody, XY, stan backendu, urządzenie i ustawienia zapisane
   z każdą próbą. „OK backendu” nie oznacza niezależnej oceny jakości.
6. Zmień numer pary: stare A/B zostają wyczyszczone. Udany nowy import lub
   usunięcie klatki zamyka porównanie; ponowne otwarcie nie przywraca starych prób.
   Nieudany import zachowuje poprzednią serię i pasujące do niej próby.

Próby są lekkie i przechowywane tylko w tej sesji okna, bez zapisu na dysku.
Zamknięcie porównania usuwa A/B. Żadna próba pary nie podmienia pełnego aligned.

## Oba pomiary i błędy metod

Otwórz kolejno `data/MOVIE_4.mpp` i `data/MOVIE_8.mpp`.
Obejrzyj stałe pary z protokołu; zapisuj źródłowe numery i oglądane struktury.
Do porównania pojedynczej pary nie trzeba rejestrować całego filmu.
W MOVIE_8 1→2 obecny Phase daje około (−0,10; +0,05); narzędzie ma pokazać
istniejący problem, nie naprawić go w tym tickecie.

Dla próby ochrony pełnego wyniku najpierw wykonaj zwykłe Phase na filmie.
Następnie w porównaniu sprawdź znane błędy:

- MOVIE_8, para 2→3, ECC — błąd dopasowania.
- MOVIE_4, para 2→3, Deep Matcher — za mało zgodnych dopasowań cech.

Deep Matcher wymaga lokalnych wag; ich wybór i urządzenie są niezależne
w oknie próby, startowo skopiowane z głównego okna. Brak wag/bibliotek ma
widoczną przyczynę. Program niczego nie pobiera i nie zamienia metody.
[Przygotowanie Deep Matcher](../deep-matcher-manual.md).

Przed błędną próbą tej samej pary oblicz poprawny wynik inną metodą.
Po niepowodzeniu musi pozostać poprzedni wynik A/B z jego nazwą i obrazem;
osobny komunikat informuje o błędzie nowej próby. Główny aligned też pozostaje.

## Anulowanie i zamykanie podczas obliczeń

Gotowy lokalny wzorzec: `data/registration-pair-cancel.mpp` — dwie klatki
1536×1536, około 36 MiB; do nałożenia na drugą klatkę XY=(+7,−5).
Przygotowanie na innym komputerze:

```bash
python tests/stmviewer/make_pair_comparison_fixture.py
```

Generator odmawia nadpisania istniejącego pliku. W razie potrzeby można
wskazać nową ścieżkę i `--size 2048`. To wzorzec syntetyczny; wybierz proporcje
pikselowe. Pomiar lokalny realnego Optical Flow: około 8 s, bez sztucznych opóźnień.

1. Otwórz wzorzec i wykonaj pełne Phase. W porównaniu pary też oblicz Phase,
   przypnij A i zanotuj obraz oraz XY.
2. Wybierz Optical Flow, uruchom próbę i podczas obliczeń kliknij **Anuluj próbę**.
   Oczekuj komunikatu o anulowaniu i zachowania wcześniejszego A/B oraz aligned.
3. Powtórz, zamykając okno porównania klawiszem Escape lub krzyżykiem.
   Okno czeka na zakończenie bieżącego obliczenia, po czym bezpiecznie się zamyka.
4. Podczas pracy otwieranie nowej serii, jej usuwanie, eksport i druga
   rejestracja są zablokowane. Podgląd oraz zoom/gamma nadal są dostępne.

Anulowanie jest kooperacyjne: trwający backend kończy obliczenie pary,
a wynik zostaje odrzucony. Szybkie zakończenie sukcesem nie zalicza próby anulowania.

## Odbiór

[Karta REG-01](reviews/REG-01.md) zawiera wyniki automatyczne i osobny zapis
ręcznego odbioru. Użytkownik potwierdził „testy manualne ok” 2026-10-29;
REG-01 ma status `done`. REG-02 ma spełnioną zależność i czeka na zlecenie.
