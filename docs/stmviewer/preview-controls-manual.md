# Próba ręczna — zoom, gamma i brakujące próbki (ticket 05)

Z katalogu `NEtCAT-viewer`, w środowisku `netcat`, uruchom:

```bash
python -m stmviewer.main
```

Ustawienia znajdują się po prawej: przyciski **−**, **+**, **Dopasuj**,
wartość **Gamma**, **Reset gamma** i **Proporcje pikselowe**. Panel przewija się,
jeśli nie mieści metadanych lub postępu. Pasek miniatur pozostaje pod obrazem.
Pusta aplikacja ma nieaktywne ustawienia podglądu.

## Wzorce

Małe pliki znajdują się w `tests/stmviewer/fixtures/preview/`.
Można je odtworzyć:

```bash
python tests/stmviewer/make_preview_fixtures.py
```

Wszystkie mają 4 × 3 piksele. `pattern1.stp` zawiera następujące wartości
w kolejności widocznej na ekranie (`—` oznacza NaN):

```text
0    0,25   1     —
—    —      0,5   1
0    —      1     —
```

| Plik | Oczekiwany wynik |
| --- | --- |
| `pattern1.stp` | Czarne zera, dwa poziomy szarości, białe jedynki, białe tło w brakujących próbkach |
| `pattern2.stp` | Ten sam wygląd; skończone liczby są większe o 10, NaN pozostaje NaN |
| `constant.stp` | Wszystkie wartości 7; jednolite szare pole przy gamma 1 |
| `missing.stp` | Wszystkie wartości NaN; całe pole ma białe tło |
| `physical.stp` | Wzór jak pattern1, pole 8 × 9 nm; obraz jest wyższy niż szerszy |
| `placeholder.stp` | Wzór jak pattern1, pole 1000 × 1000 nm; sztuczny przykład zastępczej skali |

Nie wybieraj całego katalogu jako pierwszej próby: do sekwencji użyj
`pattern1.stp` i `pattern2.stp`, pozostałe wzorce otwieraj osobno.

## Kroki i oczekiwany wynik

1. Otwórz razem `pattern1.stp` i `pattern2.stp`. Ustaw gamma 2: szare pola
   rozjaśniają się, zera pozostają czarne, białe pola pozostają białe,
   a białe tło się nie zmienia. Miniatury nadal mają gamma 1.
   Przy gamma 0,5 szare pola ciemnieją. Sprawdź krańce 0,1 i 4 oraz Reset gamma.
2. Ustaw gamma 2, przybliż kółkiem przy krawędzi rozpoznawalnego pola.
   Punkt pod kursorem pozostaje w tym samym miejscu. Przeciągnij obraz lewym
   przyciskiem: przesuwa się bez zmiany powiększenia. Przyciski +/− przybliżają
   i oddalają wokół środka podglądu.
3. Wybierz drugą klatkę przyciskiem, suwakiem, numerem i miniaturą. Gamma,
   powiększenie i przesunięcie pozostają. Oba wzorce wyglądają jednakowo:
   kontrast jest liczony osobno z zakresu skończonych wartości każdej klatki.
   Zaznaczona jest tylko bieżąca miniatura. Dopasuj przywraca cały obraz,
   pozostawiając gamma; Reset gamma pozostawia zoom i przesunięcie.
4. Otwórz `constant.stp`. Przy gamma 1 oczekuj jednolitej szarości;
   gamma 2 rozjaśnia ją, a 0,5 przyciemnia. Następnie otwórz `missing.stp`:
   cała klatka jest biała niezależnie od gamma. Pozostaje możliwy zoom.
5. Otwórz `physical.stp`: proporcja wynika z pola 8 × 9 nm.
   Zaznacz Proporcje pikselowe: obraz i miniatura zmieniają proporcję na 4:3,
   a parametry z pliku nadal pokazują 8 i 9 nm. Odznaczenie przywraca proporcję
   z nagłówka. Analogicznie sprawdź `placeholder.stp`: 1:1 zmienia się na 4:3.
6. Ustaw gamma, zoom, przesunięcie i Proporcje pikselowe. Anuluj wybór plików,
   następnie spróbuj wczytać `tests/stmviewer/fixtures/truncated.stp`.
   Po komunikacie poprzednia seria, klatka i ustawienia pozostają.
   To samo dotyczy „Anuluj import” przy dłuższym filmie. Import w tle
   z kontrolowanym opóźnieniem jest też objęty testem automatycznym.
7. Otwórz nową poprawną serię. Oczekuj pierwszej klatki, gamma 1,
   dopasowania obrazu i wyłączonych Proporcji pikselowych.
   Powtórz na rzeczywistym STP, S94 i MPP.

## Proporcje i metadane

Użytkownik zatwierdził opcję Proporcje pikselowe 2026-10-21, ponieważ eksport
TTMAPP zawiera zastępcze 1000 nm, których nagłówek nie oznacza jako zastępczych.
Zaznacz ją, gdy skala w źródle jest niewiarygodna. Dotyczy całej bieżącej serii,
głównego podglądu i miniatur. Zachowuje się przy zmianie klatki i błędzie
importu; nowa poprawna seria przywraca domyślne proporcje z pliku.

Przy odznaczonej opcji używamy dodatnich, skończonych skal X/Y z nagłówka,
a jeśli ich brakuje lub stosunek jest nieprawidłowy — proporcji pikselowych.
Nie rozpoznajemy wartości zastępczych po nazwie pliku ani samej liczbie 1000.
Etykieta „Parametry z pliku” opisuje dane źródłowe, nie potwierdzoną kalibrację.
Przełącznik nie przelicza i nie usuwa metadanych.

## Konwencja gamma i braków

Skończone wartości są normalizowane do `u` od 0 do 1 według zakresu klatki,
a jasność wynosi `u ** (1 / gamma)`. Stała klatka przyjmuje `u = 0,5`
przed gamma. Dane pomiarowe nie są zmieniane. Białe tło jest rysowane
pod przezroczystą maską braków i nie trafia do pomiaru. Tak samo prezentowane są inne niefinitywne wartości, np. ±Inf.

## Wykonane sprawdzenia

77 testów Viewera oraz mypy strict (15 plików) przechodzą. Testy obejmują
rzeczywiste pliki, obraz/miniatury, maskę, gamma, stałe i puste klatki,
niezmienność danych tylko do odczytu, gesty, przyciski, proporcje i import.
Automatyczna próba Qt xcb przeszła na wzorcach oraz lokalnym
`/home/rlew/projekty/NEtCAT-domains/data/MOVIE_3.MPP`; zrzuty oceniono wizualnie.
Użytkownik potwierdził ręczny odbiór 2026-10-21: „testy manualne ok”.
Nie wskazano systemu; odrębne odbiory platform pozostają do wykonania.
Play i przełączanie original/aligned należą do kolejnych ticketów.
