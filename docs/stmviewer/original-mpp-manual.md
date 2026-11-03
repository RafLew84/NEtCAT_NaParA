# Próba zapisu original MPP — ticket 12

Uruchom w katalogu repozytorium, w środowisku `netcat`:

```bash
python -m stmviewer
```

Na tym stanowisku Python jest pod
`/home/rlew/projekty/conda-migration-ubuntu-20261008/envs/netcat/bin/python`.
Wyniki zapisuj poza danymi źródłowymi, np. w nowym katalogu `/tmp/stmviewer-export-manual`
(na Windows w swoim katalogu roboczym). Przycisk **Zapisz MPP…** oraz Plik → Zapisz MPP… / Ctrl+S otwierają okno zapisu
wszystkich pozostałych klatek. Od ticketu 13 wybierz w polu **Typ pliku**
opcję **MPP original**; domyślna wersja odpowiada aktualnie oglądanemu widokowi.
Eksport aligned opisuje [osobna instrukcja](aligned-mpp-manual.md).

## Wartości, usuwanie i ponowne otwarcie

1. Otwórz `tests/stmviewer/fixtures/mpp/known-times.mpp`. Trzy klatki mają
   czasy 10, 20, 35 s. Usuń drugą. Pozostałe zachowują czasy 10 i 35 s.
2. Ustaw gamma 2,5, przybliż i przesuń obraz. Zapisz jako `times.mpp`.
   Powstają `times.mpp` i `times.mpp.stmviewer.json`. Komunikat wskazuje oba pliki.
   Zapis zachowuje wyświetlaną klatkę, gamma i kadr.
3. Zamknij program, uruchom ponownie i otwórz `times.mpp`. Oczekiwane:
   2 klatki, oryginalne obrazy i orientacja, czasy 10/35 s, źródłowe numery
   1/3, bieżące numery 1/2. Komunikat dodatku: „wczytano”. Nowy import ma gamma 1.
4. Sprawdź również pojedynczy `fixtures/asymmetric.stp` oraz
   `fixtures/s94/frame2.s94` (ścieżki względem `tests/stmviewer`). Oba można zapisać.
   Po usunięciu ostatniej klatki zapis jest nieaktywny.
5. Sprawdź `fixtures/preview/missing.stp`: NaN po ponownym otwarciu nadal
   pokazuje białe tło. Gamma i zoom nie zmieniają wartości w filmie.
6. Otwórz `fixtures/registration/integer.mpp`, wybierz Rejestruj, obejrzyj aligned
   i zapisz, wybierając **MPP original**. Ponownie otwarty film ma pierwotne
   wymiary i obrazy original.

Dokładne porównanie pierwszego wyniku (uruchom z katalogu repo, dostosuj ścieżkę):

```bash
PYTHONPATH=. python tests/stmviewer/check_mpp_export.py --source tests/stmviewer/fixtures/mpp/known-times.mpp --keep 1 3 --saved /tmp/stmviewer-export-manual/times.mpp
```

Oczekiwany raport: `OK: 2 klatek; dokładne wartości/NaN, parametry, czasy i pochodzenie.`
Na PowerShell ustaw najpierw `$env:PYTHONPATH="."`, potem uruchom `python ...`
bez prefiksu `PYTHONPATH=.` i użyj własnej ścieżki wyniku.

## Różne metadane i przenoszenie pary

1. W jednym wyborze otwórz `fixtures/s94/frame1.stp`, `frame2.s94`, `frame10.S94`.
   Zapisz jako `mixed.mpp`; różne skale i kanały nie blokują zapisu.
2. Otwórz wynik. Porównaj parametry wszystkich trzech klatek i ich nazwy źródłowe.
   Dokładny raport otrzymasz powyższą komendą z trzema ścieżkami po `--source`,
   bez `--keep`, i `--saved` wskazującym `mixed.mpp`.
3. Przenieś oba pliki do innego katalogu. Ponowne otwarcie nadal pokazuje
   te same parametry i historyczne pochodzenie, również gdy źródeł już nie ma.
4. Na osobnej kopii usuń JSON, otwórz MPP: film działa, etykieta podaje brak
   dodatku. Metadane pochodzą teraz wyłącznie ze wspólnego nagłówka, który dla
   sprzecznych/nieznanych pól podaje jednostki umowne, a nie parametry pierwszej klatki.
5. Obok innej kopii `mixed.mpp` połóż JSON z `times.mpp` pod pasującą nazwą.
   Film działa; etykieta zgłasza pominięcie dodatku przez niezgodny SHA-256.
6. Otwórz `fixtures/mpp-metadata/mixed.MPP`, zapisz i ponownie otwórz.
   Druga klatka zachowuje ścieżkę Windows, źródłowy numer 8 i brak czasu,
   trzecia brak skali X. Nie zostają zastąpione parametrami pierwszej klatki.

## Postęp, anulowanie, nadpisanie i błąd

1. W oknie zapisu wybierz istniejący wynik. Potwierdzenie obejmuje MPP i JSON;
   „Nie” zachowuje oba. Sprawdź też przypadek, w którym istnieje tylko JSON.
2. Przygotuj większy wzorzec; domyślny plik to około 2,1 GB, a zapis i kopie
   wymagają dodatkowego miejsca na dysku. Generator tworzy nowy plik, nie nadpisuje:

   ```bash
   python tests/stmviewer/make_mpp_export_fixture.py /tmp/stmviewer-export-manual/large.mpp
   ```

3. Otwórz go i zapisz pod nową nazwą. Podczas zapisu działa postęp i Anuluj;
   Play jest zatrzymany, otwieranie/usuwanie/rejestracja/kolejny zapis są zablokowane.
   Można wybierać klatki, zmieniać gamma i zoom. Zapis obejmuje całą serię.
4. Ponów zapis z nadpisaniem i szybko naciśnij Anuluj. Oczekiwany komunikat
   potwierdza anulowanie, a poprzednia para nadal się otwiera. Na szybkim dysku
   zapis może zdążyć się zakończyć; wtedy prawidłowy komunikat to „Zapisano”.
   Zamknięcie okna podczas zapisu również prosi worker o anulowanie i czeka na niego.
5. Kontrolowany błąd można sprawdzić na kopii wyniku w katalogu bez prawa zapisu
   (Linux: odebranie katalogowi `u+w`; po próbie przywróć). Jeśli dialog systemowy
   zatrzyma wybór wcześniej, jest to test dialogu, a nie workera eksportu.
   Błąd workera ma czytelny komunikat i zachowuje wcześniejszą parę oraz serię.
   Powtarzalne błędy zapisu i anulowanie między podmianami plików sprawdza:

   ```bash
   PYTHONPATH=.:tests/stmviewer QT_QPA_PLATFORM=offscreen python -m pytest -q tests/stmviewer/test_mpp_export_safety.py tests/stmviewer/test_mpp_export_window.py
   ```

Dwa pliki nie stanowią jednej atomowej operacji systemu plików. Zwykły błąd
lub anulowanie przywraca stare pliki. Twarde zakończenie procesu między
podmianami może pozostawić nowy MPP ze starym/brakującym dodatkiem: import
wykrywa ten stan. Jeśli samo przywracanie zawiedzie, komunikat wskazuje
katalog zachowanych kopii do odzyskania.

## Granice odbioru

Qt offscreen oraz sterowana skryptem próba xcb są testami automatycznymi.
Ręczne potwierdzenie użytkownika jest osobnym odbiorem. Windows 11 pozostaje
do sprawdzenia. Dodatkowa [próba WSxM pod Wine](wsxm-investigation.md) wykazała
problem formatowania nagłówka i wynikające z niego przesunięcie próbek.
Do ponownej próby użyj `data/test-wsxm-v2.mpp` wraz z JSON lub zapisz film
ponownie. Sprawdź także lewą krawędź na początku, w środku i na końcu filmu;
pasek widoczny w pierwszej kopii `test-wsxm.mpp` powinien zniknąć.
NaPara czyta bajty w kolejności pliku; NanoTrack/MolTrack stosują swój obrót
180° do orientacji zgodnej z Viewerem. Wspólny starszy czytnik ma limit
1000 linii nagłówka, nie obsługuje JSON ani nie rozróżnia poprawnie nieznanej
skali. Długie nagłówki i indywidualne parametry sprawdzamy w STM Viewerze;
rozszerzenie wspólnego czytnika należy do integracji.
