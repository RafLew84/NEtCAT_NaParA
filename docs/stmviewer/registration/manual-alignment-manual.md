# REG-01a — ręczna próba dopasowania pary

Ticket: [REG-01a](issues/01a-manual-alignment.md).
Wspólne zasady oceny i stałe pary: [protokół](manual-protocol.md).
Uruchom z katalogu `NEtCAT-viewer`, w środowisku `netcat`:

```bash
python -m stmviewer.main
```

## Start od zera i kierunki ruchu

1. Otwórz `tests/stmviewer/fixtures/registration/cpu.mpp` i wykonaj pełne
   **Rejestruj → Phase**. Wybierz klatkę 2, otwórz **Porównaj parę…**.
2. Wybierz **Zacznij od zera**. Oczekuj ΔX=0 i ΔY=0 px oraz widoku
   **Po dopasowaniu**. W nakładce 50/50 zobaczysz początkową rozbieżność.
3. Kliknij dwukrotnie **X+** i raz **Y−**. Oczekuj ΔX=2, ΔY=−1 px
   i pokrycia znaczników we wspólnym obszarze. Przełączaj **Odniesienie**,
   **Dopasowywana**, **Nakładka 50/50** oraz **Przełącz obrazy**.
4. Przełącz na **Przed dopasowaniem**, a następnie z powrotem na **Po**.
   Podgląd przed pokazuje zerowe przesunięcie, ale zachowuje ręczny szkic.
   Kolejny ruch przyciskiem sam przywraca widok **Po dopasowaniu**.
5. Zastosuj wynik jako B. Przejdź do pary 2→3, rozpocznij od zera,
   naciśnij trzy razy **X−** i dwa razy **Y+**. Oczekuj XY=(−3,+2) px.

+X przesuwa dopasowywany obraz w prawo, +Y w dół. Jeden krok to jeden
piksel oryginału; znaki opisują ruch obrazu, a nie fizyczny kierunek dryfu.
„Odniesienie” i „Dopasowywana” oznaczają obrazy; A/B to dwie próby dopasowania.

## Zoom, przeciąganie i stały podgląd

1. Podczas szkicu przybliż obraz kółkiem i przesuń wspólny widok przeciąganiem.
   Oczekuj niezmienionych liczb XY. Kółko i przeciąganie służą nawigacji.
2. Zanotuj XY, gamma oraz widoczną strukturę. Wykonaj jeden krok **X+**, potem
   **X−**. Obraz i kadr mają wrócić dokładnie do wcześniejszego stanu.
3. Powtórz dla Y, z gamma 1,7 oraz z wyłączonymi proporcjami pikselowymi.
   Jeden krok nadal oznacza piksel oryginału, nie piksel ekranu.
4. Przy warstwie **Odniesienie** naciśnij przycisk przesunięcia: odniesienie
   pozostaje nieruchome. Zobacz efekt w warstwie **Dopasowywana** lub nakładce.

Kontrast jest zamrożony dla oryginalnej pary. Wyświetlany kadr obejmuje pole
odniesienia; część przesuniętej klatki może wypaść poza niego. Białe obszary
oznaczają brak próbek, a nakładka obejmuje wspólne ważne piksele.

## Korekta próby, reset, odrzucenie i A/B

1. Zakończ poprzedni szkic przez **Zastosuj jako B** lub **Odrzuć edycję**.
   Dla pary 1→2 oblicz Phase i wybierz **Przypnij B jako A**.
2. Wybierz **Koryguj wybraną próbę**. Oczekuj startu od jej XY. Zmień XY,
   kliknij **Przywróć początek**: wracają skopiowane wartości, a nie (0,0).
3. Zmień XY ponownie i kliknij **Odrzuć edycję**. Poprzednio wybrana próba
   i jej obraz wracają; A i B zachowują dotychczasowe wyniki.
4. Ponów korektę, wykonaj celowo jeden krok i kliknij **Zastosuj jako B**.
   A zachowuje wynik Phase, B pokazuje wynik ręczny. Przełączaj A/B.
5. Sprawdź opis ręcznego wyniku: początkowe XY, źródło próby, łączna korekta,
   końcowe XY oraz „ustawione ręcznie — jakość nieoceniona”. Nie ma dziedziczonej
   pewności algorytmu. Ręczne B można przypiąć jako A i korygować ponownie.
6. W trakcie szkicu wybór A/B, przypinanie i uruchomienie obliczeń automatycznych
   są zablokowane. Warstwy, przed/po, zoom i gamma pozostają dostępne.

Ręczne B zastępuje poprzednie B; aby porównać je z wcześniejszym B, przypnij
wcześniejsze B jako A przed edycją. Próby istnieją tylko w sesji okna.
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
informację, że **Oblicz parę** zwraca zadaną wartość (2,4; −1,25) px.
Wykorzystuje obrazy cpu.mpp, ale nie oblicza przesunięcia Phase i nie służy
ocenie skuteczności rejestracji. Nie zmienia produkcyjnej aplikacji ani plików.

1. Kliknij **Oblicz parę**, następnie **Przypnij B jako A**.
2. Kliknij **Koryguj wybraną próbę**, potem **X+** i **Y−**.
   Oczekuj XY=(3,4; −2,25) px. Ułamki są zachowane, krok nadal wynosi 1 px.
3. **Przywróć początek** daje (2,4; −1,25). **X−**, **Y+** dają (1,4; −0,25).
4. Zastosuj jako B i przełącz A/B. A ma początkowe ułamkowe XY; B opisuje
   ręczną korektę (−1,+1), bez oceny jakości. Zamknij okno wzorca.

## Brak pokrycia, błędy metod i życie szkicu

1. W zwykłej aplikacji, na cpu.mpp, rozpocznij od zera i przesuń obraz
   poza pole odniesienia (co najmniej szerokość lub wysokość obrazu kroków).
   Oczekuj informacji **Brak wspólnego ważnego obszaru**. Można zastosować
   taką diagnostyczną próbę; opis braku pokrycia pozostaje widoczny.
2. W osobnym szkicu użyj **Przywróć początek**, aby wrócić do pokrycia.
3. Wybierz Deep Matcher bez lokalnych wag. Mimo niedostępności obliczeń
   automatycznych **Zacznij od zera** nadal działa bez GPU i modelu.
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
nie zastępują ręcznej oceny obrazu. Następny REG-02 czeka na ten odbiór.
