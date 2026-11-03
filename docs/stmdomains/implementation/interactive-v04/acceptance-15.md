# Odbiór SD-V4-15 — opis otoczenia i bariery

Data: **2026-11-03**. Baza `bc3de1b`, implementacja `1b0c1de`, poprawki
`9fe24a6` i `9bf767a`. Gałąź `domains/interactive-v04-ui`, worktree
`/home/rlew/projekty/NEtCAT-domains`. [Ticket](15-advanced-descriptors-barriers.md),
[parametry i znaczenie](advanced-settings.md), [przegląd](review-15.md).
Status implementacji: `done`. **Odbiór ręczny użytkownika 15 potwierdzony 2026-11-03 dla wersji `f129ac2` („testy manualne ok”).**

Potwierdzenie użytkownika dotyczy odbioru funkcji. Aktualizacja statusu
zmienia tylko dokumentację; nie ponawiano testów aplikacji ani GUI.
Poniższe wyniki testów dokumentują wcześniejszą weryfikację implementacji.

## Działająca funkcja

**Analiza → Analiza… → Zaawansowane** udostępnia sigma, histogram odległości
i kąta, zakres długości par oraz maksimum PCA. Zmiana opisu wymaga nowego
dopasowania z danych; istniejący katalog o innym opisie blokuje analizę.
Osobno można regulować sześć parametrów barier i zachować model klas.
Niepoprawna konfiguracja blokuje uruchomienie z komunikatem. Zbyt słabe
dane zachowują dotychczasowy mechanizm odmowy, bez zastępowania wyniku.

Pomarańczowa warstwa pokazuje maskę barier rzeczywiście używaną przy
tworzeniu domen. Przełączanie poprzedni/nowy obejmuje maskę; edycja szkicu
nie zmienia obrazu. Projekt zapisuje parametry, maskę i oddzielny szkic,
a PNG może zawierać tę diagnostykę. Stare projekty pozostają czytelne.
Szczegóły ograniczeń detektora są w UI i [opisie ustawień](advanced-settings.md).

## Wykonane sprawdzenia

Wszystkie uruchomienia aplikacji i testów używały istniejącego środowiska
`netcat`, sprawdzonego przez `sys.executable`:
`/home/rlew/projekty/conda-migration-ubuntu-20261008/envs/netcat/bin/python`.
Nie instalowano zależności ani nie zmieniano modułów wspólnych.

TDD prowadzono na granicach analizy, rzeczywistego formularza i zapisu:
zmieniony wymiar cech/PCA i nowe ID, dopasowanie lokalne/wspólne/Auto,
odrzucenie niezgodnego katalogu przed odczytem klatki, zmiana barier bez
PCA/KMeans, zachowanie ustawień przy przeliczeniu domen, błędny szkic
i zamknięcie, zapis maski oraz diagnostyka PNG raw/aligned i wycinek.
Test regresji zakresu 0,2–0,3 był RED, po poprawce GREEN; węższy zakres
pozostaje odrzucany. Zaktualizowano kontrolę leniwego odczytu projektu:
żądana klatka ładuje maskę domen i barier, pozostałe nie są materializowane.

Pierwsza pełna regresja: 509 PASS i 1 FAIL. Istniejący test wykrył zbyt
słabą kontrolę opisu przed użyciem zachowanych decyzji domen. `9bf767a`
porównuje opis z katalogiem; testy zachowują legalny opis niestandardowy
i odrzucają podmianę samych parametrów. 26 testów obszaru PASS (13,61 s),
następnie ponowiono pełny zestaw. Logi pierwszego przebiegu zachowano jako
`full-tests-before-tuning-fix-part-{1,2}.log`.

Końcowa pełna regresja: **510 testów PASS** — 229 w 119,13 s oraz
281 w 103,70 s. Uruchomiono raz każdy z 71 plików
testowych w dwóch rozłącznych grupach (35 i 36 plików), aby uniknąć
przerwania zbyt długiego procesu obserwowanego przy tickecie 14.
Qt offscreen; `OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1`.
Logi: `.scratch/stmdomains-ui-15/full-tests-part-{1,2}.log`;
dokładne listy plików: `test-files-{1,2}.json` w tym samym katalogu.

Kontrola typów **92 modułów PASS**:

```bash
python -m mypy --follow-imports=silent --ignore-missing-imports \
  stmdomains/analysis stmdomains/core stmdomains/io stmdomains/ui stmdomains/tools
```

Oba przeglądy zakończono: Standards 0 uwag, Spec 1 P3 zamknięte,
0 otwartych. 32 zmienione pliki kodu/testów mają najwyżej **474 linie**,
bez wyjątku od limitu 1000/1500. Kontrola dokumentów i `git diff --check`
uzupełniona w przekazaniu.

## Wykonany odbiór natywnego GUI

Qt X11 (`xcb`) w `netcat`, rzeczywiste okna i kontrolki, automatycznie
sterowane przez harness. Zrzuty okna ustawień i PNG obejrzano.
Nie jest to potwierdzenie osobistego odbioru przez użytkownika.
Próba dotyczy implementacji `1b0c1de`; późniejsze poprawki walidacji
`9fe24a6` i `9bf767a` mają osobne regresje i rechecki przeglądów.

Wejście: `data/TTMAPP/detection_full.moltrack.json` oraz
`data/TTMAPP/MOVIE_23raw_TTMAPP_I_AU111.MPP`. SHA-256:

```text
MPP: 8fbbfa5d515a90552c13cee2dbd289ff5cc16f000315547185c2a57bfe9f7c66
JSON: d0c4cb999bede28edb5dfd18ddbe146054711382f1c78363055be2330b3cdd2e
```

Analiza klatki **259**, ręczne **K5**, dopasowanie **259–268**, pozostałe
progi bazowe. Numery w UI od jedynki, rozmiar pola 480 × 480 px.

| Próba | Przypisane/aktywne | Domeny | Piksele barier | PCA | ID katalogu, skrót |
| --- | --- | --- | --- | --- | --- |
| Bazowe parametry | 105/312 | 5 | 691 | 24 | `9d3b7286` |
| Sigma 1,7, maksimum PCA 12, nowe klasy | 113/312 | 6 | 691 | 12 | `8e16126d` |
| Istniejące klasy, górny percentyl 98, poszerzenie 0,25 | 113/312 | 6 | 664 | 12 | `8e16126d` |
| Bazowe parametry i ponowne dopasowanie | 105/312 | 5 | 691 | 24 | `9d3b7286` |

Odtworzono dokładnie te same przypisania, katalog i maskę bazową, nie
tylko liczniki. Zmiana samych barier nie dopasowała PCA/KMeans: podczas
próby wywołania dopasowania były blokowane na granicy bibliotek.
Zapis i ponowne otwarcie zachowały rzeczywiste ustawienia sigma 1,7/PCA12,
maskę i włączoną warstwę oraz osobny szkic sigma 2. Niezgodny szkic
blokował kolejne użycie tego katalogu; odczyt niczego nie dopasował.

Kontrola syntetyczna z dodatnimi skokami obrazu: klatka 2 pliku
`.scratch/stmdomains-ui-15/demo/series.moltrack.json`. Bazowo 0/405,
0 domen i 29 448 pikseli barier. Po zmianie minimalnej długości X na
100 rozstawów i dylatacji na 0: 389/405, 5 domen, 0 pikseli barier,
ten sam katalog `a951f409`. Potwierdza wpływ bariery na wynik; nie dowodzi,
że wyłączenie przeszkód daje fizycznie poprawniejsze domeny.

Niepoprawne progi i anulowanie zachowały poprzedni kompletny wynik.
Nawigacja i zamknięcie działały; 1495 sygnałów kontrolnych pętli GUI,
największa przerwa 0,205 s. Hash źródeł pozostał niezmieniony. Strażnik
odczytu potwierdził brak użycia paczki v0.4 i historycznych artefaktów 04.
Recenzent otworzył również oba rzeczywiste projekty z ticketu 13:
wynik 105/312 zachowany, brak maski barier jawny.

Lokalne artefakty poza Git: `.scratch/stmdomains-ui-15/` — `report.json`,
`native.log`, `gui_smoke.py`, `advanced-settings.png`, `ttmapp-barriers.png`,
`ttmapp-barriers-export.png`, `advanced.stmdomains` i dane kontroli.

## Test ręczny użytkownika

Uruchom w tym worktree:

```bash
conda activate netcat
python -m stmdomains.main
```

1. Otwórz `data/TTMAPP/detection_full.moltrack.json`, przejdź do **259**.
   W **Analiza → Analiza… → Zakres** wybierz bieżącą klatkę. W **Klasy**
   wybierz **Dopasuj nowe klasy**, ręczne **K5** i zakres dopasowania
   **259–268**. Kliknij **Przywróć bazowe parametry**, potem **Analizuj**.
   Oczekiwane: 105/312, 5 domen, katalog zaczynający się `9d3b7286`.
2. W **Zaawansowane** zmień sigma na **1,7**, maksimum PCA na **12**.
   Kliknij **Analizuj**. Oczekiwane: nowy katalog `8e16126d`, 113/312,
   6 domen. Porównaj **Nowy/Poprzedni wynik**; szkic nie zmienia się.
3. Wróć do nowego wyniku. W **Klasy** wybierz **Użyj istniejących klas**
   i jego katalog. W **Zaawansowane** ustaw górny percentyl **98** oraz
   poszerzenie **0,25**. Przewiń zakładkę i zaznacz **Pokaż bariery…**.
   Przed analizą widać starą maskę. Po **Analizuj** ID klas jest zachowane,
   maska ma 664 zamiast 691 pikseli. Liczniki domen mogą pozostać takie same.
4. Przełącz widok surowy/wyrównany. Pomarańczowe bariery pozostają w tym
   samym miejscu obrazu; po wyłączeniu podglądu nie zmienia się wynik.
   Wyeksportuj PNG z włączoną diagnostyką i sprawdź jej obraz oraz legendę.
5. Zapisz projekt, otwórz go ponownie: przypisania, ustawienia, maska
   i widoczność pozostają zachowane. Można analizować z zapisanymi klasami.
6. Przy istniejących klasach zmień sigma: **Analizuj** jest zablokowane
   z informacją o wymaganym dopasowaniu. Wybierz **Dopasuj nowe klasy**.
   Ustaw dolny percentyl 99 przy górnym 98: błędne progi również blokują.
   Przywróć parametry bazowe i ponownie dopasuj na tym samym zakresie:
   wraca wynik z punktu 1. Rozpocznij jeszcze jedną próbę i od razu anuluj;
   poprzedni kompletny wynik pozostaje dostępny.
7. Opcjonalnie w **Zakres** wybierz dwie klatki i użyj istniejących klas:
   obie dostają wynik z tymi samymi ustawieniami. Sam zakres dopasowania
   z zakładki **Klasy** nie zleca analizy domen na wszystkich jego klatkach.

## Ograniczenia

To udostępnienie parametrów istniejącej metody. Brak nowego detektora
molekuł, barier lub treningu sieci. Więcej przypisań nie oznacza większej
zwalidowanej wykrywalności. Nie wykonano oceny jakości względem referencji
ani nowego przebiegu wszystkich 268 klatek z niestandardowym opisem.
Odbiór użytkownika potwierdzono 2026-11-03. Wybór parametrów odpowiednich
dla pomiaru i walidacja naukowa pozostają otwarte. Następny rekomendowany ticket:
[16 — kierunek, rozstaw i jakość geometrii](16-inspect-local-geometry.md).
