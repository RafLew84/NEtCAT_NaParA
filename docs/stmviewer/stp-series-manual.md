# Próba ręczna — seria STP (ticket 02)

Uruchom z katalogu głównego worktree `NEtCAT-viewer`, w środowisku `netcat`:

```bash
python -m stmviewer.main
```

Małe pliki są w Git, w `tests/stmviewer/fixtures/`. W razie potrzeby odtworzysz
je poleceniami `python tests/stmviewer/make_fixtures.py` oraz
`python tests/stmviewer/make_series_fixtures.py`. To sztuczne wzorce double,
a nie dane pomiarowe. Program nie zmienia plików źródłowych.

## Otwieranie i przeglądanie

1. Wybierz „Otwórz STP…” (także Plik → Otwórz lub Ctrl+O). W katalogu
   `tests/stmviewer/fixtures/series` zaznacz trzy pliki: `klatka10.stp`,
   `klatka2.stp`, `klatka1.stp` — np. Ctrl+A w liście plików.
2. Oczekuj kolejności **1, 2, 10**, numeru **1 z 3** i całego obrazu.
   Pierwszy wzorzec ma biały pasek w górnym wierszu poza lewym pikselem
   oraz biały piksel pod środkiem paska. Kalibracja i kanał są nieznane.
3. Kliknij „Następna”. Drugi wzorzec ma białe L po lewej i na dole,
   szary środek i ciemniejszy znacznik w prawym górnym rogu.
   Panel pokazuje **Topo, nm, pole 8 × 9 nm, napięcie 0 V**, rozmiar 4 × 3 px.
   Fizyczne proporcje powodują, że obraz jest wyższy niż szerszy.
4. Wybierz trzecią miniaturę. Białe L jest po prawej i na dole;
   panel pokazuje **Current, pA, pole 16 × 12 nm, napięcie 1.5 V**.
   Upewnij się, że główny obraz, zaznaczona miniatura, suwak, numer i źródło
   wskazują tę samą klatkę. Kliknij dwukrotnie Poprzednia, potem dwukrotnie
   Następna: podświetlona ma być tylko aktualna miniatura, bez pozostających
   śladów na poprzednich. Wypróbuj także suwak i wpisanie numeru.
5. Przybliż kółkiem i przesuń lewym przyciskiem myszy. Zmieniaj klatki:
   zoom i przesunięcie pozostają, choć proporcje każdej klatki wynikają z jej
   własnej skali. „Dopasuj” przywraca cały obraz. Na końcach serii odpowiedni
   przycisk Poprzednia/Następna jest nieaktywny.

## Błąd i anulowanie zachowują serię

1. Pozostaw wybraną klatkę 2 lub 3, najlepiej po przybliżeniu.
2. W katalogu `tests/stmviewer/fixtures` otwórz jednocześnie
   `asymmetric.stp` i `truncated.stp`. Komunikat wskazuje `truncated.stp`;
   po jego zamknięciu poprzednia seria, numer, obraz i zoom pozostają.
3. Powtórz z `asymmetric.stp` i `smaller.stp`. Komunikat wskazuje niezgodne
   wymiary `smaller.stp` (2 × 3 zamiast 4 × 3 px). Poprzedni stan pozostaje.
4. Anuluj sam dialog wyboru plików. Nic się nie zmienia.

Do próby anulowania trwającego importu przygotuj większą serię **poza repo**
(domyślne 1000 × 512 × 512, około 2 GiB na dysku i około 2 GiB wartości w RAM):

```bash
python tests/stmviewer/make_series_fixtures.py --large-dir /tmp/stmviewer-series-manual
```

Windows PowerShell: zamiast `/tmp/stmviewer-series-manual` użyj
`"$env:TEMP\stmviewer-series-manual"`. Opcje `--count` i `--size` pozwalają
zmienić liczbę plików oraz długość boku. Generator wypisuje rozmiar zestawu.
To wzorzec anulowania importu, nie zaliczony test wydajności z ticketu 18.

5. Z otwartą małą serią wybierz wszystkie STP z dużego katalogu. Widać postęp
   odczytu i przygotowania miniatur; nadal można oglądać poprzednie klatki
   i korzystać z zoomu. Ponowne otwarcie jest czasowo nieaktywne.
6. Kliknij „Anuluj import” przed zakończeniem. Bieżący odczyt pliku musi
   dobiec końca; aplikacja pozostaje responsywna. Po zakończeniu anulowania
   poprzedni zestaw i wybrana klatka pozostają, a Otwórz znów jest aktywne.
   Jeśli import zdążył się zakończyć, powtórz go i anuluj wcześniej.
7. Otwórz tylko `unknown.stp`. Oczekuj **1 z 1**, pojedynczej miniatury,
   nieaktywnych przycisków przechodzenia i obrazu dopasowanego do okna.
   Zamknij program i uruchom ponownie: pusty stan ma nieaktywne kontrolki
   klatek oraz Dopasuj.

## Status sprawdzeń

Automatyczne testy Qt offscreen obejmują powyższe przejścia, w tym rzeczywisty
odczyt plików z kontrolowanym opóźnieniem systemowego I/O, anulowanie,
zamykanie podczas importu i zachowanie widoku. Automatyczna próba Qt xcb
na Linuksie otworzyła trzy wzorce przez prawdziwy dialog, sprawdziła miniatury
oraz nawigację i wczytała rzeczywisty pomiar 34855.STP. Zrzuty oceniono wizualnie.
Użytkownik potwierdził ręczny odbiór ticketu 02 po poprawce podświetlenia
miniatur (`cb40891`) 2026-10-21: „testy manualne ok”. Ticket ma status `done`.
Nie wskazano systemu, więc potwierdzenie nie zamyka osobnych odbiorów Ubuntu
i Windows.
