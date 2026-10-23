# WSxM: dwukolorowy obraz MPP — 2026-10-23

## Wynik

Nagłówek eksportera nie zawierał jawnych granic wartości i przelicznika
sygnału. Dodatkowo używał LF: w sprawdzonej wersji WSxM dopisanie pól
przy zachowaniu LF nie wystarczało. Działający zapis używa **CRLF** oraz
sekcji `[Miscellaneous]` z `Minimum`, `Maximum`, `Z Scale Factor: 1`
i `Z Scale Offset: 0`. Wartości pikseli nadal są nieprzeskalowanymi float64.

Sprawdzenie dotyczy WSxM 5.0 Develop 12.0 pod Wine 9.0 na Ubuntu.
Nie stanowi odbioru WSxM na Windows ani wszystkich wariantów MPP.

## Powtarzalna próba

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

## Poprawiony plik i zachowanie danych

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

## Lokalna instalacja

WSxM z instalatora użytkownika jest zainstalowany w osobnym prefiksie:
`~/.local/share/wineprefixes/wsxm`. Skrót **WSxM 5.0 Develop 12.0** znajduje
się w menu aplikacji. Bezpośrednie uruchomienie na tym komputerze:

```bash
WINEPREFIX="$HOME/.local/share/wineprefixes/wsxm" wine 'C:\ProgramData\WSxM\WSxM 5.0 Develop 12.0\WSxM.exe' 'Z:\home\rlew\projekty\NEtCAT-viewer\data\test-wsxm.mpp'
```

Podczas startu mogą pojawić się komunikaty połączenia z aparaturą oraz
braku DSP/Dulcinea. W tej instalacji można je zamknąć i przeglądać pliki.
Do widoczności szczegółów każdej klatki: **Settings → Movie Settings →
Palette range → Fit to frame Max/Min values**. Po zatwierdzeniu przejdź
na inną klatkę. Jest to wybór kontrastu, nie zamiennik poprawnego nagłówka.
