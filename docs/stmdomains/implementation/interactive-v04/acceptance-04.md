# SD-V4-04 — otwieranie zapisanych domen v0.4

Data: **2026-11-02**. Implementacja na `domains/interactive-v04-ui`, baza
`24625f2`, commit **`b6159ac`**. Funkcja gotowa do ręcznego odbioru użytkownika;
jego potwierdzenie pozostaje do uzyskania. Odbiór 01–03 jest zachowany.

## Uruchomienie i test ręczny

W `/home/rlew/projekty/NEtCAT-domains`, w środowisku **netcat**:

```bash
python -m stmdomains.main
```

1. Otwórz `data/TTMAPP/detection_full.moltrack.json`. Jeśli aplikacja prosi
   o potwierdzenie MPP, sprawdź ścieżkę i wybierz **Użyj tego pliku**.
2. Kliknij **Otwórz wynik v0.4…** i wskaż pełną paczkę
   `data/new_code/stm_domains_prototype_v04.zip`. Możesz też wskazać
   `MANIFEST_v04.json` w rozpakowanym katalogu kompletnej paczki. ZIP
   zawierający wyłącznie kod nie jest wynikiem. Bieżąca klatka pozostaje
   wybrana; domyślnie włączają się kolory **Domeny (lokalne)**.
3. Wybierz poniższe klatki i porównaj liczniki. Włącz **Centra**, a ramki
   i maski wyłącz, jeśli przeszkadzają w ocenie. Zmaksymalizuj okno lub
   powiększ obraz. Przy 900×650 rozbudowane kontrolki zostawiają tylko
   około 100 px wysokości dopasowanego obrazu.

   | Klatka | Oznaczenia | Aktywne | Przypisane | Domeny | Duplikaty pominięte |
   | --- | ---: | ---: | ---: | ---: | ---: |
   | 7 | 318 | 317 | 278 | 5 | 1 |
   | 120 | 249 | 249 | 54 | 3 | 0 |
   | 160 | 218 | 218 | 0 | 0 | 0 |
   | 259 | 312 | 312 | 129 | 6 | 0 |
   | 268 | 308 | 308 | 151 | 5 | 0 |

4. Na klatce 7 przełącz **Klasy (końcowe)**: `q: 249`, `w: 29`, pozostałe
   klasy mają zero przypisań. Wróć do Domen: różne domeny klasy q mają
   różne kolory. Dłuższą legendę można przewijać poziomo. Kolory i numery
   domen dotyczą jednej klatki; nie oznaczają śledzenia między klatkami.
5. Kliknij szarą molekułę. Opis i dymek pod obrazem podają przyczynę odmowy;
   **Dane oznaczenia…** zawierają pełny rekord. Etykieta wstępna jest
   wyraźnie opisana i nie koloruje molekuły jak końcowe przypisanie.
   Pominięty duplikat jest osobnym stanem, poza mianownikiem aktywnych molekuł.
   Nakładające się oznaczenie aktywne ma pierwszeństwo rysowania/wyboru
   w trybach Domeny/Klasy; **Oznaczenia wejściowe** umożliwiają zwykłą inspekcję.
6. Porównaj klatkę **160** (zapisane **0 domen**, szare molekuły) z **11**
   (**Brak analizy tej klatki**, oznaczenia wejściowe). Nawigacja i odtwarzanie
   przez granicę analizowanego zakresu nie mogą zostawić poprzednich kolorów.
7. Przełącz Oryginał/Wyrównany, zmień gamma i zoom. Wynik ma pozostać na tych
   samych molekułach. Zmiana Domeny/Klasy zachowuje zoom. **Dane wyniku…**
   pokazują pochodzenie, analizowany zakres, zapisane parametry i podsumowanie.
   Otwieranie dialogu zatrzymuje odtwarzanie. Zakończ program — bez traceback.

### Mała kontrola i niezgodny wynik

Przygotuj gotowe pliki poleceniem:

```bash
python -m stmdomains.tools.result_demo
```

Otwórz `.scratch/stmdomains-ui-04/demo/input.moltrack.json`, a następnie
`result.zip` z tego samego katalogu (albo `package/MANIFEST_v04.json`). To sztuczne obrazy do kontroli UI,
nie dane ani referencja skuteczności detektora.

- Klatka 1: **2 domeny tej samej klasy q**, **3 / 4** aktywnych przypisane,
  jedno szare nieprzypisane oznaczenie i jeden pominięty duplikat. W Domenach
  dwie barwy, w Klasach jedna. Szary punkt przy (18, 4) ma niejednoznaczną klasę.
- Klatka 2: **brak analizy**; widoczne wejściowe oznaczenie.
- Klatka 3: **0 domen, 0 / 2**, dwa powody odmowy.
- Mając nadal otwartą tę serię i jej wynik, spróbuj dołączyć ZIP TTMAPP.
  Pojawi się błąd zgodności źródła. Poprzedni obraz, wynik i klatka pozostają.
  Ponowne otwarcie innej serii usuwa poprzedni wynik.

## Wykonane sprawdzenia

W istniejącym **netcat**, bez instalacji pakietów:

- Testy importera, prezentacji, kontrolera i całego okna sprawdzają ID,
  współrzędne, mapę roboczą różną od źródłowej, końcową klasę/domenę,
  liczniki, odmowy, duplikaty, brak analizy, sprzeczne wejście, anulowanie
  i spóźnione wyniki. Testy stanu i kolorów uruchamiano przy implementacji.
- **Pełny zestaw STM Domains: 355 passed, bez pominięć, 16,12 s**, w tym
  **47 nowych przypadków**. Uruchomiono go raz, po poprawkach przeglądu:

  ```bash
  QT_QPA_PLATFORM=offscreen OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 python -m pytest -q tests/stmdomains
  ```
- Mypy: **35 plików produkcyjnego core/io/ui/tools PASS**:

  ```bash
  python -m mypy --follow-imports=silent --ignore-missing-imports stmdomains/core stmdomains/io stmdomains/ui stmdomains/tools
  ```

- Dodatkowy mypy całego `stmdomains` zgłasza **112 błędów w 25 plikach**
  historycznych badań. Sprawdzono także czysty snapshot bazy `24625f2`:
  ten sam wynik 112/25. Nie naprawiano ich w zakresie 04; pełnego katalogu
  nie oznaczamy jako przechodzącego kontrolę typów.
- Kontrola długości: **19 plików kodu i testów, maksimum 395 linii**, PASS:

  ```bash
  python -m stmdomains.tools.check_code_size --base 24625f2
  ```

- Rzeczywiste GUI X11/xcb, sterowane Qt: wszystkie **56 klatek wyniku**
  porównano z niezależnie odczytanym CSV, łącznie **4190 przypisań / 122 domeny**.
  Sprawdzono ID, współrzędne, obie legendy, 12 par klatka/raw-aligned, odmowę
  po kliknięciu, zoom/gamma, odtwarzanie 7–13 i stały układ w 900×650.
  Obejrzano zrzuty. To techniczne sprawdzenie agenta, osobne od odbioru użytkownika.
- Import rzeczywistego ZIP i rozpakowanego manifestu daje ten sam wynik.
  SHA-256 JSON/MPP/ZIP przed/po GUI identyczne. Wyjście ma kod 0, obie pule
  kończą pracę. Artefakty lokalne: `.scratch/stmdomains-ui-04/`, poza Git.
- `git diff --check` oraz lokalne odnośniki zmienionej dokumentacji sprawdzono.
  Istniejący test ramki uwzględnia teraz rasteryzację linii przy ułamkowej
  skali Qt (sąsiedztwo ±1 px); nadal sprawdza kolor w miejscu ramki.

## Standards

Niezależny przegląd `24625f2...b6159ac` nie wykrył naruszeń udokumentowanych
zasad organizacji kodu ani istotnych uwag heurystycznych. Zgłosił dwie
uwagi jakościowe P2: pozostawienie referencji do poprzedniej serii po zmianie
pliku oraz zbyt późną kontrolę zakresu klatek przed dekodowaniem NPZ.
Obie poprawiono. Trzy nowe regresje odtworzyły błędy przed poprawką, po niej
przechodzą. Dodatkowo poprawiono instrukcję demo: dane molekuły otwiera
kliknięcie. Recenzent potwierdził wszystkie poprawki.
**Bilans: 2 P2 i 1 korekta instrukcji naprawione; 0 otwartych uwag.**

## Spec

Niezależny przegląd tej samej różnicy: **0 uwag**. Potwierdzono powiązanie
źródeł/obrazów/map/ID, rozdzielenie końcowych klas i domen od etykiet wstępnych,
stany odmowy/duplikatu/braku analizy oraz atomową publikację wyniku i klatki.
Nie stwierdzono brakujących wymagań ani rozszerzenia zakresu o analizę/trening.
Mały obraz w małym oknie pozostaje jawnym ograniczeniem użyteczności.
**Bilans: 0 otwartych uwag.**

## Zachowanie i ograniczenia

Importer sprawdza manifest wymaganych plików, SHA-256 źródeł, rzeczywiste
obrazy, mapy klatek, ID, współrzędne i zgodność podsumowań z przypisaniami.
Odczytuje JSON/CSV/NPZ; nie wykonuje kodu paczki ani nie ładuje pickle/joblib.
Weryfikacja i przygotowanie widoku działają w tle. Przerwana lub błędna
operacja zachowuje poprzedni wynik; nowa seria odrzuca spóźniony wynik starej.

Źródłowy JSON/MPP oraz tablice weryfikacyjne są czytane do pamięci.
Lokalny pomiar: otwarcie MolTrack **0,82 s**, wyniku **0,49 s**, szczyt RSS
około **1227 MiB**. To pomiar jednej próby, nie gwarancja wydajności.
Małe okno ma ograniczoną przestrzeń obrazu; powiększenie pozostaje dostępne.

To podgląd zapisanego eksperymentu, bez nowego obliczania ani oceny trafności.
Analiza bieżącej klatki należy do **SD-V4-05**. Wynik obejmuje 56 z 268 klatek:
1–10, 120–123, 160–170, 200–220, 259–268. Klasa i domena są osobne;
klasa wstępna pozostaje diagnostyką. Kalibracja i rejestracja zachowują
dotychczasowe ograniczenia źródła. Badawcze 04/13 pozostają otwarte.

## Przekazanie integracyjne

Zmiany dotyczą wyłącznie STM Domains, jego testów i dokumentacji.
Bez nowych zależności. Wcześniejsza prośba do integratora o NumPy/SciPy
oraz pytest-qt pozostaje aktualna; `netcat` ma potrzebne pakiety.
Następny ticket w kolejności: **05 — Oblicz domeny na bieżącej klatce**.
