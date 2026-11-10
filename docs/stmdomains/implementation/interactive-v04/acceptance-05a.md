# SD-V4-05a — obszary i granice domen

Data: **2026-11-02**. Baza `319c156`, implementacja **`dfcf392`**,
gałąź `domains/interactive-v04-ui`. **Ręczny odbiór użytkownika potwierdzony
2026-11-02 dla wersji `617b006`** słowami „testy manualn ok”.
Ticket dodano do planu i wykonano na polecenie użytkownika.

Zapis potwierdzenia zmienia wyłącznie dokumentację. `git diff --check` PASS;
testów kodu nie ponawiano. Następny ticket: **06 — strojenie tworzenia domen**.

## Uruchomienie i test ręczny

W katalogu `/home/rlew/projekty/NEtCAT-domains`:

```bash
conda activate netcat
python -m stmdomains.main
```

1. Otwórz `data/TTMAPP/detection_full.moltrack.json`, w razie potrzeby
   potwierdź istniejący MPP. Wybierz **259**, kliknij **Analizuj klatkę · K5**.
2. Zmaksymalizuj okno, wybierz **Oryginał** i wyłącz **Centra** oraz **Ramki**.
   Widać sześć kolorowych obszarów z obrysami i numerami D1–D6.
   Licznik pozostaje **120 / 312, 6 domen**, jak w 05.
3. Kliknij **Obszary…** przy legendzie. Osobno włączaj/wyłączaj
   **Wypełnienie domen**, **Obrysy domen** i **Numery domen**. Suwak
   **Krycie wypełnienia** działa od 0 do 100%, domyślnie 35%.
   Przy 0% obrysy i numery nadal są widoczne, jeżeli je włączono.
   Menu zamknij kliknięciem poza nim lub Escape.
4. Przełącz **Domeny / Klasy**: kolory obszarów odpowiadają legendzie
   i molekułom. Dwie domeny tej samej klasy zachowują oddzielne obrysy
   oraz numery D. **Wejściowe** ukrywa obszary i wyłącza ich kontrolki.
   Włącz Centra, aby ponownie zobaczyć szare molekuły bez przypisania.
5. Zmień **Oryginał / Wyrównany**, gamma i zoom. Obszary pozostają na tej
   samej części obrazu. Wybrane warstwy i krycie zachowują się przy
   nawigacji; ich zmiana nie uruchamia analizy ani nie zmienia członkostwa.
6. Przejdź do nieanalizowanej klatki: brak starych obszarów. Wróć do 259,
   sprawdź też analizę 7, 120 i 268. Anuluj ponowną analizę oraz przejdź
   do innej klatki podczas obliczeń. Poprzedni poprawny wynik zachowuje
   swoją mapę, a spóźniony wynik nie trafia na inny obraz.
7. Zamknij program podczas kalibracji — terminal wraca bez traceback.

**Maski molekuł** to osobna warstwa wejściowa z MolTrack, dawniej
„Maski / obrysy”. Na 7 dostępne są 318 masek; na 120/259/268 ich nie
zapisano, więc przełącznik jest nieaktywny. Obliczone obszary domen
działają niezależnie. Górny suwak **Krycie masek** dotyczy masek molekuł;
suwak w **Obszary…** dotyczy wypełnienia domen.

### Kontrole bez dodatkowych danych

```bash
python -m stmdomains.tools.analysis_demo
```

Otwórz `.scratch/stmdomains-ui-05/demo/series.moltrack.json`:

| Klatka | Po analizie | Oczekiwany widok |
| --- | --- | --- |
| 1 | 357/405, 17 domen | Wypełnienie, obrysy i numery; Obszary… aktywne |
| 2 | `complete`, 0/405, 0 domen | Brak obszarów, komunikat prawidłowego zera |
| 3 | Brak oznaczeń | Brak obszarów i jawny brak danych |
| 4 | Brak dopasowania klas | Brak obszarów, wyjaśnienie zbyt małej próby |
| 5 przed analizą | Brak analizy | Brak obszarów pozostałych klatek |

## Wykonane sprawdzenia

W istniejącym **netcat**, bez instalacji:

- **8 nowych testów** obliczeń, obrazu i kontrolek: maska zgodna z końcowymi
  ID, powtarzalność, zero/brak wyniku, podział po rasteryzacji, odrzucenie
  małego fragmentu, renumeracja zmieniająca kolejność domen, zachowane
  otwory, kolory, niezależność warstw, geometria ułamkowa i stabilny układ.
  Testy dodawano od brakującego zachowania do działającego przekroju.
- **25 celowanych testów regresji PASS**: publikacja wyników, kolory,
  anulowanie/błędy, układ i dotychczasowe maski molekuł.
- Mypy **41 modułów PASS**:

  ```bash
  python -m mypy --follow-imports=silent --ignore-missing-imports stmdomains/analysis stmdomains/core stmdomains/io stmdomains/ui stmdomains/tools
  ```

- Długości kodu/testów: **13 plików, maksimum 405 linii**;
  `python -m stmdomains.tools.check_code_size --base 319c156`.
- **325 lokalnych odnośników w 8 dokumentach PASS**, graf 19 ticketów
  bez cykli i każdy z testem ręcznym; `git diff --check` PASS.
- Pełny zestaw: **348 passed, bez pominięć, 30,10 s**. Uruchomiony raz
  na koniec, po obu przeglądach:

  ```bash
  QT_QPA_PLATFORM=offscreen OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 python -m pytest -q tests/stmdomains
  ```

### Rzeczywiste dane i GUI

Przy tym samym wejściu wykonano porównanie z kodem 05 z `319c156`:
**identyczne przypisania każdej molekuły, statusy, przyczyny odmów i model**.
Porównanie nie ograniczało się do liczników. Sprawdzono także zgodność
każdej przypisanej molekuły z ID w mapie końcowej.

| Klatka | Przypisane / aktywne | Domeny |
| --- | ---: | ---: |
| 7 | 245 / 317 | 12 |
| 120 | 67 / 248 | 3 |
| 259 | 120 / 312 | 6 |
| 268 | 145 / 308 | 5 |

Rzeczywiste GUI **X11/xcb sterowane Qt**: cztery klatki w raw/aligned,
otwarcie menu Obszary… myszą, przełączniki, krycie, klasy/domeny,
gamma/zoom, przejście do nieanalizowanej klatki, powrót, anulowanie,
wszystkie stany demo oraz zamknięcie podczas kalibracji. **PASS**;
proces zakończył się kodem 0, obie pule workerów bez aktywnych zadań.
Układ 900×650 stabilny podczas analizy/nawigacji; zrzuty okna i menu
obejrzano także w rozmiarze zmaksymalizowanym. Małe okno nadal ma
niewielki obraz, zgodnie z ograniczeniem wcześniejszego układu; do oceny
obszarów zalecana maksymalizacja lub zoom. Nie dodano nowego wiersza UI.

SHA-256 MPP i JSON przed/po identyczne, wejścia takie same jak w
[raporcie 05](acceptance-05.md). Podczas prób dostęp do ZIP i dawnych
artefaktów był blokowany: **0 odczytów**. GUI: maksymalna przerwa pomiędzy
sygnałami testowego timera około **0,233 s**, szczyt RSS około **1462 MiB**.
Pomiary dotyczą tej lokalnej próby, nie są gwarancją dla dowolnych danych.

Artefakty `.scratch/stmdomains-ui-05a/`: `gui-smoke.json`,
`method-smoke.json`, skrypty, demo i zrzuty m.in. `frame-259-raw.png`,
`frame-259-classes.png`, `frame-259-outlines-numbers.png`,
`region-controls-popup.png`, `window-900x650.png`. Pozostają poza Git.
Sprawdzenie agenta jest odrębne od potwierdzonego powyżej odbioru użytkownika.

## Przegląd code-review

Przypięty zakres: `319c156...dfcf392`, dwa niezależne przeglądy.

### Standards

**0 naruszeń reguł, 0 usterek blokujących, brak osobnych uwag heurystycznych.**
Potwierdzono wspólną renumerację mapy i molekuł, własny niemodyfikowalny
bufor, translację i przycięcie nakładki oraz cache tylko aktualnego wyniku.
Podział modułów i zakres zmian zgodny z regułami repo. Niezależnie
uruchomione 8 nowych testów: PASS.

### Spec

**Brak ustaleń wymagających poprawki.** Nie stwierdzono braków, wyjścia
poza zakres ani błędnej realizacji kryteriów. Sprawdzono niezależność
warstw, rozróżnienie masek molekuł, zgodność końcowych map po podziale,
otwory, brak scalania domen przez kolor klasy, geometrię i usuwanie
nieaktualnej nakładki. Niezależnie uruchomione 8 nowych testów: PASS.

Standards: 0 uwag; Spec: 0 uwag. Oba przeglądy bez otwartych usterek.

## Sposób prezentacji i ograniczenia

Wynik zachowuje niemodyfikowalną mapę `int32` w oryginalnej geometrii
klatki. Jest to mapa po rozcięciu barierami, podziale na spójne fragmenty,
minimum ośmiu centrów i wspólnej renumeracji pikseli oraz molekuł.
Odrzucone fragmenty i otwory pozostają zerowe. Obrysy biegną po krawędziach
tych pikseli; nie wygładzamy ani nie wypełniamy braków otoczką wypukłą.
Numer D jest zakotwiczony wewnątrz danego obszaru i zachowuje czytelny
rozmiar przy zoomie. Kolorowanie klas nie scala granic domen.

Widok używa jednego kolorowego rastra i ścieżek aktualnego wyniku.
Gamma i przesunięcie widoku nie wywołują ponownie budowy obrysów.
Mapa TTMAPP ma **256 KiB na wynik**; limit obrazu 2048² to **16 MiB**
na mapę. Wyniki pozostają w pamięci bieżącej serii jak w 05.
Budowa ścieżek na czterech klatkach trwała około **0,8–2,7 ms**;
kontrola mapy 259 powiększonej do 2048² zajęła około **22 ms**.

To zmiana prezentacji istniejącej metody. Nie jest niezależnym pomiarem
fizycznej granicy ani poprawą trafności detekcji. Nadal obowiązują
ograniczenia 05: lokalne K5, brak wspólnego znaczenia klas między klatkami,
pojedynczy kierunek periodyczności, fragmentacja i przybliżone bariery.
Bez nowych zależności lub zmian wspólnych; wcześniejsze zgłoszenie
zależności integratorowi pozostaje aktualne. Następny ticket: **06**.
