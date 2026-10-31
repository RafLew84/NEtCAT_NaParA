# REG-02 — próba korelacji bez normalizacji

Ticket: [REG-02](issues/02-unnormalized-correlation.md).
Zapis wyników: [karta REG-02](reviews/REG-02.md).
Obowiązuje [wspólny protokół oceny](manual-protocol.md).

Z katalogu `NEtCAT-viewer`, w środowisku `netcat`:

```bash
python -m stmviewer.main
```

Metoda **Korelacja bez normalizacji (v1)** jest osobnym wyborem. Oblicza jedno XY
na parę z oryginalnych wartości; gamma, zoom i proporcje są ustawieniami
prezentacji. Start aplikacji nadal wybiera **Phase**. Wynik nowej metody ma
informację **pewność niezweryfikowana** — obliczenie XY nie jest jego niezależną
oceną jakości. Pierwsza klatka pełnej serii jest odniesieniem z XY=(0,0).

## Znane przesunięcia i porównanie w układzie C

1. Otwórz `tests/stmviewer/fixtures/registration/cpu.mpp`. W głównym oknie
   wybierz **Phase → Rejestruj**. Zanotuj nazwę, XY i wygląd pełnego aligned.
2. Wybierz klatkę 2 i **Porównaj parę…**. W oknie pary ustaw gamma 1,
   **Proporcje pikselowe** i **Nakładka 50/50**. Wybierz **Phase**,
   kliknij **Dopasuj automatycznie**, potem **Zachowaj do porównania**.
3. Wybierz **Korelacja bez normalizacji (v1) → Dopasuj automatycznie**. Oczekuj
   ΔX=+2 px, ΔY=−1 px. Przełączaj **Wynik zachowany / Wynik bieżący** oraz
   **Bez przesunięcia / Z dopasowaniem**. Z dopasowaniem rozpoznawalne znaczniki
   we wspólnym obszarze powinny się pokrywać.
4. Rozwiń **Szczegóły wybranego wyniku**. Nowy wynik ma własną nazwę,
   `normalization=None` oraz informację o niezweryfikowanej pewności; zachowany
   Phase ma wcześniejsze ustawienia i XY. Przybliż i przesuń wspólny podgląd,
   zmień gamma, przełączaj karty i warstwy. Wyniki XY pozostają bez zmian.
   Ponowne obliczenie nowego wariantu przy zmienionej gamma daje to samo XY.
5. Dla pary 2→3 powtórz porównanie: oczekiwane XY=(−3,+2).
   Zmiana pary czyści obie karty, więc wynik Phase zachowaj ponownie.
6. Zamknij okno pary. Główny aligned nadal pochodzi z Phase. Wybierz w głównym
   oknie **Korelacja bez normalizacji (v1) → Rejestruj**. Po sukcesie aligned pokazuje
   nową metodę. Przesunięcia skumulowane klatek 1–3 wynoszą kolejno
   **(0,0), (+2,−1), (−1,+1)**. Działają original/aligned, zoom, gamma i Play.

Próba pary służy porównaniu. Dopiero **Rejestruj** w głównym oknie tworzy nowy
pełny wynik używany przez eksport. Każde ponowienie korzysta z oryginałów,
a gotowy aligned jest zastępowany po sukcesie.

## MOVIE_4 i MOVIE_8 — jakość struktur

| Oryginalny film | Pary źródłowe, numery od 1 |
| --- | --- |
| `data/MOVIE_4.mpp` | 1→2, 33→34, 120→121 |
| `data/MOVIE_8.mpp` | 1→2, 16→17, 56→57 |

Dla każdej pary wykonaj Phase, zachowaj wynik, oblicz **Korelację bez
normalizacji**. Porównuj karty przy jednakowym kadrze, kontraście, gamma i zoomie.
Sprawdź przynajmniej trzy rozpoznawalne struktury w różnych częściach obrazu.
Zapisz XY obu metod oraz osobno dla fragmentów: **lepiej / podobnie / gorzej /
niejednoznacznie**. Opisz pozostałe rozbieżności góra–środek–dół i tearing.

W MOVIE_8 1→2 wcześniejszy wynik Phase to około (−0,10;+0,05), nowego wariantu
(+13,55;+0,25). Trzy znane fragmenty wskazują lokalnie około (+14,0):
prostokąty original `(180,160,260,240)`, `(350,320,430,400)` i `(90,330,170,410)`.
Oczekujemy zbliżenia nowego XY do tego lokalnego odniesienia (≤3 px w reproduktorze).
Obejrzyj też inne struktury; próg nie jest oceną całego filmu ani fizycznego dryfu.

Wykonaj również pełną rejestrację **obu filmów**, kolejno Phase i nowym wariantem.
Obejrzyj aligned podczas Play i na dodatkowych podejrzanych klatkach; zanotuj
przyczynę i parę, jeśli obliczenie nie dojdzie do końca. Mniejszy obszar aligned
lub spokojniejszy ruch same w sobie nie dowodzą poprawy. Jedno XY może poprawić
pokrycie części struktur, pozostawiając lokalne rozerwania; REG-02 nie koryguje
deformacji wewnątrz klatki.

## Anulowanie, błąd i zachowanie wcześniejszego wyniku

1. Po udanej pełnej rejestracji MOVIE_8 zanotuj nazwę, XY i wygląd aligned.
   Uruchom ponownie nowy wariant i podczas pracy kliknij **Anuluj rejestrację**.
   Oczekuj zakończenia obliczeń i zachowania poprzedniego wyniku. Obliczenie
   może zakończyć bieżący krok przed anulowaniem. Jeśli zdążyło zakończyć się
   sukcesem, próba anulowania nie została wykonana; powtórz na MOVIE_4.
2. Na MOVIE_8, po gotowym aligned nowego wariantu, wybierz **ECC → Rejestruj**.
   Znany błąd pary 2→3 powinien pokazać przyczynę i pozostawić wcześniejszy
   aligned. To kontrola ochrony wyniku przy błędzie innej metody.
3. W oknie tej samej pary 2→3 wykonaj nowy wariant i zachowaj do porównania,
   następnie spróbuj ECC. Po błędzie obie wcześniejsze karty i pełny aligned
   pozostają dostępne. Jeśli ECC w używanym środowisku zakończy się sukcesem,
   zapisz to — nie zalicza to scenariusza błędu.
4. Osobno otwórz `tests/stmviewer/fixtures/registration/flat.mpp` i uruchom
   nowy wariant. Oczekuj błędu braku tekstury, bez utworzenia wyniku z pozornym
   zerowym przesunięciem. Nowy import celowo zastąpi poprzednią serię.

## Mały eksport i ponowne otwarcie

1. Ponownie otwórz `cpu.mpp`, wybierz **Korelacja bez normalizacji (v1)** i wykonaj
   pełne **Rejestruj**. Zanotuj XY, wymiary aligned i położenie znaczników.
2. Kliknij **Zapisz MPP…**, wybierz typ **MPP aligned** i nową nazwę, np.
   `reg02-cpu-aligned.mpp`. Zachowaj razem MPP i towarzyszący plik metadanych.
3. Przed zmianą serii kliknij **Zapisz AVI…**. Wybierz **aligned**, całą serię,
   5 kl./s, **FFV1**, gamma neutralna, białe tło i bez opisów. Zapisz film.
   W VLC sprawdź 3 klatki, pełny obszar, zgodność znaczników i białe marginesy.
4. Otwórz zapisany MPP wraz z metadanymi. Sprawdź liczbę klatek, geometrię,
   braki, przesunięcia i nazwę **Korelacja bez normalizacji (v1)** w historii.
   Niezweryfikowana pewność ma pozostać rozpoznawalna po ponownym odczycie.
   Otwierany film zawiera już wyrównane piksele; nie wykonuj dodatkowej rejestracji
   przy sprawdzaniu tego roundtripu.

Zapisz wynik w karcie REG-02. Automatyczne testy i próby Qt nie zastępują tej
oceny wzrokowej. REG-03 czeka na decyzję użytkownika po odbiorze REG-02.
