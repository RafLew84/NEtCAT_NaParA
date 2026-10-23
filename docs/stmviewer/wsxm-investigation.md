# WSxM: odczyt MPP, kontrast i pasek przy krawędzi — 2026-10-23

## Wynik

Przyczyną końcowo potwierdzonego błędu jest **formatowanie nagłówka**.
WSxM 5.0 Develop 12.0 czyta próbki z miejsca odpowiadającego długości
nagłówka w swoim natywnym układzie. Samo poprawne `Image header size`
nie wystarcza. Zwarty nagłówek powoduje odczyt od niewłaściwego bajtu:
zależnie od różnicy rozmiarów zmienia wartości albo przesuwa obraz.

Końcowa poprawka odtwarza układ natywny: CRLF, cztery spacje przed polami,
puste wiersze wokół nagłówków sekcji, uporządkowane sekcje/pola oraz
pomijanie pustych sekcji. Zachowano jawny zakres skończonych wartości
i jednostkowy przelicznik sygnału. Bajty pomiarów pozostają niezmienione.

Pierwsza poprawka (`b887b2b`) z CRLF i czterema polami liczbowymi przywracała
przejścia tonalne, lecz nadal przesuwała próbki. Nie stanowiła pełnego
rozwiązania; ujawniły to późniejsze nagrania użytkownika. Wcześniejsza
hipoteza o konieczności samych pól zakresu nie jest rozstrzygnięciem
przyczyny. Opis pierwszego eksperymentu poniżej pozostaje historią diagnozy.

Sprawdzenie dotyczy WSxM 5.0 Develop 12.0 pod Wine 9.0 na Ubuntu.
Nie stanowi odbioru WSxM na Windows ani wszystkich wariantów MPP.

## Pierwsza próba: przejścia tonalne

Wejście użytkownika: `data/test.mpp`, 369 klatek 256 × 256, pochodzących
z S94. Wszystkie wartości są skończone; zakres całej serii wynosi
−6.337890625 do 15.08203125 nm. Minimalny przykład to pojedyncza klatka
źródłowa o indeksie 184 (185. w serii), zakres −0.61767578125 do 0.666015625.
Oryginalny plik nie był nadpisywany.

Test steruje rzeczywistym WSxM na wirtualnym ekranie X11 i ocenia kolory
wewnątrz obrazu, z zatrzymanym odtwarzaniem. Zrzuty oceniono również
wizualnie. Końcowy warunek to ponad 16 kolorów występujących w więcej
niż 20 pikselach; ten warunek dotyczy konkretnego wzorca, nie dowolnego
poprawnego obrazu STM. Film o stałej wartości słusznie miałby jeden kolor.

| Nagłówek tej samej klatki | Wynik obrazu |
| --- | --- |
| LF, dotychczasowy zapis | Brak przejść tonalnych |
| CRLF, bez nowych pól | 5 kolorów; błąd |
| LF, cztery nowe pola | 5 kolorów; błąd |
| CRLF, cztery nowe pola | 216 kolorów; poprawny obraz |
| Natywny nagłówek istniejącego MPP WSxM | Poprawny obraz |

To porównanie potwierdza działający zestaw zmian. Nie rozstrzyga, czy każde
z czterech pól jest osobno konieczne we wszystkich wersjach WSxM.
Przesunięcie poziomu sygnału na dodatni w kopii diagnostycznej także
zmieniało wygląd, ale **nie jest rozwiązaniem przyjętym w eksporterze**.
Wyłączenie automatycznego Plane nie rozwiązało błędu. Kontrast osobny dla
klatek pomagał na początku filmu, ale nie naprawiał późniejszych klatek.

Lokalny, diagnostyczny skrypt i artefakty: `/tmp/wsxm-investigation/`.
Polecenie końcowej próby ma postać (Python ze środowiska `netcat`):

```bash
DISPLAY=:98 QT_QPA_PLATFORM=xcb python /tmp/wsxm-investigation/run_case.py /tmp/wsxm-investigation/full-corrected-header.mpp full-corrected-header --frame=5 --assert-tones
DISPLAY=:98 QT_QPA_PLATFORM=xcb python /tmp/wsxm-investigation/audit_frames.py
```

Skrypty są narzędziami tej diagnozy, wymagają lokalnego Wine, WSxM, Xvfb
oraz ustalonego rozmiaru okna; nie należą do przenośnego zestawu testów CI.
Pierwsza wersja mierzyła kolory palety w całym oknie. Końcowa mierzy kolory
wewnątrz obrazu. W końcowej próbie pełnego filmu klatki 0/184/368 mają
odpowiednio **72/216/205** kolorów spełniających próg, z widocznymi szczegółami.
To próba automatyczna GUI, nie ręczny odbiór użytkownika.

## Pierwsza kopia i zachowanie danych

Poprawiony eksporter utworzył `data/test-wsxm.mpp` oraz
`data/test-wsxm.mpp.stmviewer.json`. MPP jest bajtowo identyczny z wariantem
sprawdzonym w WSxM (`full-corrected-header.mpp`).

- SHA-256 oryginału: `b4298947954a67648c254662d19852a41e36512f1b2870f65271178a24990e1e`.
- SHA-256 poprawionego MPP: `12776e16f68ff377d1c0907fd9d30053db68dd58b318aa128901378009a8d22f`.
- SHA-256 części pomiarowej obu plików jest identyczny:
  `6a2027bbc4ad004e2f73aa9a443a5229b47188b15ae41c3f99b4a38f1e55b1e3`.
- `check_mpp_export.py` porównał **wszystkie 369 klatek** obu wersji
  z ich źródłowymi S94: dokładnie zgodne wartości, parametry, czasy i pochodzenie.

Zakres nagłówka obejmuje skończone próbki całej serii. NaN i nieskończoności
nie służą do wyliczania minimum/maksimum, ale pozostają w danych. Jeśli
brak skończonych próbek, pola granic są pomijane. Skanowanie zakresu działa
blokami i sprawdza anulowanie; nie tworzy kopii całego filmu.
Test publicznego eksportu sprawdza CRLF, granice z kilku klatek, jednostkowy
przelicznik, dokładne bajty próbek oraz ponowny odczyt. Test nie zastępuje
uruchomienia WSxM. Odbiór jego obsługi NaN pozostaje osobnym sprawdzeniem.

Film ma różne skale fizyczne w poszczególnych klatkach. Wspólny nagłówek
podaje X/Y w jednostkach umownych; pełną kalibrację zachowuje dodatek JSON,
który odczytuje STM Viewer. Próba nie dowodzi, że WSxM odtwarza te indywidualne
parametry z dodatku.

## Końcowa próba: położenie próbek i lewa krawędź

Nagrania użytkownika z 18:59:10 i 19:00:22 pokazują pasek we wszystkich
klatkach `test-wsxm.mpp`. Wzorzec 256 × 256 z rampą i znacznikiem pozwolił
odtworzyć ten objaw, z wyłączonym Plane i innymi filtrami. Po zapisie
kopii przez rzeczywisty WSxM można porównać piksele liczbowo, niezależnie
od palety i rysowania okna.

Sprawdzone hipotezy: format nagłówka, ustawienia przetwarzania i metadane
przesunięcia X/Y. Natywny nagłówek usunął problem przy tych samych danych,
ustawieniach i X/Y; dalsza zmiana ustawień lub offsetów nie była potrzebna.

| Wariant nagłówka rampy | Długość nagłówka | Odczyt/zapis WSxM |
| --- | ---: | --- |
| Zwarty CRLF z zakresem | 490 B | Odczyt od 546 B; przesunięcie o 7 double |
| Dodane tylko wcięcia | 558 B | Nadal od 546 B; część tekstu odczytana jako double |
| Dodane tylko puste wiersze | 508 B | Błędne wartości próbek |
| Pełny układ natywny | 546 B | Wszystkie 65 536 próbek dokładnie zgodne |
| Pełny nagłówek zapisany przez WSxM | 2584 B | Wszystkie 65 536 próbek dokładnie zgodne |

Wyjaśnienie ponownego formatowania wynika z powtarzalnego zachowania
programu, bez dostępu do jego kodu źródłowego. Test przegrywający przed
poprawką: `compare_wsxm_samples.py edge-ramp.mpp edge-native-saved.mpp`
w lokalnym katalogu diagnostycznym; 64 386 różnych pozycji z 65 536.
Po zastosowaniu natywnego układu ten sam test porównania daje 0 różnic.
Regresja publicznego eksportu utrwala zweryfikowany nagłówek 546 B oraz
początek danych: RED przed zmianą eksportera, GREEN po zmianie.

**Wynik do ponownej próby:** `data/test-wsxm-v2.mpp` oraz
`data/test-wsxm-v2.mpp.stmviewer.json`. Oryginału ani pierwszej kopii nie
nadpisano. SHA-256 nowego MPP:
`e3a821bafc04291119c65530b152a5529bb02595b52bf9b6d51c12de85440c6c`.
Nagłówek ma 485 B; część pomiarowa jest bajtowo identyczna z oryginałem.

- Własny odczyt porównano ze źródłowymi S94: **369 klatek**, dokładne
  wartości, metadane, czasy i pochodzenie.
- Cały film otwarto i zapisano przez WSxM przy wyłączonym Plane:
  **24 182 784 / 24 182 784** próbek dokładnie zgodnych, we właściwej kolejności.
  Kopia diagnostyczna: `/tmp/wsxm-investigation/full-v2-native-roundtrip.mpp`.
- Oceniono obrazy klatek 0/184/368: pasek zniknął, szczegóły pozostają widoczne.
  Liczba kolorów spełniających wcześniejszy próg: **72/218/206**.
- Dodatkowy film 3 × 64 × 96 z unikalnymi wartościami i czasami 2/5/9 s:
  **18 432 / 18 432** próbek zgodnych po odczycie/zapisie w WSxM; czasy
  zachowane. Obejmuje niepustą sekcję synchronizacji i prostokątny obraz.
- Testy Viewera po poprawce: **217 passed, 2 skipped**, 22.07 s.
  Mypy strict: **23 pliki**, bez błędów.
- Pełny zestaw repo po pierwszej poprawce: **2002 passed, 14 failed,
  16 skipped**, 230.78 s. Identyfikatory 14 niepowodzeń MolTrack/NanoTrack
  są identyczne z wynikiem ticketu 12; brak nowych niepowodzeń.
  Po końcowej korekcie formatowania ponowiono zestaw Viewera, obejmujący
  również kontrolę eksportu przez starsze czytniki.

[Przegląd Standards/Spec](implementation/review-12-wsxm.md): brak otwartych
uwag. Implementacja: `b887b2b`, końcowa korekta: `0cb6644`.

Próby Wine są automatyczne, sterowane GUI. Nie zastępują ręcznego odbioru
użytkownika na Ubuntu/Windows ani sprawdzenia NaN w WSxM. Testy tego
programu nie dowodzą obsługi indywidualnych metadanych JSON ani wszystkich
wariantów kodowania nagłówka. Wszystkie skrypty i filmy diagnostyczne
pozostają lokalnie w `/tmp/wsxm-investigation/`; nie trafiają do Git.

## Nagranie Windows: słaby kontrast — 2026-10-23

Użytkownik dostarczył `bandicam 2026-10-23 19-19-29-772.mp4` z nośnika
`/media/rlew/A7DE-44B4`. Na nagraniu otwarty jest `test-wsxm-v2.mpp`:
widoczne są słabe szczegóły i duże zmiany ogólnej jasności między klatkami,
bez wcześniejszego paska przy krawędzi. SHA-256 kopii na nośniku jest
identyczny z lokalnym v2: `e3a821bafc04291119c65530b152a5529bb02595b52bf9b6d51c12de85440c6c`.

W izolowanej kopii WSxM odtworzono ten wygląd przy ustawieniu
**Settings → Movie Settings → Palette range → Fit to movie Max/Min values**.
Następnie zmieniono wyłącznie tę opcję na **Fit to frame Max/Min values**,
zatwierdzono i odświeżono klatkę. Szczegóły wróciły bez zmiany MPP lub
włączenia Plane. Dla tej samej klatki o indeksie 4 rozpiętość jasności
między percentylami 1 i 99 wzrosła z **24 do 217** w skali 0–255.
Pierwszy obraz nagrania Windows również miał rozpiętość **24**.
To lokalne odtworzenie objawu i naprawy ustawienia, nie potwierdzenie
bieżącej konfiguracji na komputerze Windows — potrzebna jest próba użytkownika.

Próg diagnostyczny >30 dotyczy tego konkretnego obrazu, nie dowolnego
pomiaru. Komenda `windows/check_contrast.py` w katalogu diagnozy: RED dla
`windows/movie-range-frame4.png`, GREEN dla `windows/frame-range-frame4.png`,
z wycinkiem `8 112 258 362`. Nagranie, zrzuty i skrypt pozostają lokalne.

Globalny zakres filmu to −6.337890625…15.08203125 nm. Zakres pojedynczych
klatek 0/184/368 zajmuje odpowiednio około 6.5/6.0/3.2% tego przedziału,
więc wspólna paleta słabo różnicuje ich szczegóły. Wybór zakresu dla każdej
klatki poprawia widoczność, ale jednakowy kolor nie oznacza wtedy jednakowej
wartości między klatkami. Nie zmieniano eksportera ani danych; Windows
nadal oczekuje na potwierdzenie użytkownika po zmianie opcji.

## Lokalna instalacja

WSxM z instalatora użytkownika jest zainstalowany w osobnym prefiksie:
`~/.local/share/wineprefixes/wsxm`. Skrót **WSxM 5.0 Develop 12.0** znajduje
się w menu aplikacji. Bezpośrednie uruchomienie na tym komputerze:

```bash
WINEPREFIX="$HOME/.local/share/wineprefixes/wsxm" wine 'C:\ProgramData\WSxM\WSxM 5.0 Develop 12.0\WSxM.exe' 'Z:\home\rlew\projekty\NEtCAT-viewer\data\test-wsxm-v2.mpp'
```

Podczas startu mogą pojawić się komunikaty połączenia z aparaturą oraz
braku DSP/Dulcinea. W tej instalacji można je zamknąć i przeglądać pliki.
Do widoczności szczegółów każdej klatki: **Settings → Movie Settings →
Palette range → Fit to frame Max/Min values**. Po zatwierdzeniu przejdź
na inną klatkę. Jest to wybór kontrastu, nie zamiennik poprawnego nagłówka.
