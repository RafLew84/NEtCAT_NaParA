# SD-V4-08 — analiza zakresu lub całej serii

Data ukończenia **2026-11-03**. Baza **`e51b612`**, implementacja **`1c39ae2`**, poprawka **`46c274f`**,
gałąź `domains/interactive-v04-ui`. **Odbiór ręczny użytkownika oczekuje.**
Wykonane sprawdzenia agenta opisano oddzielnie poniżej.

## Uruchomienie i test ręczny

W `/home/rlew/projekty/NEtCAT-domains`:

```bash
conda activate netcat
python -m stmdomains.main
```

1. Otwórz `data/TTMAPP/detection_full.moltrack.json` i menu
   **Analiza → Analiza serii…**. Okno jest niemodalne; można je przesunąć
   obok obrazu. Ma zakładki **Zakres i klasy** oraz **Tworzenie domen**.
2. Wybierz klatki **259–268**, **Ten sam zakres co analiza**, **K5**.
   W zakładce domen wybierz **Przywróć bazowe**. Kliknij **Analizuj wybrane
   klatki**: przycisk stosuje ustawienia z obu zakładek. Sama edycja pól
   nie zmienia obliczonego wyniku. Najpierw powstaje wspólny katalog,
   potem domeny kolejnych klatek.
3. Po zakończeniu tabela pokazuje **10/10 klatek**, a suwak/miniatury
   pozwalają obejrzeć oznaczenia na każdej z nich. Oczekiwane wyniki:
   **259: 105/312 i 5 domen; 268: 119/308 i 4 domeny**. Dwuklik w wiersz
   tabeli przechodzi do jego klatki. W trybie **Klasy** ten sam numer/kolor
   odnosi się do tego samego katalogu. Numery **Domen** są lokalne;
   nie oznaczają śledzenia tej samej domeny w czasie.
4. Na 259 kliknij górne **Analizuj klatkę · K5**. Przy tych samych
   ustawieniach i katalogu wynik jest identyczny z wynikiem serii.
   To osobne przeliczenie; stopka odróżnia je od wyniku przebiegu.
   Poprzedni wynik jest nadal dostępny przez okno klas/tworzenia domen.
5. W oknie serii ustaw **250–268, K8, Ten sam zakres co analiza**,
   a w zakładce domen minimum **6** i łączenie **1,80**. Jedno uruchomienie
   stosuje oba zestawy ustawień do wszystkich 19 klatek. Oczekiwane:
   **250: 68/301, 6 domen; 259: 108/312, 7; 268: 131/308, 6**.
6. Aby wykorzystać istniejące klasy, wybierz **Użyj wybranego wspólnego
   katalogu**. K i zakres dopasowania są pokazane zgodnie z katalogiem,
   bez ponownego dopasowania. Katalog lokalny jednej klatki nie wystarcza.
   Można też wybrać **Inny wybrany zakres**: np. analizować 250–251,
   dopasowując klasy z 259–268. Opcja **Cała seria** w danych do odkrywania
   klas odnosi się do dopasowania, a osobna opcja przy **Klatki do analizy**
   określa obrazy, na których mają powstać domeny.
7. Uruchom większy zakres, przejdź do innej klatki podczas obliczeń,
   potem kliknij **Anuluj analizę serii**. Ukończone wyniki pozostają
   dostępne. Pozostałe wiersze mają stan **Niewykonana**. Jeżeli istniał
   wcześniejszy wynik takiej klatki, pozostaje widoczny z informacją,
   że pochodzi spoza tego przebiegu; nie jest uznawany za nowy wynik.
   Anulowanie podczas dopasowania zachowuje poprzedni katalog.
8. Sprawdź niepoprawny zakres oraz relację progów geometrii. Komunikat
   blokuje uruchomienie. Brak oznaczeń i błąd klatki mają osobne stany,
   nie są przedstawiane jako poprawnie obliczone zero domen.
9. Po zakończeniu serii otwórz **Tworzenie domen…** i dostrój tylko jedną
   klatkę. Tabela serii zachowuje liczniki pierwotnego przebiegu, a stopka
   oznacza nowy indywidualny wynik jako spoza niego. Przywrócenie poprzedniej
   wersji przywraca również jej powiązanie z przebiegiem.
10. Zamknięcie okna ustawień pozostawia obliczenia w tle. Ponowne otwarcie
    pokazuje postęp/wyniki. Zamknięcie aplikacji podczas pracy powinno
    zakończyć proces bez traceback. Otwarcie innej serii anuluje pracę;
    zaakceptowany import usuwa poprzednie wyniki i tabelę.

**Parametry serii są szkicem w jej własnej zakładce „Tworzenie domen”.**
Przycisk **Z wyświetlanego wyniku** kopiuje zastosowane wartości bieżącej
klatki; **Przywróć bazowe** wpisuje bazowe. Niezastosowane pola w osobnym
oknie strojenia 06 nie są automatycznie przejmowane. Podczas przebiegu
parametry pozostają stałe, a nawigacja nie zmienia zakresu obliczeń.

### Kontrole bez danych TTMAPP

Lokalne wejścia można odtworzyć w `netcat`:

```bash
python -m stmdomains.tools.class_discovery_demo --output .scratch/stmdomains-ui-08/demo
```

- Otwórz `pair_b.moltrack.json`, wybierz **Cała seria / Ten sam zakres /
  K5**, bazowe domeny. Pierwsza klatka: **357/405, 17 domen**; trzecia:
  **Brak oznaczeń**. Przejdź między nimi: brak nakładki na trzeciej nie
  jest wynikiem zerowej liczby domen. Na pierwszej indywidualne minimum
  **30** daje **231 przypisań**, a tabela wcześniejszego przebiegu nadal 357.
- `single.moltrack.json`: **K1**, jedna klatka — **12/16, 1 domena**.
  Następnie spróbuj K8: jawna odmowa dopasowania, wcześniejszy wynik
  i katalog pozostają dostępne.
- `empty.moltrack.json`: brak danych do dopasowania; zrozumiały komunikat.

Generator tworzy tylko obrazy MPP i oznaczenia. Kontrole nie wymagają
modelu ani gotowych wyników i sprawdzają program, nie trafność fizyczną domen.

## Realizacja i ograniczenia

`SeriesAnalysisPlan` zamraża zakres analizy, źródło klas, K i `DomainSettings`.
`analyze_series` zwraca wspólny katalog, następnie kolejne wyniki lub błędy.
Wydzielone `fit_shared_catalogue` korzysta z tego samego dopasowania co 07,
bez niepotrzebnego obliczania domen podczas etapu odkrywania klas.
Ponowne użycie katalogu sprawdza serię, wspólny zakres, K i parametry metody.

`SeriesRunner` przesuwa obliczenia o jeden wynik po jego odebraniu przez
wątek GUI. Kolejka nie gromadzi wyników wszystkich klatek. Identyfikatory
zadań i przebiegów odrzucają spóźnione zdarzenia; osobne żądania podglądu
nie anulują serii. Wyświetlany obraz dostaje wyłącznie wynik swojej klatki.
Błąd dopasowania zatrzymuje przebieg; błąd pojedynczej analizy jest zapisany
w tabeli i nie blokuje następnych klatek. Postęp i przyczyna błędu są jawne.

Wynik zawiera parametry, katalog oraz `series_analysis` z identyfikatorem
przebiegu, zakresem analizy i sposobem pozyskania klas. Indywidualne strojenie
usuwa znacznik przynależności do przebiegu z nowego wyniku; poprzednia wersja
zachowuje go. Współdzielone kontrolki `DomainSettingsFields` zapewniają
te same zakresy i jednostki w oknie pojedynczej klatki oraz serii.

Pozostają **dwie wersje na klatkę** i tabela ostatniego przebiegu. Ponowne
przejścia nie dopisują wyników ani nie powielają cache obrazów. Katalog
i jego niemodyfikowalne metadane są współdzielone między klatkami.
Zewnętrzny modyfikowalny słownik, również opakowany w `MappingProxyType`,
nadal jest kopiowany do własnej migawki. Pamięć wyników rośnie z liczbą
analizowanych klatek, a nie liczbą przejść po tej samej serii.

Ograniczenia metody i dopasowania z 07 pozostają: najwyżej 6000 próbek
wspólnego fitu, deterministyczny limit na klatkę, jawna skala deskryptora,
K1–8, kontrola porządku i barier. Klas nie należy utożsamiać z fazami
fizycznymi ani domen ze śledzonymi obiektami. Wyniki są w pamięci:
trwały zapis projektu będzie w 13, eksport w 14. **Auto pozostaje w 12**.

## Wykonane sprawdzenia

Interpreter zweryfikowany przed próbami:
`/home/rlew/projekty/conda-migration-ubuntu-20261008/envs/netcat/bin/python`.
Wszystkie testy i uruchomienia w **netcat**, bez instalacji pakietów.

- **13 nowych przypadków testowych**: oddzielne zakresy i identyczność
  batch/pojedyncza klatka, współdzielenie niezmiennych metadanych, użycie
  istniejącego modelu bez dopasowania, puste dane i błąd jednej klatki,
  anulowanie fitu/analizy, walidacja zakresu/katalogu, publikacja na właściwej
  klatce, anulowanie/otwarcie/zamknięcie, odzyskanie po odmowie, dwie wersje,
  cache obrazów, rzeczywiste kontrolki obu zakładek i późniejsze strojenie.
- Celowane regresje 06/07, prezentacji, układu i zamykania PASS.
- Mypy **59 modułów PASS**:

  ```bash
  python -m mypy --follow-imports=silent --ignore-missing-imports stmdomains/analysis stmdomains/core stmdomains/io stmdomains/ui stmdomains/tools
  ```

- Kod/testy: **14 plików, maksimum 527 linii**:
  `python -m stmdomains.tools.check_code_size --base e51b612`.
- `git diff --check` PASS; **341 lokalnych ścieżek odnośników w 7 dokumentach PASS**.
- Pełny zestaw uruchomiony raz po przeglądzie i poprawce:
  **409 passed, bez pominięć, 95,15 s**:

  ```bash
  QT_QPA_PLATFORM=offscreen OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 python -m pytest -q tests/stmdomains
  ```

### Dane TTMAPP i rzeczywiste GUI

Główna próba **X11/xcb sterowana Qt PASS**: obie zakładki, jawne uruchomienie,
wyniki każdej klatki 259–268 i 250–268, zastosowanie tych samych klas do
pojedynczej klatki, niezależny zakres fitu, ponowne użycie katalogu, cała
seria, nawigacja podczas pracy, częściowe anulowanie i ponowne otwarcie.
Sprawdzono raw/aligned, gamma i stabilny układ **900×650**. Obejrzano zrzuty.

Główna próba odpowiada implementacji `1c39ae2` poza później poprawionym
wyświetlaniem nieaktywnych końców zakresu dopasowania. Końcowa krótka
próba na `46c274f` potwierdziła te pola, dwuklik w tabeli, strojenie
357 → 231 przypisań i przywrócenie wcześniejszego wyniku z poprawną
informacją w stopce. Pierwsza wersja skryptu tej krótkiej próby wysyłała
sam sygnał zdarzenia dwukliku, bez poprzedzającego kliknięcia w tabeli;
po odtworzeniu pełnej sekwencji myszy próba PASS. Nie wymagało to zmiany kodu.

| Zakres analizy | Dopasowanie | Domeny | Czas |
| --- | --- | --- | ---: |
| 259–268 | K5 z 259–268 | bazowe parametry | 13,00 s |
| 250–268 | K8 z 250–268 | minimum 6, łączenie 1,80 | 24,73 s |
| 250–251 | K8 z 259–268 | minimum 6, łączenie 1,80 | 7,77 s |
| Wszystkie 268 | ten sam K8 z 259–268, bez fitu | minimum 6, łączenie 1,80 | 167,67 s |

Cała seria zakończyła się **268/268, bez błędów**. Przykłady ostatniego
przebiegu: klatka 1 **23/288, 2 domeny**, 120 **38/248, 2**, 259
**107/312, 6**, 268 **138/308, 6**. Wcześniejsze liczniki z instrukcji
dotyczą innych katalogów/ustawień. Na 259 i 250 ponowna pojedyncza analiza
z tym samym modelem i ustawieniami odtworzyła przypisania; na 259 także
identyczną mapę pikseli. Więcej przypisań nie jest dowodem poprawy trafności.

Anulowanie pozostawiło **2 ukończone klatki**; niewykonane miały jawny stan.
Demo z brakiem oznaczeń zakończyło się poprawnie. Zamknięcie podczas
dopasowania: **kod 0**, wszystkie **trzy pule** zakończone. Źródłowe JSON/MPP
miały identyczne SHA-256 przed i po próbie:

- JSON `d0c4cb999bede28edb5dfd18ddbe146054711382f1c78363055be2330b3cdd2e`.
- MPP `8fbbfa5d515a90552c13cee2dbd289ff5cc16f000315547185c2a57bfe9f7c66`.

Zablokowano dostęp do paczek i historycznych modeli/wyników: **0 odczytów**.
W tej próbie maksymalny RSS **866 MiB**, przerwa testowego timera **0,237 s**,
cache obrazów podczas ponownych przejść najwyżej **2350080 B** (limit 32 MiB).
Wyniki nie są przenoszone między worktree. Bez zmian modułów wspólnych;
zależności zgłoszone integratorowi w 05 pozostają aktualne.

Artefakty lokalne poza Git: `.scratch/stmdomains-ui-08/`, w tym `gui-smoke.json`,
`gui-final.json`, `pytest-full.log`, małe demo i zrzuty. Sprawdzenie agenta
nie zastępuje oczekującego odbioru ręcznego użytkownika ani walidacji detektora.

## Przegląd code-review

Dwie niezależne osie dla **`e51b612...1c39ae2`**; poprawka **`46c274f`**
sprawdzona dodatkowo przez recenzenta Standards.

### Standards

**1 uwaga P2, poprawiona; 0 otwartych.** Indywidualne strojenie zachowywało
znacznik przebiegu serii mimo innych parametrów. Teraz nowy wynik jest
oznaczony jako spoza przebiegu; tabela i poprzedni wynik zachowują swoje
pochodzenie. Regresja Qt przeszła RED→GREEN, recenzent niezależnie potwierdził
**1 test PASS**. Brak dodatkowych uwag z bazowej listy zapachów kodu.

### Spec

**0 uwag.** Potwierdzono zakresy, wspólny model i ustawienia, ponowne
użycie katalogu, częściowe wyniki, puste dane, błędy, nawigację i odrzucanie
spóźnionych zdarzeń. Bez rozszerzenia zakresu. Obie osie niezależnie
uruchomiły po **12 testów celowanych PASS** przed poprawką.

Standards: 1 poprawiona, 0 otwartych; Spec: 0 uwag.

Następny rekomendowany ticket **12 — automatyczny wybór liczby klas**.
