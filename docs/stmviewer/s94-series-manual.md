# Próba ręczna — S94 i mieszane serie (ticket 03)

Z katalogu `NEtCAT-viewer`, w środowisku `netcat`, uruchom:

```bash
python -m stmviewer.main
```

Wybór „Otwórz STP/S94…” (także menu Plik lub Ctrl+O) pozwala zaznaczyć jeden
lub wiele plików obu formatów. Początkowy filtr obejmuje oba formaty; można
również wybrać osobny filtr STP lub S94.

## Wzorce w repozytorium

Małe pliki znajdują się w `tests/stmviewer/fixtures/s94/`. Można je odtworzyć:

```bash
python tests/stmviewer/make_s94_fixtures.py
```

| Plik | Oczekiwany wynik |
| --- | --- |
| `frame1.stp` | 4 × 3 px, Topo, nm, pole 8 × 9 nm; białe L po lewej i na dole |
| `frame2.s94` | Ten sam obraz i wartości; Topography, nm, pole 8 × 9 nm, offsety 2 i −1 nm, napięcie −0,2 V, kąt skanowania 37° |
| `frame10.S94` | Current, nA, pole 16 × 12 nm; ten sam kształt, lecz inna kalibracja wartości |
| `unknown-gain.s94` | Topography, jednostka nieznana, opis surowych wartości i nieznanego wzmocnienia Z (99) |
| `unknown-mode.s94` | Unknown (7), jednostka nieznana, opis surowych wartości i nieznanego trybu |
| `swapped.s94` | 3 × 4 px po transpozycji, pole 9 × 8 nm, offsety −1 i 2 nm; L po lewej i na górze |
| `truncated.s94` | Błąd niepełnych danych, bez podmiany wcześniejszej serii |

1. Otwórz razem `frame10.S94`, `frame2.s94`, `frame1.stp`. Oczekuj wspólnej
   kolejności **frame1, frame2, frame10**. Nie wybieraj wszystkich plików katalogu,
   bo zawiera on także celowo wadliwe i niezgodne wymiarowo przykłady.
2. Przejdź przez serię przyciskami, suwakiem, numerem oraz miniaturami.
   Pierwsze dwa obrazy mają identyczny kształt i proporcje. Trzeci ma inne
   proporcje fizyczne. Nazwa, kanał, jednostka i pole zmieniają się per klatka.
   Podświetlona jest zawsze tylko bieżąca miniatura.
3. Otwórz osobno `unknown-gain.s94`, a potem `unknown-mode.s94`.
   Oczekuj wyraźnego opisu surowych wartości. Program nie przypisuje im nm ani nA.
   Następnie otwórz `frame2.s94`: opis surowych wartości znika.
4. Otwórz osobno `swapped.s94`. Sprawdź kształt i metadane z tabeli.
   Kąt skanowania pozostaje źródłowym ustawieniem pomiaru 37°; nie jest
   wyliczonym kątem rastra po transpozycji.
5. Wróć do poprawnej mieszanej serii, wybierz drugą lub trzecią klatkę,
   przybliż ją i przesuń. Spróbuj otworzyć razem `frame1.stp` i `truncated.s94`.
   Błąd wskazuje S94; po zamknięciu komunikatu wcześniejsza seria, numer i widok pozostają.
6. Powtórz z `frame1.stp` i `swapped.s94`. Import odrzuca niezgodność **po**
   transpozycji (3 × 4 zamiast 4 × 3 px), zachowując poprzedni stan.
7. Anuluj dialog wyboru plików — stan pozostaje. Anulowanie trwającego importu
   działa tak jak w [próbie serii STP](stp-series-manual.md); testy automatyczne
   obejmują także anulowanie w trakcie odczytu S94 po poprawnym odczycie STP.

## Rzeczywiste pomiary lokalne

Na tym stanowisku pary są dostępne w `/home/rlew/projekty/NEtCAT-domains/data/`:
`17851.STP` / `17851.S94` oraz `17544.STP` / `17544.S94`. Dane pomiarowe
pozostają lokalne; nie są kopiowane do Git. Na innym stanowisku użyj własnej
odpowiadającej pary, a wzorcami syntetycznymi sprawdź samą obsługę formatu.

Otwórz razem oba pliki jednej pary. Przełączaj przyciskami i porównaj kształt,
orientację, jednostki nm, wymiary 256 × 256 oraz pole około 102,847794 nm
(dla 17851) lub 58,770168 nm (dla 17544). Wartości macierzy tych par są
identyczne. Metadane mogą być pełniejsze w S94: np. napięcie 0,2 V i kąt 310°
nie występują w ich eksportach STP. Nieznane parametry STP pozostają nieznane.

Dodatkowa para prądowa `85291r.STP` / `85291r.s94` ma identyczne liczby,
ale nagłówek STP podaje nm, podczas gdy tryb S94 oznacza nA. Viewer zachowuje
jednostkę każdego źródła. Ta para nie służy za wzorzec zgodności jednostek.
Pole `It` S94 jest zachowane w surowym nagłówku, lecz bez potwierdzonej jednostki
nie jest prezentowane jako zmierzony prąd zadany.

## Status

Testy automatyczne obejmują rzeczywiste dekodowanie binarnych wzorców,
little-endian ze znakiem, kalibrację, transpozycję i metadane, mieszane serie,
błędy i anulowanie. Próba automatyczna na ekranie Linuksa xcb potwierdziła
wybór obu formatów w dialogu, opis surowych wartości i identyczny podgląd
rzeczywistej pary 17851.

Użytkownik potwierdził pozytywny wynik testów manualnych 2026-10-21:
„testy manualne ok”. Ticket 03 ma status `done`. Nie wskazano systemu;
odrębny odbiór platform, w tym Windows, pozostaje do wykonania.
