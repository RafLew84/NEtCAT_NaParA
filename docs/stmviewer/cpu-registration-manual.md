# Próba ręczna — metody rejestracji CPU (ticket 09)

Z katalogu `NEtCAT-viewer`, w środowisku `netcat`:

```bash
python -m stmviewer.main
```

Dla Ubuntu 24.04 i Windows 11: [konfiguracja środowiska](README.md#uruchomienie).
Zestaw podstawowy obejmuje Phase, Tile+RANSAC i Optical Flow. ECC wymaga
opcjonalnego `stmviewer/requirements-ecc.txt`. Zainstalowana lokalnie wersja
OpenCV to 4.11.0 (pakiet opencv-python 4.11.0.86).

## Dane

W repo jest `tests/stmviewer/fixtures/registration/cpu.mpp`: trzy klatki
80 × 80 z asymetrycznymi znacznikami i teksturą, czasy 10/20/35 s.
Odtworzenie dokładnie tego wzorca:

```bash
python tests/stmviewer/make_cpu_registration_fixtures.py
```

Przesunięcia XY do zastosowania względem pierwszej klatki: (0,0), (2,−1),
(−1,1). Phase i Tile+RANSAC dają te wartości całkowite. ECC i Optical Flow
wyznaczają wartości bliskie, z dokładnością około 0,3 px na tym wzorcu.
Marginesy zaokrąglane w górę mogą dawać różne rozmiary aligned:
zaobserwowano odpowiednio 83 × 82, 83 × 82, 84 × 83 i 84 × 84 px.
To normalny skutek przesunięć subpikselowych; nie przycinamy źródłowego pola.

Można włączyć **Proporcje pikselowe** — nagłówek wzorca ma pole 8 × 9 nm.
Stary `integer.mpp` ma tylko 48 × 32 px i jest zbyt mały dla domyślnego
Tile+RANSAC; do porównania wszystkich metod użyj `cpu.mpp`.

Do dłuższej próby i anulowania: `data/MOVIE_3.MPP` (17 klatek) lub
`data/TTMAPP/MOVIE_23raw_TTMAPP_I_AU111.MPP` (268 klatek, zastępcza kalibracja).
Nie każda metoda musi skutecznie dopasować każdy pomiar.

## Kroki i oczekiwane wyniki

1. Otwórz `cpu.mpp`, wybierz klatkę 2, ustaw gamma 1,5 i uruchom Phase.
   Oczekuj aligned, ΔX 2 px i ΔY −1 px. Przybliż i przesuń wynik.
2. Z listy metod wybierz **Tile+RANSAC**. Obraz, zoom, obrys, wynikowe
   przesunięcia i nazwa **Phase** w opisie gotowego wyniku pozostają.
   Dopiero **Rejestruj** uruchamia nową metodę. Po sukcesie opis wskazuje
   Tile+RANSAC, nowy obszar jest dopasowany do okna, gamma zostaje.
3. Powtórz dla **ECC** i **Optical Flow**. Przejdź przez trzy klatki:
   znaczniki powinny pozostać w podobnym miejscu; dopuszczalne są drobne
   różnice subpikselowe. Original/aligned przywracają własne kadry.
4. W aligned obejrzyj klatkę 2, następnie wybierz 1 i usuń ją. Dawna druga
   zachowuje obraz, położenie, metodę i cały obszar. Odniesienie nadal
   wskazuje MPP 1; pochodzenie bieżącej klatki wskazuje MPP 2.
5. Otwórz lokalny `MOVIE_3.MPP`, wykonaj Tile+RANSAC, potem wybierz ECC
   i kliknij Rejestruj. W lokalnej próbie ECC zgłasza błąd pary 2 → 3:
   wcześniejszy wynik Tile+RANSAC pozostaje wraz z jego nazwą i geometrią.
   Kolejne samodzielne wybranie Optical Flow i uruchomienie rejestracji
   może go zastąpić. Program nie przełącza algorytmu po błędzie.
6. Na MOVIE_3 Tile+RANSAC i Optical Flow dają kompletne wyniki z ostrzeżeniami
   niepewności. Obejrzyj oznaczenia w panelu i miniaturach, także niepewność
   odziedziczoną w kolejnych klatkach. To oznaczenie potrzeby oceny wyniku,
   nie potwierdzenie jego fizycznej poprawności.
7. Po uzyskaniu aligned uruchom ponownie Optical Flow i kliknij
   **Anuluj rejestrację**. Na szybkim komputerze użyj dłuższego filmu:
   najpierw uzyskaj dla niego aligned, a potem ponów rejestrację.
   Nawigacja, zoom i gamma są dostępne w czasie pracy; Play, otwieranie,
   usuwanie i lista metod są zablokowane. Anulowanie czeka na koniec
   bieżącej pary/klatki, po czym zachowuje cały stary wynik i bieżący kadr.

Obliczenia zawsze korzystają z oryginałów pozostałych w bieżącej serii.
Metody i parametry pochodzą z istniejącej fabryki NanoTrack: raw, adjacent,
domyślne backend_params. ECC zawiera własny etap wstępny Phase; Optical Flow
używa TV-L1 i mediany przepływu jako jednej translacji. Nie stosuje deformacji
poszczególnych obszarów. Ten ticket nie dodaje strojenia parametrów.

## Brak opcjonalnej biblioteki

W osobnym, nowym środowisku Python 3.12 zainstaluj tylko podstawowe wymagania.
Nie usuwaj OpenCV ze współdzielonego `netcat`.

Ubuntu:

```bash
python3.12 -m venv /tmp/stmviewer-cpu-no-ecc
/tmp/stmviewer-cpu-no-ecc/bin/python -m pip install -r stmviewer/requirements.txt
/tmp/stmviewer-cpu-no-ecc/bin/python -m stmviewer.main
```

Windows, PowerShell (nowy katalog środowiska):

```powershell
py -3.12 -m venv "$env:TEMP\stmviewer-cpu-no-ecc"
& "$env:TEMP\stmviewer-cpu-no-ecc\Scripts\python.exe" -m pip install -r stmviewer/requirements.txt
& "$env:TEMP\stmviewer-cpu-no-ecc\Scripts\python.exe" -m stmviewer.main
```

Otwórz `cpu.mpp` i wykonaj Phase. Wybierz ECC: przycisk Rejestruj ma być
nieaktywny, a komunikat ma podać niedostępność ECC i brak cv2. Gotowy wynik
Phase pozostaje. Zmiana na Phase, Tile+RANSAC lub Optical Flow ponownie
udostępnia rejestrację. Po instalacji opcjonalnego zestawu i ponownym starcie
ECC powinien być dostępny. Brak SciPy albo scikit-image także nie blokuje
startu ani przeglądania — niedostępne stają się wszystkie metody rejestracji.

## Status prób

Automatyczne testy sprawdzają rzeczywiste backendy, błędy/niekompletne wyniki,
anulowanie, niską pewność, wybór metody oraz zachowanie starego aligned.
Osobne, świeże procesy z zablokowanym importem cv2/scipy/skimage sprawdzają
start i przeglądanie; to kontrolowana symulacja braku bibliotek.

Próba automatyczna Qt xcb na Linuksie użyła rzeczywistych dialogów i backendów,
wzorca `cpu.mpp` oraz lokalnego MOVIE_3, w tym rzeczywistego anulowania
Optical Flow. Przeszła; źródła zachowały sumy SHA-256. Obejrzano zrzuty.
ECC na MOVIE_3 zgłosił błąd z zachowaniem poprzedniego wyniku, zgodnie z krokiem 5.

Ręczny odbiór użytkownika, próba osobnego środowiska bez OpenCV oraz Windows
nie zostały jeszcze wykonane. Wyniki pełnej weryfikacji: [przekazanie](handoff.md).
