# SD-V4-01 — działający import i przeglądanie obrazów

Data: **2026-11-02**. [Ticket 01](01-open-images.md) wykonano na gałęzi
`domains/interactive-v04-ui`, od bazy `4c4825f`. Implementacja: `347a2b5`;
końcowe poprawki po przeglądzie i ten raport są w kolejnym commicie zadania,
wskazanym w odpowiedzi końcowej.

## Uruchomienie i ręczne sprawdzenie

W katalogu `/home/rlew/projekty/NEtCAT-domains`, w środowisku **netcat**:

```bash
python -m stmdomains.main
```

Zweryfikowany interpreter i sposób sprawdzenia środowiska opisuje
[instrukcja uruchomienia](../README.md#uruchomienie-i-środowisko).
Nie trzeba nic doinstalowywać do obecnego lokalnego `netcat`.

1. Kliknij **Otwórz zapis MolTrack…** i wybierz
   `data/TTMAPP/detection_full.moltrack.json`. Program odnajdzie MPP obok JSON.
   Przy komunikacie o zmienionej dacie sprawdź wskazaną ścieżkę i wybierz
   **Użyj tego pliku**, jeśli jest to właściwy pomiar. **Anuluj** zachowuje
   poprzednio otwartą serię.
2. Zapis TTMAPP ma aktywną ostatnią klatkę, więc początkowo pojawi się
   **268 / 268**, obraz 256×256 px. Wybierz kolejno 1, 134, 259 i 268.
   Obraz, numer roboczy i źródłowy muszą zmieniać się razem.
3. Użyj **Poprzednia/Następna**, pola numeru (zatwierdzanego Enterem),
   **Powiększ/Pomniejsz/Dopasuj** i kółka myszy. Powiększony obraz można
   przesuwać przeciągnięciem. Pierwsza i ostatnia klatka blokują odpowiedni krok.
   Zmiana klatki o tych samych wymiarach zachowuje zoom.
4. Przygotuj małe przypadki do kolejnych sprawdzeń:

   ```bash
   python -m stmdomains.tools.demo_inputs
   ```

   Powstaną lokalnie w `.scratch/stmdomains-ui-01/demo/`; instrukcja
   `README.txt` opisuje także oczekiwane położenie niesymetrycznych wzorców.
5. Otwórz `single.moltrack.json`: jedna klatka 48×32 px, nieaktywna nawigacja,
   jasny kwadrat w prawym dolnym i ciemny prostokąt w lewym górnym rogu.
   Następnie `reordered.moltrack.json`: klatki źródłowe **4 → 2**, czasy
   **40 s → 20 s**, bez ponownego odwrócenia kolejności.
6. Otwórz `unknown-version.moltrack.json`: czytelny błąd, wcześniejszy obraz
   pozostaje. Przy `bad-source.moltrack.json` anuluj wskazanie MPP; poprzednia
   seria ma pozostać. Ponów i wskaż `demo.mpp`, aby naprawić źródło.
7. Dla `changed-mtime.moltrack.json` sprawdź oba wybory w potwierdzeniu.
   Podczas otwierania większego zapisu kliknij **Anuluj**: wcześniejszy widok
   pozostaje, a kończący się odczyt nie może go później zastąpić.

To zakres obrazów oryginalnych. Nakładki molekuł i raw/aligned należą do 02;
miniatury, gamma i odtwarzanie do 03. Nie jest to odbiór całego historycznego
szkieletu ani metody wykrywania domen.

## Wykonane sprawdzenia

Środowisko: Python z istniejącego `netcat`, PyQt6, NumPy, pytest/pytest-qt,
mypy. Bez instalacji i zmian wspólnej konfiguracji.

- **35 nowych testów** importu/modelu/widoku: rzeczywisty mały MPP, schema
  1/2/3, niesymetryczna geometria, niestandardowa mapa, relokacja, mtime,
  niepoprawne wejście, pojedyncza klatka, zoom i anulowanie opóźnionego odczytu.
  Test opóźnia wyłącznie granicę systemu plików i potwierdza działanie pętli GUI.
- **Pełny zestaw STM Domains: 230 passed**, bez pominięć, 11,76 s:

  ```bash
  QT_QPA_PLATFORM=offscreen OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 python -m pytest -q tests/stmdomains
  ```

  To pełny zestaw aplikacji, nie wszystkich pozostałych programów repozytorium.
- **Mypy: 14 plików, bez błędów**; sprawdzany także podczas implementacji:

  ```bash
  python -m mypy --follow-imports=silent --ignore-missing-imports stmdomains/core stmdomains/io stmdomains/ui stmdomains/tools
  ```

- **Rozmiar kodu: 16 nowych/zmienionych plików, maksimum 209 linii**:

  ```bash
  python -m stmdomains.tools.check_code_size --base 4c4825f
  ```

  Narzędzie sprawdza fizyczne linie, zgłasza wymagane uzasadnienie powyżej
  1000 i błąd powyżej 1500; obejmuje także niewersjonowany jeszcze kod.
- Wejście `python -m stmdomains.main` uruchomiono w offscreen i potwierdzono
  działającą pętlę zdarzeń przed kontrolowanym zakończeniem próby.
- **Rzeczywisty ekran X11/xcb `:1`:** automatycznie sterowane okno,
  prawdziwy dialog potwierdzenia mtime, TTMAPP 268×256×256, klatki
  1/40/41/64/68/69/134/259/268, zoom/dopasowanie oraz przykład jednej klatki.
  Przejrzano wizualnie zrzuty obrazu i dialogu. Powtórzono po poprawieniu tekstów UI.
- Dodatkowo przegląd standardów sprawdził zamknięcie okna podczas zadania:
  okno zamyka się bez oczekiwania na odczyt, a porzucone zadanie kończy się
  i zwalnia zasoby. Nie jest siłowo przerywane.
- Lokalne odnośniki dokumentacji i `git diff --check`.

**Odbiór ręczny przez użytkownika pozostaje do wykonania** według powyższych
kroków. Sterowanie Qt i ogląd zrzutów przez agenta są sprawdzeniami technicznymi;
nie są deklaracją wykonania tych kroków przez użytkownika.

## Dane i pomiary lokalne

MPP: `data/TTMAPP/MOVIE_23raw_TTMAPP_I_AU111.MPP`, zapis:
`data/TTMAPP/detection_full.moltrack.json`. Import zachowuje mapę 0…267,
aktywny indeks 267 oraz wejściowe sekcje dla przyszłych oznaczeń, bez dekodowania
masek. Loader jest wywoływany bez odwracania kolejności; jego obrót macierzy
o 180° sprawdzono na znanym niesymetrycznym przykładzie.

Jednorazowa próba okna: otwarcie około **0,72 s**, łącznie z automatycznym
potwierdzeniem źródła; przejścia klatek około **0,01–0,02 s**, z interwałem
sprawdzania gotowości w skrypcie. Maksymalny RSS procesu około **1051 MiB**.
To pomiar lokalny, nie gwarancja czasu dla innych danych. Czytnik materializuje
cały MPP, a JSON jest odczytywany w całości; import nie jest strumieniowy.
Anulowanie odrzuca wynik, ale trwający odczyt może potrzebować czasu na zakończenie.

TTMAPP ma zastępcze czasy i niepotwierdzoną kalibrację: UI pokazuje px oraz
„czas nieznany”. Historyczny zapis nie ma rozmiarów raw ani hasha odniesienia;
ograniczenie weryfikacji jest jawne. Metadane zgodne z zapisem nie dowodzą
identyczności nieznanej historycznej zawartości. Źródła pozostają niezmienione.

Artefakty lokalne: `.scratch/stmdomains-ui-01/gui-smoke.json`, skrypt
`gui_smoke.py` oraz `frame-1.png`, `frame-259.png`, `mtime-confirmation.png`
i `single-frame.png`. Nie trafiają do Git. Dostęp do rzeczywistego ekranu
wymagał uruchomienia sprawdzenia poza piaskownicą; testy offscreen działały w niej.

## Standards

Przegląd niezależnego agenta dla `4c4825f...347a2b5`: brak twardych naruszeń
standardów. Zachowano lokalne granice modułów, publiczny czytnik MPP,
rozdzielenie Qt od modelu, GUI od pracy w tle oraz anulowanie bez kończenia wątku.
Nie znaleziono istotnych przypadków zbędnych abstrakcji ani innych smells.

Jedna uwaga do czytelności: techniczne nazwy metadanych i stałe zastrzeżenie
w stopce. Poprawiono nazwy na język użytkownika, usunięto zbędny komunikat
i nazwano przyciski potwierdzenia po polsku. Agent sprawdził końcowe hunki:
**uwaga zamknięta, bez nowych uwag**.

## Spec

Niezależny przegląd `4c4825f...347a2b5`: brak istotnych niezgodności,
braków implementacji lub rozszerzenia zakresu SD-V4-01. Sprawdzono zachowanie
mapy i orientacji, walidację, relokację, potwierdzenie mtime, ochronę poprzedniej
serii, pojedynczą klatkę oraz brak fikcyjnych jednostek. Oznaczenia i wyrównanie
pozostają poza bieżącą funkcją zgodnie z ticketem.

Końcowy bilans przeglądu: **Standards — 0 otwartych uwag (1 poprawiona);
Spec — 0 uwag**.

## Przekazanie integracyjne

Zmiany wyłącznie w `stmdomains/`, jego testach i dokumentacji. Wspólny czytnik,
konfiguracja główna i CI pozostają bez zmian. Główny plik zależności szkieletów
nadal wymienia sam PyQt6; instalacja z niego nie jest pełnym środowiskiem nowej
funkcji. Integrator powinien uwzględnić używany przez importer NumPy
oraz pytest-qt dla testów; przyszłe wyrównanie będzie potrzebowało SciPy.
Obecne lokalne `netcat` zawiera te zależności.
