# Ticket 14 — zapis original do AVI

Status: **done** — użytkownik potwierdził testy manualne 2026-10-26.
Uruchomienie z katalogu repo:

```bash
conda activate netcat
python -m stmviewer.main
```

Na nowym stanowisku stos OpenCV/FFmpeg dodaje
`python -m pip install -r stmviewer/requirements-avi.txt`. Lokalny netcat już go zawiera. Instalacja VLC
jest osobna; program nie pobiera kodeków. Wybór kodeka jest sprawdzany przez
próbny zapis/odczyt, a gotowy film przez odczyt wszystkich klatek przed publikacją.

## Dane

Gotowe lokalnie: `data/MOVIE_3.MPP` (17 × 256 × 256) oraz katalog
`data/avi-ticket14/`. Wzorce można odtworzyć z repo:

```bash
PYTHONPATH=. python tests/stmviewer/make_avi_fixtures.py
```

- `odd.mpp`: sześć klatek 65 × 49. Cztery przesuwające się białe znaczniki,
  szary znacznik, biała ostatnia kolumna, szary ostatni wiersz i brakujące próbki;
  klatka 5 całkowicie pusta, 6 stała. Znane czasy 10, 15, 35, 40 s w pierwszych czterech.
- `anisotropic.mpp`: te same dane, piksel X dwa razy szerszy od Y.
- `long.mpp`: 600 klatek 512 × 512, około 1,26 GB, do anulowania.
  Opcjonalnie generowany przez dodanie `--long` do powyższej komendy.
  Zawiera deterministyczną teksturę; służy próbie zapisu, nie odbiorowi
  wydajności docelowej serii. Mały film może skończyć się przed kliknięciem Anuluj.
- MPP i JSON należy zachować razem. To pliki lokalne, poza Git.

## Próba w programie

1. Otwórz `MOVIE_3.MPP`. Ustaw Play na 5 kl./s. Wybierz **Zapisz AVI original…**
   w panelu lub menu Plik. Początkowo: cała seria, FPS 5, MJPG. Podsumowanie
   ma pokazać 17 klatek, 256 × 256 px i 3,400 s (interfejs używa kropki).
2. Ustaw FPS 7, zapisz `movie-mjpg.avi`, potem FFV1 do `movie-ffv1.avi`.
   Po zakończeniu wyświetla się ścieżka wyniku; Play nadal ma 5 kl./s.
   Otwórz oba filmy w VLC i sprawdź obrazy, orientację oraz kolejność.
3. Wybierz zakres 5–10 i FPS 5: sześć klatek, 1,200 s. Zakres 5–5 daje
   jedną klatkę, bez powtarzania. Zakres od większy od do blokuje Zapisz.
   Usuń klatkę z serii i ponów: numery zakresu dotyczą obecnej listy.
4. Ustaw gamma 2, przybliż i przesuń obraz, zmień rozmiar okna. Ponowny film
   ma gamma 2, ale cały obraz 256 × 256. Przy oglądaniu aligned przycisk nadal
   jawnie zapisuje **original**; eksport aligned jest w tickecie 16.
5. Otwórz `odd.mpp`, gamma 1. Eksport obu kodeków ma **66 × 50**:
   ostatnie krawędzie pomiaru zostają, z prawej i dołu dodano czarny piksel.
   Piąta klatka pozostaje w filmie jako czarna, szósta jest szara (127).
   Przy gamma 2 szósta staje się jaśniejsza (180), braki i dopełnienie nadal czarne.
   MJPG może zmieniać jasności przy kompresji; FFV1 zachowuje raster dokładnie.
6. `anisotropic.mpp` daje **130 × 50**, bez pomniejszania danych. Zaznaczenie
   **Proporcje pikselowe** przed otwarciem eksportu daje 66 × 50. Pozwala to
   pominąć zastępczą skalę nagłówka. Niespójne lub nieznane skale również dają
   proporcje pikselowe; wybrany zakres określa, które kalibracje są porównywane.
7. Zapisz krótki poprawny film. Otwórz `long.mpp`, wybierz tę samą nazwę,
   potwierdź zastąpienie i naciśnij **Anuluj zapis AVI**. Stary film ma pozostać.
   W trakcie zapisu można oglądać klatki oraz zmieniać gamma/zoom; eksport
   zachowuje ustawienia z chwili otwarcia jego opcji. Play, import, usuwanie,
   rejestracja i oba eksporty są zablokowane. Zamknięcie programu anuluje
   pracę i czeka na bezpieczne zakończenie.
8. Dla próby awarii kodeka można otworzyć `tests/stmviewer/fixtures/asymmetric.stp`.
   Lokalny MJPG 4 × 4 kończy proces testowy błędem; Viewer ma pokazać komunikat
   i zachować serię oraz poprzedni film. Można samodzielnie wybrać FFV1.
   Inny build OpenCV może poprawnie obsłużyć ten rozmiar — wtedy poprawny zapis
   również spełnia kryterium. Program nie zmienia kodeka automatycznie.

Czarne tło AVI jest ustawieniem ticketu 14. Białe tło podglądu i obecny zapis MPP
pozostają zgodne z wcześniejszym odbiorem. Wybór czarny/szary/biały, kontrastu
oraz neutralnej gamma należy do ticketu 15.

Lokalnie można uruchomić tymczasową kopię VLC bez instalacji w systemie:

```bash
/tmp/stmviewer-avi-vlc/vlc data/avi-ticket14/MOVIE_3-FFV1.avi
```

Ta kopia pozostaje dostępna do usunięcia katalogu `/tmp/stmviewer-avi-vlc/`.

## Wykonane sprawdzenia — 2026-10-26

- Testy automatyczne obejmują renderer, rzeczywisty zapis/odczyt obu kodeków,
  zakres/FPS, braki, błędy, anulowanie, ochronę wcześniejszego pliku i GUI.
- Qt xcb na osobnym Xvfb: **13 passed**, obejmuje nowe AVI i dotychczasowy MPP.
  Obejrzano również zrzut głównego okna i dialogu. To automatyczna próba GUI,
  nie ręczna akceptacja użytkownika.
- Faktyczne odtwarzanie **VLC 3.0.20** na Ubuntu/Xvfb, wyjście obrazu `xcb_x11`:
  sześć filmów (MOVIE_3, odd, anisotropic × MJPG/FFV1) odtworzonych do EOF,
  kody zakończenia 0, bez błędów dekodera/obrazu. Obejrzano zrzuty.
  Zewnętrzny VLC używa bibliotek systemowych Ubuntu, a nie FFmpeg z OpenCV.
  Pakiety rozpakowano w `/tmp/stmviewer-avi-vlc/`, bez instalowania w systemie;
  logi, obrazy i `results.json` są w tym katalogu. Gotowe AVI są przy wzorcach.
- Rzeczywisty eksport 600 klatek 512 × 512 przerwano przez GUI po rozpoczęciu
  kodowania (postęp 32). Stary AVI pozostał identyczny bajtowo. Pierwsza próba
  na mniejszym wzorcu zakończyła się przed kliknięciem, dlatego generator
  udostępnia teraz większy plik opcjonalnie.
- Użytkownik potwierdził odbiór ręczny 2026-10-26: „testy manualne ok”.
  Nie wskazał systemu, więc nie przypisujemy temu potwierdzeniu odbioru Windows 11.
  Duża seria docelowa, test zasobów i odbiory platform mają odrębne tickety 18–21.
