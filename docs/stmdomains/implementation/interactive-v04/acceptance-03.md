# SD-V4-03 — miniatury, odtwarzanie i gamma

Data: **2026-11-02**. [Ticket 03](03-filmstrip-and-playback.md) wykonano na
`domains/interactive-v04-ui`, baza `d862333`, implementacja **`93701af`**.
Poprawki zaznaczenia/pauzy i raport: **`c5deb59`**, stabilność układu okna:
**`0745e4e`**. **2026-11-02 użytkownik potwierdził ręczny odbiór 03 wraz
z poprawką układu** słowami „testy manualne ok”. Następnie zgłosił opisany
poniżej błąd wyjścia. **Ręczny odbiór poprawki wyjścia `3dd8b47` również
potwierdził 2026-11-02 słowami „testy manualne ok”. Odbiór 03 wraz z obiema
poprawkami jest zakończony.**

## Poprawka wyjścia z programu

2026-11-02, baza `0745e4e`, poprawka **`3dd8b47`**, ręczny odbiór potwierdzony.
Zgłoszono awaryjne zakończenie procesu:
`RuntimeError: wrapped C/C++ object of type TaskSignals has been deleted`
przy `finished.emit` w `Task.run`. Reprodukcja w osobnym procesie odtworzyła
ten sam traceback i kod wyjścia 134 dwukrotnie podczas zamykania okna
w trakcie odczytu pliku.

Przyczyną było niszczenie obiektów Qt przed zakończeniem pracy wątków.
Anulowanie odrzucało wynik, lecz worker nadal potrzebował swojego obiektu
sygnałów do zakończenia `run`. Na `aboutToQuit` okno zatrzymuje teraz oba
źródła pracy i timery, a następnie dołącza własne pule kontrolera i miniatur
przez `waitForDone`, przy żywych obiektach Qt. Dotyczy to zamknięcia ostatniego
okna oraz `QApplication.quit()`. Nie zależy od dostarczenia slotów GUI
i nie przerywa siłowo odczytu. Proces może chwilę zaczekać na trwającą
operację, zanim wróci do powłoki.

W `netcat`: **25 celowanych testów PASS**, w tym **4 nowe regresje osobnych
procesów** dla importu/miniatur × zamknięcie okna/wyjście aplikacji. Testy
sprawdzają rzeczywisty koniec procesu, brak traceback i zakończenie pracy
pul przed destrukcją Qt. Kontrolowane opóźnienia dotyczą odczytu pliku
i obliczeń NumPy; zwalnia je osobny wątek, niezależnie od pętli GUI.
Te cztery przypadki sprawdzono także na **X11/xcb: 4 PASS**. Pierwotna
reprodukcja również kończy się teraz kodem 0. Dodatkowo **3/3 rzeczywiste
próby TTMAPP na X11 PASS**: zamknięcie podczas importu, przygotowywania
miniatur po pierwszym obrazie i odtwarzania. Każdy proces kończy się kodem 0,
bez stderr i z obiema pulami bez aktywnych wątków. Mypy **27 plików PASS**;
**5 zmienionych/nowych plików kodu i testów, maksimum 341 linii**.
Przegląd poprawki bez uwag. Pełnego zestawu testów aplikacji nie powtarzano.
Lokalne skrypty diagnostyczne pozostają w `.scratch/stmdomains-ui-03/shutdown-debug/`.

**Scenariusz ręczny (odbiór potwierdzony):** uruchom program w `netcat`, otwórz TTMAPP
i zamknij okno podczas ładowania lub odtwarzania. Sprawdź również wyjście
przez **Plik → Zakończ**. Terminal powinien wrócić do znaku zachęty bez
traceback ani „Przerwane (zrzut pamięci)”. Potwierdzony odbiór funkcji 03
i stabilności układu pozostaje zachowany; ten scenariusz dotyczy poprawki wyjścia.

## Poprawka po zgłoszeniu użytkownika — stabilny układ okna

2026-11-02, baza `c5deb59`, poprawka **`0745e4e`**, odbiór ręczny potwierdzony
przez użytkownika. Pokazywanie paska postępu i przycisku **Anuluj**
zwiększało wysokość dolnego wiersza. W odtworzonym przypadku obraz kurczył
się o **8 px**, a suwak i miniatury przesuwały się o tę samą wartość.
Ukryte elementy zachowują teraz swoje miejsce w układzie; informacja
o ładowaniu i anulowanie pozostają dostępne.

Regresja w `test_window_layout.py` odtworzyła błąd dwukrotnie przed poprawką.
Po poprawce sprawdza rzeczywiste żądanie klatki przy zajętych workerach Qt,
geometrię okna/obrazu/nawigacji przed ładowaniem, w trakcie i po zakończeniu
lub anulowaniu, dla okien **1100×760** oraz **900×650**.

W `netcat`: **13 celowanych testów okna PASS** (w tym 4 nowe przypadki
regresyjne), mypy **27 plików PASS**. Kod/testy: **331/71 linii**.
Pełnego zestawu 300 testów z pierwotnego odbioru nie powtarzano.
Rzeczywiste GUI X11: **12 przejść** przez klatki TTMAPP 1/40/41/64/69/268
w obu rozmiarach, widok wyrównany. Geometria pozostała identyczna w cyklu
gotowe → ładowanie → nowa klatka, również przy zmianach komunikatów masek
i oznaczeń. Obejrzano zrzut mniejszego okna. Artefakty lokalne:
`.scratch/stmdomains-ui-03/layout-debug/`. Bez nowych zależności.

**Ręcznie:** uruchom aplikację ponownie, ustaw zwykłe okno około 900×650,
otwórz TTMAPP i zmieniaj klatki numerem, suwakiem oraz miniaturami.
Włącz także odtwarzanie. Podczas pojawiania się komunikatu o ładowaniu
obraz, suwak i pasek miniatur mają pozostać na miejscu, bez zmiany rozmiaru.
Jeśli przygotowanie trwa wystarczająco długo, sprawdź **Anuluj** — układ
również ma pozostać nieruchomy. To poprawka 03; kolejny ticket 04 nie jest
częścią tego zgłoszenia. Poniżej zachowano pierwotny raport implementacji.

## Uruchomienie i test ręczny

W katalogu `/home/rlew/projekty/NEtCAT-domains`, w środowisku **netcat**:

```bash
python -m stmdomains.main
```

1. Otwórz `data/TTMAPP/detection_full.moltrack.json`. W razie potwierdzenia
   daty MPP sprawdź ścieżkę i wybierz **Użyj tego pliku**. Zapis otwiera
   **klatkę 268 w widoku Wyrównany**: przywracamy zapisany tryb, jeżeli
   geometria jest dostępna. To zmiana względem początkowego Oryginału w 02.
2. Kliknij miniaturę, przeciągnij suwak, wpisz numer klatki. Obraz, oznaczenia,
   zaznaczona miniatura, suwak i numer mają wskazywać tę samą klatkę.
   Miniatury pojawiają się stopniowo w widocznym fragmencie paska; pasek można
   przewijać poziomo. Prawy przycisk myszy nie zmienia zaznaczenia.
3. Wybierz **1 kl./s**, uruchom **Odtwórz**, użyj **Pauza** i odczekaj chwilę:
   numer oraz obraz mają pozostać bez zmian. Wznów i sprawdź także 2, 5, 10
   oraz 20 kl./s. To maksymalne tempo przeglądania; wolne przygotowanie
   obrazu spowalnia odtwarzanie, zachowując wszystkie klatki po kolei.
   Na końcu odtwarzanie się zatrzymuje, a przycisk zmienia się na
   **Od początku**. Osobny przycisk **Od początku** działa również w środku serii.
4. Podczas odtwarzania wybierz klatkę ręcznie albo otwórz **Informacje
   o klatce…**. Odtwarzanie ma się zatrzymać. Edycja numeru, gamma i wybór
   innego pliku również zatrzymują odtwarzanie. Szybka sekwencja wyboru
   miniatury, Play i Pauza nie może później zmienić zatrzymanego obrazu.
5. Ustaw **Gamma 2**: półtony dużego obrazu jaśnieją, miniatury zachowują
   oryginał przy gamma 1. Sprawdź 0,5 i przycisk **Gamma 1**. Zakres kontrolki
   wynosi 0,2–5. Gamma nie zmienia oznaczeń ani danych pomiarowych.
6. Powiększ obraz i włącz wybrane warstwy. Przejście do kolejnych klatek
   zachowuje zoom, gamma i ustawienia warstw. Przełącz **Oryginał/Wyrównany**:
   oba używają kontrastu wyliczonego z oryginału; zmiana układu dopasowuje
   widok do nowego płótna. Sprawdź również zmianę rozmiaru okna.
7. Przygotuj krótką serię kontrolną:

   ```bash
   python -m stmdomains.tools.browsing_demo
   ```

   Otwórz `.scratch/stmdomains-ui-03/demo/series.moltrack.json`. Osiem klatek
   ma ruchomy jasny prostokąt z oznaczeniem `frame-N`, odpowiadającym numerowi
   klatki. **Klatka 3** zawiera wyłącznie NaN/inf: pojawia się informacja
   o braku próbek i znikają poprzedni obraz oraz oznaczenia. **Klatka 4**
   jest stała i bez oznaczeń: jednolita szarość przy gamma 1, jaśniejsza
   przy gamma 2. Od klatki 5 wracają obraz i poprawne oznaczenie.
   Plik `single.moltrack.json` w tym samym katalogu zawiera jedną klatkę:
   odtwarzanie i zbędna nawigacja są wyłączone, a gamma i obraz dostępne.
   Szczegóły geometrii zapisano w wygenerowanym `README.txt`.

## Wykonane sprawdzenia

W istniejącym **netcat**, bez instalacji pakietów:

- **21 nowych testów**: 12 gamma/renderera, 3 miniatur, 5 kontrolera oraz
  1 całego okna. Obejmują wspólny kontrast raw/aligned, stałe i niepoprawne
  próbki, zachowanie masek, ograniczenia cache, zmianę serii, potwierdzanie
  wyboru klatki, pauzę, koniec, odtwarzanie bez pomijania, opóźnioną pracę
  w rzeczywistych wątkach Qt, jedną klatkę i zapisany tryb widoku.
- **Pełny zestaw STM Domains: 300 passed, bez pominięć, 13,58 s**.
  Uruchomiono go raz po poprawkach i przeglądzie:

  ```bash
  QT_QPA_PLATFORM=offscreen OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 python -m pytest -q tests/stmdomains
  ```

- Mypy **27 plików PASS**, także sprawdzany w trakcie implementacji:

  ```bash
  python -m mypy --follow-imports=silent --ignore-missing-imports stmdomains/core stmdomains/io stmdomains/ui stmdomains/tools
  ```

- Kontrola długości **12 plików PASS, maksimum 327 linii**:

  ```bash
  python -m stmdomains.tools.check_code_size --base d862333
  ```

- Rzeczywiste GUI X11/xcb, sterowane przez Qt: TTMAPP, wszystkie tempa,
  pełne odtworzenie **268 klatek** przy ustawieniu 20 kl./s, pauza/wznowienie,
  koniec/restart, miniatury, gamma, zoom i pauza przed dialogiem. Dla każdej
  publikacji sprawdzono zgodność obrazu, indeksów oznaczeń, numeru, suwaka
  i paska miniatur. Sprawdzono także kontrolne klatki bez skończonych próbek,
  stałą klatkę i serię jednej klatki. Obejrzano zrzuty okna.
- Po końcowych poprawkach ponownie sprawdzono ich zakres na X11:
  **9 testów miniatur/kontrolera/okna PASS**, obejmujących prawy przycisk
  myszy i pauzę podczas oczekującego ręcznego żądania klatki.
- SHA-256 wejściowego JSON i MPP przed/po próbie GUI pozostały identyczne.
  Sprawdzono lokalne odnośniki dokumentacji i `git diff --check`.

To techniczne sprawdzenie agenta, odrębne od ręcznego odbioru użytkownika.
Artefakty lokalne: `.scratch/stmdomains-ui-03/gui_smoke.py`, `gui-smoke.json`,
zrzuty `opened.png`, `end.png`, `gamma-2.png`, `invalid-samples.png`,
`single.png` i przykłady `demo/`; pozostają poza Git.

## Zachowanie i ograniczenia

Kontrast 2–98 percentyla jest wyznaczany z oryginalnej klatki. Gamma używa
`u ** (1/gamma)` przed zamianą na 8 bitów, z tym samym zakresem dla raw
i aligned. Miniatury pokazują wyłącznie oryginał przy gamma 1. Zapisany tryb
wyrównany jest przywracany tylko przy dostępnej geometrii; inaczej działa raw.

Odtwarzanie planuje jeden następny krok po opublikowaniu kompletnego obrazu
z oznaczeniami. Nie nadrabia czasu przez pomijanie klatek. Pauza odrzuca
oczekujący krok, również przejęty przez Play z ręcznej nawigacji. Nie przerywa
siłowo obliczenia już trwającego w wątku. Zmiana gamma lub trybu widoku
zatrzymuje serię do inspekcji.

Miniatury są przygotowywane pojedynczo poza wątkiem GUI, dla widocznego
fragmentu i sąsiadów. Cache mieści **64 rastry do 96×64 px**, najwyżej
**1,5 MiB rastrów** plus narzut obiektów Qt. Cache obrazów pozostaje ograniczony
do **3 wpisów/32 MiB**, a masek do **2 wpisów/64 MiB**. Aktualny widok i bufory
mają osobny koszt; JSON i MPP nadal są wczytywane w całości.

Lokalna próba TTMAPP: otwarcie około **0,83 s**, wszystkie 267 przejść po
pierwszej klatce przy limicie 20 kl./s około **17,62 s**, cache miniatur
64 wpisy/**1 MiB** rastrów, szczyt RSS około **1132 MiB**. To pomiar lokalny,
nie gwarancja osiągnięcia 20 kl./s. Tempo przeglądania nie jest czasem pomiaru.
Niepotwierdzona kalibracja TTMAPP i 267 rejestracji o niskiej pewności
zachowują dotychczasowe komunikaty.

## Standards

Niezależny przegląd `d862333...93701af` wykrył **1 uwagę P2**: natywna
obsługa prawego przycisku Qt zmieniała zaznaczenie miniatury bez zmiany obrazu.
Poprawiono obsługę przycisków i dodano przypadek regresyjny, który najpierw
odtworzył błąd. Recenzent potwierdził poprawkę. Nie zgłoszono innych
naruszeń standardów ani istotnych heurystycznych uwag do organizacji kodu.
Bilans: **1 naprawiona, 0 otwartych**.

## Spec

Pierwszy niezależny przegląd tej samej różnicy nie zgłosił niezgodności.
Końcowa kontrola implementacji ujawniła dodatkowo sekwencję ręczna nawigacja
w toku → Play → Pauza, która mogła opublikować spóźniony obraz. Test odtworzył
błąd; Play przejmuje teraz to żądanie, dzięki czemu Pauza je odrzuca.
Recenzent specyfikacji potwierdził zgodność poprawki z zatrzymaniem na aktualnie
pokazanej klatce. Bilans po poprawce: **0 otwartych uwag**.

## Przekazanie integracyjne

Zmiany dotyczą aplikacji, jej testów i dokumentacji. Ticket 03 nie wymaga
nowych zależności. Nadal obowiązuje przekazane wcześniej integratorowi
uzupełnienie wspólnych zależności o NumPy/SciPy oraz testów o pytest-qt.
Lokalny `netcat` ma potrzebne pakiety. **Aktualizacja planu 2026-11-02:**
następny ticket to **SD-V4-05 — klasy i domeny obliczane z danych**.
Późniejszy import wyników 04 został wycofany na polecenie użytkownika;
aktualny kod odpowiada odebranemu 03 z poprawkami. Historyczny odbiór całego
szkieletu oraz badawcze 04/13 pozostają osobnymi, otwartymi zadaniami.
