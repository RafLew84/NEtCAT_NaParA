# SD-V4-07 — liczba klas i zakres dopasowania

Data **2026-11-02**. Baza `eebbfbd`, implementacja **`dedd8b8`**, poprawki
**`65e9d2a`**, gałąź `domains/interactive-v04-ui`. Status `done`.
**Ręczny odbiór użytkownika potwierdzony 2026-11-02 dla wersji `7f79362`**
słowami „testy manualne ok”. Poniżej oddzielnie opisano wykonane sprawdzenia
agenta i instrukcję użytkownika.

Zapis potwierdzenia zmienia wyłącznie dokumentację. `git diff --check` PASS;
testów kodu nie ponawiano. Następny ticket: **08 — analiza zakresu/serii**.

## Uruchomienie i test ręczny

W `/home/rlew/projekty/NEtCAT-domains`:

```bash
conda activate netcat
python -m stmdomains.main
```

1. Otwórz `data/TTMAPP/detection_full.moltrack.json`, wybierz **259**.
   Otwórz **Analiza → Klasy i zakres…**. Małe okno jest niemodalne,
   można ustawić je obok obrazu. Wybierz **K5 / Bieżąca klatka**, kliknij
   **Dopasuj klasy i analizuj klatkę**. Przy bazowych parametrach domen:
   **120/312 molekuł, 6 domen**, lokalny katalog klatki 259.
2. Zmień K na **4**. Sama zmiana pola pozostawia wcześniejszy obraz.
   Kliknij dopasowanie: **132/312, 6 domen**, nowy lokalny katalog.
   W trybie **Klasy** legenda pokazuje cztery klasy. W trybie **Domeny**
   nadal jest sześć domen: liczba klas nie jest liczbą domen.
3. Ustaw **K5 / Wybrany zakres / 259–268**, uruchom dopasowanie:
   **105/312, 5 domen** na bieżącej 259. Dialog pokazuje wspólny katalog,
   **1715 otoczeń i 10/10 klatek z próbkami**. Tylko bieżąca klatka
   otrzymuje nowy wynik domen; zakres wskazuje dane do odkrywania klas.
4. Przełącz **Pokaż wynik i wybierz jego katalog → Poprzedni wynik**:
   wracają lokalny K4, jego kolory, przypisania i katalog. **Nowy wynik**
   przywraca wspólny K5. Zoom i przesunięcie obrazu pozostają zachowane.
   Etykieta „klasa 1” w dwóch katalogach nie musi oznaczać tej samej struktury.
5. Przy wybranym wspólnym K5 przejdź do **268**. Samo przejście nie
   uruchamia obliczeń: klatka jest nieprzeliczona albo ma jawnie wcześniejszy
   katalog, jeżeli wcześniej ją analizowano. Górne **Analizuj klatkę · K5**
   stosuje wybrany wspólny katalog bez dopasowania: **119/308, 4 domeny**.
   Wersja katalogu jest taka sama jak na 259. **Dane…** pokazuje pochodzenie
   modelu, zakres i próbki. Powrót do 259 przywraca jej własny wynik.
6. Opcjonalnie na 259 wybierz **Cała seria / K5**. Po dopasowaniu wszystkich
   268 klatek oczekiwane **111/312, 4 domeny** na 259. Lokalna próba trwała
   około **159 s**. Działa postęp i anulowanie; pozostałe domeny serii
   nie są jeszcze przeliczane automatycznie (to ticket 08).
7. Sprawdź zakres od większego numeru do mniejszego: komunikat i nieaktywny
   przycisk. Przełączenie na bieżącą klatkę lub całą serię ignoruje
   nieaktywne końce zakresu. Anulowanie lub odmowa dopasowania zachowuje
   wcześniejsze poprawne wyniki i katalog. Nawigacja do innej klatki
   anuluje trwające dopasowanie; gamma i raw/aligned zachowują jego kontekst.
8. **Analiza → Tworzenie domen…** nadal stroi domeny wyświetlanego wyniku,
   zachowując jego K i katalog. Sprawdź również po wyborze poprzedniego
   wyniku. Ponowne otwarcie serii usuwa wyniki i aktywny katalog z pamięci.
   Zamknięcie podczas dopasowania powinno wrócić do terminala bez traceback.

Górny przycisk analizy używa aktywnego katalogu wspólnego. Przy katalogu
lokalnym wykonuje nowe lokalne dopasowanie z jego K; nie przenosi modelu
innej klatki. Przycisk w **Klasy i zakres…** zawsze dopasowuje z wybranych
danych. Edycja pól w obu oknach pozostaje szkicem do jawnego uruchomienia.

### Małe kontrole do otwarcia w tym samym UI

Pliki zostały wygenerowane lokalnie. Można je odtworzyć w `netcat`:

```bash
python -m stmdomains.tools.class_discovery_demo
```

Otwieraj zapisy z `.scratch/stmdomains-ui-07/demo/`:

- `single.moltrack.json`: jedna klatka 128×128 px, 16 centrów na siatce
  obróconej o 45°. Lokalne **K1 daje 12/16 i jedną domenę**. **K8**
  odmawia dopasowania z powodu za małej liczby różnych użytecznych otoczeń;
  wcześniejszy K1 pozostaje. Wyłącz ramki, pozostaw centra i obszary.
- `pair_a.moltrack.json` i `pair_b.moltrack.json`: pierwsza klatka jest
  identyczna, kolejne się różnią. Lokalne **K5 na pierwszej klatce** daje
  w obu **357/405 i 17 domen**, identyczne przypisania i katalog `13040c17…`.
  Wynik lokalny nie korzysta z pozostałych obrazów.
- `empty.moltrack.json`: brak oznaczeń; dopasowanie wyjaśnia brak danych.

Generator zapisuje tylko MPP i oznaczenia MolTrack, bez modelu lub etykiet
wynikowych. Kontrole służą sprawdzeniu programu, nie ocenie trafności
detekcji domen na rzeczywistych danych.

## Obliczenia, wersje i ograniczenia

`ClassFitSettings` waliduje K1–8 i zakres. `discover_classes` oddziela
dane dopasowania od analizowanej klatki. Przy wspólnym zakresie odwiedza
wszystkie wybrane klatki; klasy powstają z użytecznych deskryptorów
po dotychczasowej kontroli otoczenia i porządku. Dopasowanie ma limit
**6000 próbek**, z limitem na klatkę `floor(6000 / liczba wybranych klatek)`.
Nadmiar wybierany jest deterministycznie w równych odstępach stabilnej
kolejności oznaczeń. Niewykorzystane limity pustych klatek nie są
przenoszone na inne. Zakres ponad 6000 klatek otrzymuje komunikat odmowy.
Lokalne dopasowanie korzysta ze wszystkich użytecznych próbek klatki.

TTMAPP 259–268 mieści wszystkie 1715 próbek. Dla 268 klatek rozpatrzono
20071 użytecznych otoczeń i dopasowano **4497** (limit **22/klatkę**).
Nie ma zależności od pierwszych dziesięciu klatek. Metadane zawierają
zakres roboczy i źródłowy, SHA-256 wejścia, odstęp molekuł, identyfikatory
wybranych oznaczeń, liczby użytecznych/użytych próbek i powody braków.
Deskryptor jest normalizowany medianą odległości do najbliższego sąsiada
na danej klatce po usunięciu duplikatów. Nadal zależy od orientacji;
klasa robocza nie jest potwierdzonym typem struktury niezależnym od obrotu.

PCA używa najwyżej 24 składowych, liczby próbek minus jeden i wymiaru
deskryptora. Dla jednej próbki lub stałego zbioru K1 pozostaje oryginalna
przestrzeń deskryptora, aby odmienne otoczenia nadal mogły zostać odrzucone.
K1 pomija margines względem nieistniejącego drugiego centroidu, zachowując
kontrolę promienia klasy. KMeans używa ziarna 24 i 20 inicjalizacji.
Za mało użytecznych/różnych otoczeń oznacza odmowę zamiast sztucznego
utworzenia pustych klas. Nadal obowiązują ograniczenia pojedynczej klatki:
3000 oznaczeń i 2048² pikseli.

Niemodyfikowalny `ClassCatalogue` przechowuje projekcję, centroidy, promienie
i pochodzenie. Wersja jest skrótem treści: ponowne identyczne dopasowanie
daje ten sam identyfikator. Losowy identyfikator otwartej sesji osobno
chroni przed użyciem modelu obcej serii. Model lokalny przy zastosowaniu
wymaga tej samej klatki i SHA-256; wspólny można jawnie stosować do innych
klatek tej otwartej serii, również spoza zakresu dopasowania.

W pamięci pozostają dwie ukończone wersje wyniku na klatkę; trzecia
zastępuje najstarszą. Wybranie poprzedniej przywraca również jej katalog.
Stare wyniki nie są przemalowywane według nowego modelu. Nieudana próba,
również górnym przyciskiem po nawigacji z innym K, zachowuje obie wersje
i pokazuje powód odmowy. Brak trwałego zapisu projektu (13), automatycznej
analizy domen serii (08) i wyboru Auto (12).

## Wykonane sprawdzenia

Wszystkie uruchomienia w zweryfikowanym środowisku **netcat**:
`/home/rlew/projekty/conda-migration-ubuntu-20261008/envs/netcat/bin/python`.
Bez instalacji pakietów i zmian modułów wspólnych.

- **23 nowe przypadki testowe**: K1/4/8, małe/stałe dane, promień K1,
  użycie katalogu bez dopasowania PCA/KMeans, dokładny zakres i oddzielna
  klatka wyniku, niezależność lokalna, powtarzalność i niezmienność,
  puste klatki, błędne K/zakres, anulowanie, wersje i aktywny katalog,
  nawigacja/ponowne otwarcie/gamma, menu i kontrolki Qt, widoczność demo
  oraz zachowanie poprawnych wyników po odmowie górnego przycisku.
- Celowane regresje wcześniejszych obliczeń, prezentacji i sesji PASS.
- Mypy **54 moduły PASS**:

  ```bash
  python -m mypy --follow-imports=silent --ignore-missing-imports stmdomains/analysis stmdomains/core stmdomains/io stmdomains/ui stmdomains/tools
  ```

- Kod/testy: **23 pliki, maksimum 469 linii**:
  `python -m stmdomains.tools.check_code_size --base eebbfbd`.
- `git diff --check` PASS; **333 lokalne ścieżki odnośników w 7 dokumentach PASS**.
- Pełny zestaw uruchomiono raz po przeglądzie i poprawce:
  **396 passed, bez pominięć, 65,41 s**:

  ```bash
  QT_QPA_PLATFORM=offscreen OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 python -m pytest -q tests/stmdomains
  ```

### Rzeczywiste dane i GUI

Wykonano **X11/xcb sterowane Qt**: menu, lokalne K5/K4, zakres 259–268,
cała seria, poprzedni/nowy katalog, jawne wcześniejsze wyniki, zastosowanie
wspólnego modelu na 268, walidacja zakresu, anulowanie, nawigacja,
ponowne otwarcie, gamma/raw/aligned oraz stabilny układ **900×650**.
Obejrzano zrzuty dialogu i wyniku. Zamknięcie podczas dopasowania:
kod procesu **0**, obie pule workerów zakończone. To sprawdzenie agenta,
odrębne od potwierdzonego powyżej ręcznego odbioru użytkownika.

| Wynik / zakres dopasowania | Przypisane / aktywne | Domeny | Czas dopasowania z wynikiem |
| --- | ---: | ---: | ---: |
| 259, lokalne K5 | 120 / 312 | 6 | 0,73 s |
| 259, lokalne K4 | 132 / 312 | 6 | 0,73 s |
| 259, K5 z 259–268 | 105 / 312 | 5 | 6,44 s |
| 268, zastosowanie tego samego wspólnego K5 | 119 / 308 | 4 | nie mierzono |
| 259, K5 z całej serii 268 klatek | 111 / 312 | 4 | 159,13 s |

To liczniki działania przy bazowych parametrach domen, bez oceny accuracy.
Lokalne K5 zachowuje wynik wcześniejszej aplikacji. Więcej przypisań K4
nie dowodzi poprawy jakości. Wynik wspólny również nie stanowi przyjęcia
detektora ani nowej walidacji fizycznych granic.

Główna próba GUI odpowiada `dedd8b8` poza później dodanym tekstem liczby
próbek w dialogu. Krótka próba końcowa potwierdziła ten tekst, zachowanie
wspólnego katalogu przy minimum domeny 6 oraz czytelność poprawionej
kontroli K1 128×128. Początkowa kontrola zajmowała za małą część obrazu
512×512 i przy domyślnym kontraście wyglądała płasko; poprawiono generator
oraz dodano regresję widoczności. Poprawkę odmowy z `65e9d2a` sprawdzono
testem kontrolera Qt offscreen i niezależnym przeglądem.

Wejścia TTMAPP identyczne przed i po głównej próbie (SHA-256):

- JSON `d0c4cb999bede28edb5dfd18ddbe146054711382f1c78363055be2330b3cdd2e`.
- MPP `8fbbfa5d515a90552c13cee2dbd289ff5cc16f000315547185c2a57bfe9f7c66`.

Blokowano odczyty paczek i dawnych modeli/wyników: **0 odczytów**.
Maksymalny RSS **666 MiB**, maksymalna przerwa testowego timera **0,232 s**
w tej próbie. Artefakty poza Git: `.scratch/stmdomains-ui-07/`, w tym
`gui-smoke.json`, `gui-controls-final.json`, `pytest-full.log`, demo
i zrzuty okien. Nie są plikami wymaganymi przez aplikację.

## Przegląd code-review

Przypięty zakres **`eebbfbd...dedd8b8`**, dwie niezależne osie;
poprawka **`65e9d2a`** sprawdzona dodatkowo przez recenzenta Standards.

### Standards

**1 uwaga P2, poprawiona; 0 otwartych.** Górne „Analizuj klatkę” po
przejściu z lokalnego K8 do małej klatki z poprawnym K1 mogło zastąpić
wynik odmową i usunąć historię. Teraz odmowa zachowuje obie wersje
i aktywny katalog, pokazując przyczynę. Regresja przeszła RED→GREEN;
recenzent potwierdził poprawkę i niezależnie uruchomił test **PASS**.
Brak dodatkowych uwag z listy zapachów kodu.

### Spec

**0 uwag.** Potwierdzono rozdzielenie zakresu dopasowania i klatki wyniku,
lokalność, ponowne użycie katalogu, K1, wersje, anulowanie i pochodzenie.
Bez rozszerzenia zakresu. Niezależnie **20 testów celowanych PASS**.

Standards: 1 poprawiona, 0 otwartych; Spec: 0 uwag.

Następny ticket **08 — analiza zakresu/serii**, potem **12 — Auto**.
