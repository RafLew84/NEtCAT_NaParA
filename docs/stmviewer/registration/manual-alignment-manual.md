# REG-01a — ręczna próba dopasowania pary

Ticket: [REG-01a](issues/01a-manual-alignment.md).
Wspólne zasady oceny i stałe pary: [protokół](manual-protocol.md).
Uruchom z katalogu `NEtCAT-viewer`, w środowisku `netcat`:

```bash
python -m stmviewer.main
```

Instrukcja odpowiada wybranemu układowi C: wyniki i metoda są po lewej,
podgląd po prawej, ręczne sterowanie pod obrazem. **Porównywanie dwóch
wyników jest opcjonalne** — ręczne dopasowanie można zakończyć bez użycia
„Zachowaj do porównania”. Wynik pozostaje w tym oknie i nie zmienia filmu.

## Start od zera i kierunki ruchu

1. Otwórz `tests/stmviewer/fixtures/registration/cpu.mpp` i wykonaj pełne
   **Rejestruj → Phase**. Wybierz klatkę 2, otwórz **Porównaj parę…**.
2. Wybierz **Ustaw ręcznie od zera**. Oczekuj ΔX=0 i ΔY=0 px oraz widoku
   **Z dopasowaniem**. W nakładce 50/50 zobaczysz początkową rozbieżność.
3. Kliknij dwukrotnie **X +1 →** i raz **↑ Y −1**. Oczekuj ΔX=2, ΔY=−1 px
   i pokrycia znaczników we wspólnym obszarze. Przełączaj **Klatka bazowa**,
   **Klatka przesuwana**, **Nakładka 50/50** oraz **Pokaż klatkę bazową / Pokaż klatkę przesuwaną**.
4. Przełącz na **Bez przesunięcia**, a następnie z powrotem na **Z dopasowaniem**.
   Widok bez przesunięcia pokazuje zerowe XY, ale zachowuje ręczny szkic.
   Kolejny ruch przyciskiem sam przywraca widok **Z dopasowaniem**.
5. Kliknij **Zakończ korektę**: nowe XY staje się wynikiem bieżącym.
   Przejdź do pary 2→3, rozpocznij od zera,
   naciśnij trzy razy **← X −1** i dwa razy **Y +1 ↓**. Oczekuj XY=(−3,+2) px.

+X przesuwa dopasowywany obraz w prawo, +Y w dół. Jeden krok to jeden
piksel oryginału; znaki opisują ruch obrazu, a nie fizyczny kierunek dryfu.
„Klatka bazowa” i „Klatka przesuwana” oznaczają obrazy. Karty „Wynik bieżący”
i „Wynik zachowany” oznaczają dwa dopasowania, każde z własną metodą i XY.

## Zoom, przeciąganie i stały podgląd

1. Podczas szkicu przybliż obraz kółkiem i przesuń wspólny widok przeciąganiem.
   Oczekuj niezmienionych liczb XY. Kółko i przeciąganie służą nawigacji.
2. Zanotuj XY, gamma oraz widoczną strukturę. Wykonaj jeden krok **X +1 →**, potem
   **← X −1**. Obraz i kadr mają wrócić dokładnie do wcześniejszego stanu.
3. Powtórz dla Y, z gamma 1,7 oraz z wyłączonymi proporcjami pikselowymi.
   Jeden krok nadal oznacza piksel oryginału, nie piksel ekranu.
4. Przy warstwie **Klatka bazowa** naciśnij przycisk przesunięcia: klatka bazowa
   pozostaje nieruchoma. Zobacz efekt w warstwie **Klatka przesuwana** lub nakładce.

Kontrast jest zamrożony dla oryginalnej pary. Wyświetlany kadr obejmuje pole
odniesienia; część przesuniętej klatki może wypaść poza niego. Białe obszary
oznaczają brak próbek, a nakładka obejmuje wspólne ważne piksele.

## Korekta wyniku, cofnięcie ruchów i opcjonalne porównanie

1. Zakończ poprzedni szkic przez **Zakończ korektę** lub **Anuluj korektę**.
   Dla pary 1→2 wybierz Phase, kliknij **Dopasuj automatycznie**, a następnie
   **Zachowaj do porównania**. Karta „Wynik zachowany” pokazuje kopię wyniku Phase.
2. Wybierz **Popraw wybrany wynik ręcznie**. Oczekuj startu od XY wybranego wyniku. Zmień XY,
   kliknij **Cofnij wszystkie ruchy**: wracają skopiowane wartości, a nie (0,0).
3. Zmień XY ponownie i kliknij **Anuluj korektę**. Poprzednio wybrany wynik
   i jego obraz wracają; obie karty zachowują dotychczasowe dopasowania.
4. Ponów korektę, wykonaj celowo jeden krok i kliknij **Zakończ korektę**.
   „Wynik zachowany” nadal pokazuje Phase, „Wynik bieżący” pokazuje wynik ręczny.
   Klikaj obie karty, aby porównywać dopasowania.
5. Wybierz kartę ręcznego wyniku i rozwiń **Szczegóły wybranego wyniku**.
   Sprawdź opis: początkowe XY, źródło próby, łączna korekta,
   końcowe XY oraz „ustawione ręcznie — jakość nieoceniona”. Nie ma dziedziczonej
   pewności algorytmu. Ręczny wynik bieżący można również zachować do porównania i korygować ponownie.
6. W trakcie szkicu wybór kart wyników, zachowywanie do porównania i obliczenia
   automatyczne tej pary są zablokowane. Warstwy, widok bez/z przesunięciem,
   zoom i gamma pozostają dostępne.

Zakończenie korekty zastępuje wynik bieżący. Aby porównać go z wcześniejszym,
użyj **Zachowaj do porównania** przed edycją. Ten przycisk zawsze kopiuje wynik
bieżący, także gdy oglądasz zachowany. Wyniki istnieją tylko w sesji okna.
Zapis na dysk obejmuje późniejszy REG-07.

## Powtarzalny przykład z ułamkowym początkiem

Uruchom osobne okno wzorca z katalogu repozytorium. Na Ubuntu:

```bash
PYTHONPATH=. python tests/stmviewer/manual_pair_fixture.py
```

W PowerShell, w przygotowanym środowisku Python:

```powershell
$env:PYTHONPATH = "."
python tests/stmviewer/manual_pair_fixture.py
```

Okno ma tytuł „wzorzec ułamkowego startu (wynik syntetyczny)” i wyraźną
informację, że **Dopasuj automatycznie** zwraca zadaną wartość (2,4; −1,25) px.
Wykorzystuje obrazy cpu.mpp, ale nie oblicza przesunięcia Phase i nie służy
ocenie skuteczności rejestracji. Nie zmienia produkcyjnej aplikacji ani plików.

1. Kliknij **Dopasuj automatycznie**, następnie **Zachowaj do porównania**.
2. Kliknij **Popraw wybrany wynik ręcznie**, potem **X +1 →** i **↑ Y −1**.
   Oczekuj XY=(3,4; −2,25) px. Ułamki są zachowane, krok nadal wynosi 1 px.
3. **Cofnij wszystkie ruchy** daje (2,4; −1,25). **← X −1**, **Y +1 ↓** dają (1,4; −0,25).
4. Kliknij **Zakończ korektę** i przełączaj karty wyników. Zachowany ma początkowe
   ułamkowe XY; bieżący opisuje ręczną korektę (−1,+1), bez oceny jakości.
   Opis rozwiń przez **Szczegóły wybranego wyniku**. Zamknij okno wzorca.

## Brak pokrycia, błędy metod i życie szkicu

1. W zwykłej aplikacji, na cpu.mpp, rozpocznij od zera i przesuń obraz
   poza pole odniesienia (co najmniej szerokość lub wysokość obrazu kroków).
   Oczekuj informacji **Brak wspólnego ważnego obszaru**. Można zastosować
   taki diagnostyczny wynik przez **Zakończ korektę**; opis braku pokrycia pozostaje widoczny.
2. Wróć przez **Cofnij wszystkie ruchy** przed zastosowaniem. Jeśli już zastosowano
   próbę bez pokrycia, wybierz **Ustaw ręcznie od zera**, aby wrócić do wspólnego pola.
3. Wybierz Deep Matcher bez lokalnych wag. Mimo niedostępności obliczeń
   automatycznych **Ustaw ręcznie od zera** nadal działa bez GPU i modelu.
4. Zmień parę podczas niezastosowanego szkicu: nowa para nie dziedziczy XY.
   Zamknij i otwórz okno — prób i szkicu nie przywracamy.
5. Podczas szkicu spróbuj wczytać uszkodzony plik. Po nieudanym imporcie
   poprzednia seria i szkic mają pozostać. Udany import lub usunięcie klatki
   zamyka porównanie i czyści niepasujące już próby.
6. Uruchom dłuższą rejestrację zgodnie z
   [próbą anulowania REG-01](pair-comparison-manual.md#anulowanie-i-zamykanie-podczas-obliczeń).
   Podczas pracy sterowanie ręcznym XY jest zablokowane. Po zakończeniu
   lub anulowaniu znów można rozpocząć ręczne dopasowanie.

## MOVIE_4, MOVIE_8 i ochrona pełnego aligned

W zwykłej aplikacji otwórz kolejno oba pomiary. Sprawdź stałe pary:

| Film | Pary źródłowe |
| --- | --- |
| `data/MOVIE_4.mpp` | 1→2, 33→34, 120→121 |
| `data/MOVIE_8.mpp` | 1→2, 16→17, 56→57 |

Spróbuj ręcznego startu od zera i korekty automatycznej próby. Obejrzyj
kilka struktur w różnych częściach obrazu. Zanotuj, gdzie jedno XY poprawia
pokrycie, a gdzie pozostaje rozbieżność. Kierunek dryfu może się zmieniać.
Ręczne dopasowanie nie naprawia deformacji wewnątrz klatki i nie jest dowodem
fizycznego dryfu. Sprawdź również możliwość startu po błędzie ECC na parze
2→3 MOVIE_8; Deep Matcher 2→3 MOVIE_4 sprawdzaj tylko z dostępnymi wagami.

Do sprawdzenia eksportu **ponownie otwórz cpu.mpp i wykonaj pełne Phase**.
Zanotuj jego wynik i wygląd aligned. Dopiero teraz zastosuj celowo inne XY
w ręcznej próbie pary. W głównym oknie aligned ma zachować wynik Phase.
Zapisz mały aligned do MPP+metadane i AVI, otwórz MPP w programie, a AVI
w VLC. Eksport ma nadal korzystać z pełnego Phase, bez ręcznej korekty pary.

Wyniki zapisz w [karcie REG-01a](reviews/REG-01a.md). Próby automatyczne Qt
nie zastępują ręcznej oceny obrazu. Użytkownik potwierdził „testy manualne ok”
2026-10-31 po wdrożeniu układu C; REG-01a ma status `done`, a REG-02 czeka
na osobne zlecenie.
