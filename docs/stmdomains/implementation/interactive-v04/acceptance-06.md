# SD-V4-06 — strojenie tworzenia domen

Data: **2026-11-02**. Baza `8caa8a7`, implementacja **`98ca8ff`**, poprawka **`36aea1f`**,
gałąź `domains/interactive-v04-ui`. **Odbiór ręczny użytkownika potwierdzony
2026-11-02 dla wersji `a4dcace`** słowami „testy manualne ok”.
Sprawdzenie agenta w rzeczywistym GUI opisano osobno poniżej.

Zapis potwierdzenia zmienia wyłącznie dokumentację. `git diff --check` PASS;
testów kodu nie ponawiano. Następny ticket: **07 — liczba klas i zakres dopasowania**.

## Uruchomienie i test ręczny

W `/home/rlew/projekty/NEtCAT-domains`:

```bash
conda activate netcat
python -m stmdomains.main
```

1. Otwórz `data/TTMAPP/detection_full.moltrack.json`, wybierz **259**,
   kliknij **Analizuj klatkę · K5**. W ustawieniach bazowych oczekiwane
   **120/312 molekuł, 6 domen**. Wyłącz Centra/Ramki, aby oglądać obszary.
2. Otwórz **Analiza → Tworzenie domen…**. Okno można przesunąć obok
   obrazu; pozostaje niemodalne. Zawiera minimum molekuł, odległość
   łączenia, kontrolę geometrii, próg krawędzi, średnicę regionu
   i zasięg maski. Pomoc przy polach objaśnia jednostki i znaczenie.
3. Zmieniaj średnicę **0,50 → 0,55 → 0,60**, za każdym razem klikając
   **Przelicz domeny**. Na tym wejściu trzy wyniki mają 120/312 i 6 domen.
   Sama edycja pola pozostawia obraz i dane wcześniejszego wyniku bez zmian.
4. Ustaw **Pokaż na obrazie → Poprzedni wynik / Nowy wynik**. Zmieniają
   się obszary, przypisania, liczniki i dane wyniku, ale nie zoom ani
   przesunięcie obrazu. Stopka głównego okna pokazuje wybraną wersję.
   Pod przełącznikiem są wartości rzeczywiście użyte w wyświetlanym wyniku;
   pola edycji nadal dotyczą nowego przeliczenia.
5. Kliknij **Przywróć bazowe**, ustaw minimum **6**, przelicz: **127/312,
   7 domen**. Osobno przywróć bazowe, ustaw łączenie **1,80**, przelicz:
   **129/312, 7 domen**. W **Dane…** przy legendzie model i jego zakres
   pozostają te same; zmieniają się parametry tworzenia domen.
6. Przy włączonej geometrii wpisz próg krawędzi **0,70**, średnica **0,50**.
   Komunikat wyjaśnia błędną relację, a **Przelicz domeny** jest nieaktywne.
   **Przywróć bazowe** naprawia pola; dopiero **Przelicz domeny** odtwarza
   120/312 i 6 domen. Przywracanie pól samo nie uruchamia obliczeń.
7. Przejdź do nieanalizowanej klatki, a potem wróć do 259. Wyniki i ich
   wersje są przypisane do właściwej klatki; niewykonane edycje pól nie
   przechodzą do innej klatki. Zmiana widoku raw/aligned i gamma zachowuje
   wybraną wersję wyniku. Anulowanie przeliczenia zachowuje obie ukończone
   wersje; ponowne otwarcie serii usuwa dotychczasowe wyniki.
8. Okno ustawień działa również przed pierwszą analizą: **Przelicz domeny**
   najpierw dopasuje K5. Sprawdź brak oznaczeń i brak danych do K5 w demo
   z `python -m stmdomains.tools.analysis_demo`. Zamknij program podczas
   analizy: terminal powinien wrócić bez traceback.

## Ustawienia i sposób obliczeń

| Parametr | Bazowy | Dopuszczony zakres |
| --- | ---: | --- |
| Minimum molekuł | 8 | liczba całkowita 1–3000 |
| Odległość łączenia | 1,50 | 0,05–10 × odstęp molekuł |
| Kontrola geometrii | zgodność otoczeń całej domeny | włączona / wyłączona |
| Próg krawędzi | 0,20 | 0–1, nie większy od średnicy regionu |
| Średnica regionu | 0,50 | 0–1, nie mniejsza od progu krawędzi |
| Zasięg maski | 0,85 | 0,05–10 × odstęp molekuł |

„Średnica regionu” jest maksymalną różnicą opisów otoczenia, mierzoną
odległością Hellingera; nie jest średnicą przestrzenną w pikselach.
Wyłączenie geometrii pomija oba progi, ale nadal obowiązują klasy,
test porządku, bariery, zasięg łączenia, minimum i spójność maski.
Większy zasięg maski może zmienić powierzchnię bez zmiany przypisań.

`DomainSettings` jest wspólną, niemodyfikowalną konfiguracją obliczeń
oraz metadanych. Minimum stosowane w grafie i po rasteryzacji pochodzi
z tego samego pola. Słownik klas, jego model, lokalne przypisania klas
oraz oceny porządku pozostają zachowane przy strojeniu. Deskryptory
są ponownie wyliczane z danych, podobnie jak bariery; duże tablice
pośrednie nie są przechowywane dla wszystkich klatek.

Przed ponownym użyciem decyzji o klasach sprawdzane są tożsamość serii,
indeksy klatki, SHA-256 treści obrazu i oznaczeń oraz parametry wcześniejszych
etapów. Niezgodne wejście wymaga ponownego **Analizuj klatkę**. Ten górny
przycisk wykonuje pełne dopasowanie i używa ostatnio obliczonych ustawień
tej klatki. Niezastosowany szkic w oknie ustawień działa wyłącznie przez
**Przelicz domeny**. Program zachowuje najwyżej dwie ukończone wersje na
klatkę w pamięci bieżącej serii; trzecie przeliczenie zastępuje najstarszą.
Nie jest to trwały zapis projektu ani katalog klas wspólny dla serii.

## Wykonane sprawdzenia

Interpreter sprawdzono przed uruchomieniem:
`/home/rlew/projekty/conda-migration-ubuntu-20261008/envs/netcat/bin/python`.
Bez instalowania pakietów i zmian modułów wspólnych.

- **25 nowych testów**: wpływ wszystkich sześciu parametrów na kontrolowane
  układy, minimum po grafie i rasteryzacji, niepoprawne zakresy i relacje,
  brak ponownego dopasowania PCA, niezmienne klasy/model/oceny porządku,
  odtworzenie bazowych przypisań i pikseli, niezgodne dane/metoda,
  porównanie/nawigacja, anulowanie i błędy, rzeczywiste kontrolki menu/okna,
  stabilny zoom/przesunięcie oraz poprawne komunikaty, również przy ponowieniu
  analizy po przekroczeniu limitu pikseli lub liczby oznaczeń.
- Celowane testy dotychczasowych wyników, kontrolera, okna i map domen PASS.
- Mypy **45 modułów PASS**:

  ```bash
  python -m mypy --follow-imports=silent --ignore-missing-imports stmdomains/analysis stmdomains/core stmdomains/io stmdomains/ui stmdomains/tools
  ```

- Kod/testy: **12 plików, maksimum 424 linie**;
  `python -m stmdomains.tools.check_code_size --base 8caa8a7`.
- Pełny zestaw po poprawce i przeglądzie: **373 passed, bez pominięć,
  41,51 s**. Uruchomiony raz na koniec:

  ```bash
  QT_QPA_PLATFORM=offscreen OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 python -m pytest -q tests/stmdomains
  ```

- `git diff --check` PASS; **325 lokalnych ścieżek docelowych w 7 dokumentach PASS**.

### Rzeczywiste dane i GUI

Dla `98ca8ff` wykonano **X11/xcb sterowane Qt**: menu otwarte myszą, okno niemodalne,
przeliczanie i porównanie w tej samej pozycji obrazu, wszystkie parametry,
walidacja, przywrócenie bazowego wyniku, raw/aligned, gamma, zmiana klatki,
anulowanie, powrót i ponowne otwarcie serii. Układ okna **900×650** stabilny.
Obejrzano zrzuty okna ustawień i wyników. Próba po korekcie skryptu PASS:
wstępny skrypt niepoprawnie porównywał zoom sprzed zmiany raw/aligned;
sprawdzenie gamma odnosi się teraz do bieżącego widoku po tej zmianie.

Każdy poniższy wariant zmienia jeden parametr względem bazowego wyniku,
a klasy i model pozostają te same:

| Klatka 259 / wariant | Przypisane / aktywne | Domeny |
| --- | ---: | ---: |
| Bazowy, średnica 0,50 | 120 / 312 | 6 |
| Średnica 0,55 | 120 / 312 | 6 |
| Średnica 0,60 | 120 / 312 | 6 |
| Minimum 6 | 127 / 312 | 7 |
| Łączenie 1,80 | 129 / 312 | 7 |
| Próg krawędzi 0,30 | 120 / 312 | 6 |
| Zasięg maski 1,00 | 120 / 312 | 6 |
| Geometria wyłączona | 120 / 312 | 6 |
| Ponownie bazowy | 120 / 312 | 6 |

Odtworzony wynik ma identyczne przypisania każdej molekuły i mapę pikseli,
nie tylko te same liczniki. W demo potwierdzono dodatni wynik **357/405,
17 domen**, prawidłowe zero **0/405**, brak oznaczeń i brak danych do K5.
Zamknięcie podczas kalibracji: kod procesu **0**, obie pule workerów zakończone.
To sprawdzenie funkcji przez agenta, nie odbiór ręczny użytkownika ani ocena
trafności fizycznej domen.

Wejścia identyczne przed i po próbie (SHA-256):

- `data/TTMAPP/detection_full.moltrack.json`:
  `d0c4cb999bede28edb5dfd18ddbe146054711382f1c78363055be2330b3cdd2e`.
- `data/TTMAPP/MOVIE_23raw_TTMAPP_I_AU111.MPP`:
  `8fbbfa5d515a90552c13cee2dbd289ff5cc16f000315547185c2a57bfe9f7c66`.
- Ten sam `model_id` we wszystkich wariantach:
  `b9d3114433d7a380e044f21d56ee29545d97276d62708e46107fae99bce7fe7d`.

Odczyty ZIP oraz historycznych modeli/wyników były blokowane: **0 odczytów**.
Artefakty lokalne `.scratch/stmdomains-ui-06/`: `gui_smoke.py`,
`gui-smoke.json`, demo oraz zrzuty dialogu i każdego wariantu; poza Git.
Szczyt RSS około **1462 MiB**, maksymalna przerwa timera **0,179 s**
w tej próbie. Dwie mapy TTMAPP to łącznie 512 KiB na analizowaną klatkę,
plus przypisania i model; przy maksymalnym obrazie 2048² dwie mapy to 32 MiB.

Więcej przypisań nie oznacza lepszej detekcji. Na 259 sama zmiana średnicy
0,50–0,60 nie usuwa odmów wcześniejszych etapów. Ręczne K i zakres dopasowania
pozostają następnym ticketem **07**, analiza serii — **08**, Auto — **12**.
Brak zapisu projektu; to nadal eksperymentalna metoda jednej klatki.

## Przegląd code-review

Przypięty zakres `8caa8a7...98ca8ff`, dwa niezależne przeglądy.
Poprawka sprawdzona dodatkowo w zakresie `98ca8ff...36aea1f`.

### Standards

**0 uwag.** Brak naruszeń udokumentowanych zasad i istotnych problemów
z bazowej listy zapachów kodu. Konfiguracja, przeliczanie i dialog mają
odrębne odpowiedzialności; obliczenia pozostają poza GUI. Dane pochodzenia
i niezmienne wyniki są zachowane. Niezależnie **23 testy PASS**;
12 plików kodu/testów, maksimum 424 linie.

### Spec

**1 uwaga P3, poprawiona w `36aea1f`; 0 otwartych uwag.** Ponowne
przeliczenie po przekroczeniu limitu zasobów niepoprawnie wymagało
fingerprintu nieistniejącego modelu i zgłaszało zmianę danych. Teraz
niekompletny wynik przechodzi ponownie analizę, po sprawdzeniu tożsamości
klatki, zachowując prawdziwy powód odmowy. Dwie nowe regresje obejmują
limit pikseli/oznaczeń oraz obcą serię. Recenzent potwierdził poprawkę.
Pozostałe kryteria spełnione, bez poszerzania zakresu; niezależnie
uruchomione przed poprawką **23 testy PASS**.

Standards: 0 uwag; Spec: 1 poprawiona, 0 otwartych.
