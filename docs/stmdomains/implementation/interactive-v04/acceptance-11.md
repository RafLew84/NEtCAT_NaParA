# SD-V4-11 — wspólne okno analizy

Data: **2026-11-03**. Gałąź `domains/interactive-v04-ui`, worktree
`/home/rlew/projekty/NEtCAT-domains`. Baza `c60e7fb`, implementacja `d18048b`.
[Ticket 11](11-unified-analysis-window.md).
**Odbiór ręczny użytkownika oczekuje.** Sprawdzenia agenta opisano poniżej.

## Uruchomienie i obsługa

W środowisku **netcat**, z katalogu tego worktree:

```bash
python -m stmdomains.main
```

Otwórz `data/TTMAPP/detection_full.moltrack.json`; powiązany obraz to
`data/TTMAPP/MOVIE_23raw_TTMAPP_I_AU111.MPP`. Nie trzeba wczytywać modelu.

Menu **Analiza → Analiza…** otwiera jedno niemodalne okno. Przycisk
**Analizuj klatkę…** przy obrazie otwiera to samo okno i wybiera bieżącą
klatkę jako cel. Obliczenia ruszają dopiero po **Analizuj** w tym oknie.

| Zakładka | Co wybierasz |
| --- | --- |
| Zakres | Klatki, które otrzymają domeny: bieżąca, zakres lub cała seria. |
| Klasy | Dopasuj nowe / użyj istniejących, K1–8, niezależny zakres odkrywania, margines i promień akceptacji. |
| Porządek | Kwantyl, minima wsparcia, promień i sigma w jednostkach odstępu d. |
| Domeny | Minimum molekuł, łączenie, geometria i zasięg obszaru domeny. |

Pola przewijają się wewnątrz zakładki, jeśli okno jest małe.
**Analizuj** stosuje wszystkie zakładki, także akceptację klas w serii.
Podsumowanie przed startem wskazuje zakres domen i źródło klas. Tabela
pokazuje stan każdej klatki bieżącego przebiegu; dwuklik przechodzi do obrazu.
**Anuluj obliczenia** zachowuje ukończone klatki i wcześniejsze wyniki.

**Szkic ustawień** pozostaje podczas przeglądania tej samej serii,
zamknięcia/otwarcia okna i porównania poprzedniego/nowego wyniku. W trybie
bieżącej klatki zmienia się cel, gdy przechodzisz do innego obrazu.
Start utrwala zakres i parametry; nawigacja w trakcie obliczeń ich nie zmienia.
Otwarcie nowej serii resetuje szkic i katalog. Wyniki i szkic są tylko w pamięci.

**Z wyświetlanego wyniku** jawnie kopiuje progi i wybiera jego katalog
w trybie „Użyj istniejących”; zakres analizy pozostaje wybrany przez użytkownika.
**Przywróć bazowe parametry** resetuje akceptację, porządek i domeny,
zachowując wybór klas i zakresów. Oba przyciski zmieniają szkic; nie przeliczają.
Do samego strojenia wybierz **Użyj istniejących klas**. „Dopasuj nowe”
wykonuje ponowne odkrywanie według ustawionego testu porządku.

Lokalny katalog można zastosować do niezmienionych danych jego klatki.
Do wielu klatek potrzebny jest wspólny katalog. Brak zgodności wyłącza
uruchomienie lub daje błąd z wyjaśnieniem; nie uruchamia ukrytego dopasowania.
Porównanie pokazuje wynik oglądanej klatki, bez podmiany katalogu w szkicu.
Pełne użyte parametry są pod **Dane…** obok legendy; dane molekuły nadal
rozdzielają akceptację klasy, porządek i końcową domenę.

## Test ręczny: jedna klatka i ten sam wynik w zakresie

1. Otwórz wskazany zapis TTMAPP, przejdź do **259**, kliknij
   **Analizuj klatkę…**. Wybierz **Klasy → Dopasuj nowe**, **K5**,
   **Inny wybrany zakres**, **259–268**. Zakres domen pozostaje bieżący.
2. W tej samej zakładce ustaw **margines 0,060**, **mnożnik promienia 0,80**.
   W **Porządek** wybierz **kwantyl 0,925**, pozostaw minimum **10 / 8**,
   promień **3** i bazową sigmę **1,333333** (wewnętrznie dokładne 4/3).
   W **Domeny** ustaw minimum **6**, odległość łączenia **1,80 × odstęp**.
   Pozostałe parametry pozostaw bazowe. Przełącz zakładki, zamknij i otwórz
   okno z menu: ustawienia powinny zostać, obraz jeszcze bez analizy.
3. Kliknij **Analizuj**. Oczekiwane na 259: **8 domen, 111/312** przypisanych,
   **219/312** zaakceptowanych klas, porządek **179/312**. Katalog zaczyna
   się od `cfc23500`. Tabela ma tylko klatkę 259.
4. W **Klasy** wybierz **Użyj istniejących klas** z tym katalogiem.
   W **Zakres** wybierz **Wybrany zakres 259–268**. Kliknij **Analizuj**.
   Przeglądaj suwakiem lub dwuklikiem tabeli: każda klatka ma wynik.
   Na 259 mają być identyczne przypisania i obszary jak w kroku 3;
   cały zakres używa marginesu 0,060 i mnożnika 0,80.

| Klatka | Przypisano do domen | Domeny |
| --- | ---: | ---: |
| 259 | 111 | 8 |
| 260 | 88 | 5 |
| 261 | 146 | 11 |
| 262 | 90 | 6 |
| 263 | 94 | 6 |
| 264 | 129 | 8 |
| 265 | 135 | 8 |
| 266 | 121 | 7 |
| 267 | 123 | 7 |
| 268 | 90 | 4 |

5. Wróć na 259, wybierz analizę bieżącej klatki i zachowaj istniejący
   katalog. Zmień promień/sigmę porządku na **2 / 1**, pozostaw kwantyl
   **0,925**. Po analizie oczekiwane **48/312, 3 domeny**, porządek **77/312**,
   akceptacja klasy nadal **219/312**. Kalibracja się zmienia, katalog nie.
6. Przełącz **Poprzedni wynik**: wraca obraz z kroku 4, ale szkic nadal
   zawiera promień 2 i sigmę 1. **Z wyświetlanego wyniku** dopiero jawnie
   kopiuje ustawienia. Samo oglądanie nie zmienia parametrów następnej próby.
7. Wybierz **Przywróć bazowe parametry**, pozostaw istniejący katalog
   i przelicz 259. Oczekiwane **101/312, 5 domen**, akceptacja **265/312**,
   porządek **159/312**. Katalog wciąż pochodzi z kroku 3; nie jest to
   nowy bazowy model dopasowany z kwantylem 0,950.
8. Wybierz całą serię z istniejącym katalogiem i uruchom. Przejdź do
   odległej klatki podczas pracy i anuluj po kilku ukończonych. Tabela
   rozróżnia gotowe i **Niewykonana**; wcześniejszy obraz jest opisany jako
   wynik spoza bieżącego przebiegu. Sprawdź też wyjście podczas obliczeń.
9. Sprawdź nawigację, raw/wyrównany, gammę, warstwy domen i okno główne
   około **900×650**. Otwórz inną serię: K5 i progi bazowe, brak starego
   katalogu/tabeli, jawny komunikat o nowej serii.

## Gotowe kontrole i brak danych

Pliki przygotowane lokalnie:

- `.scratch/stmdomains-ui-11/demo/order-controls.moltrack.json` wraz z MPP:
  układ regularny, losowy, rzędy i cztery centra.
- `.scratch/stmdomains-ui-11/class-demo/pair_b.moltrack.json` wraz z MPP:
  trzy klatki, ostatnia bez oznaczeń.

Można je odtworzyć generatorami aplikacji:

```bash
python -m stmdomains.tools.order_demo --output .scratch/stmdomains-ui-11/demo
python -m stmdomains.tools.class_discovery_demo --output .scratch/stmdomains-ui-11/class-demo
```

Na kontroli porządku wybierz analizę całej serii, nowe **K1** z jawnego
zakresu odkrywania **1–1**, wszystkie pozostałe parametry bazowe.
K1 wyłącza pole marginesu. Oczekiwane:

| Klatka | Aktywne centra | Porządek | Przypisano | Domeny |
| --- | ---: | ---: | ---: | ---: |
| Regularna | 121 | 117 | 117 | 1 |
| Losowa | 98 | 12 | 0 | 0 |
| Rzędy | 94 | 30 | 0 | 0 |
| Cztery centra | 4 | 0 | 0 | 0 |

W `pair_b` przejdź do klatki 3 i analizuj bieżącą klatkę: oczekiwane
**Brak oznaczeń**, bez wymyślonego katalogu ani liczby wykrytych domen.
Na pierwszej klatce można obliczyć K1, następnie anulować nowe dopasowanie:
wcześniejszy katalog i wynik pozostają. Wybór lokalnego katalogu na innej
klatce blokuje analizę i wyjaśnia powód. Nieudana kalibracja również
zachowuje wcześniejszy wynik, z błędem w tabeli i szczegółami w podpowiedzi.

## Wykonane sprawdzenia agenta

Interpreter: `/home/rlew/projekty/conda-migration-ubuntu-20261008/envs/netcat/bin/python`.
Nie instalowano zależności ani nie zmieniano wspólnych modułów.

- TDD na publicznych obliczeniach i kontrolkach: najpierw brak przekazania
  akceptacji do serii, brak lokalnego trybu wspólnego przebiegu, nieprawidłowe
  parametry wyniku bez danych, brak wspólnego okna, niezgodne K wybranego
  katalogu; następnie implementacje i przejścia testów.
- Testy celowane: **15 regresji UI PASS**, **21 obliczeń/sesji/wyjścia PASS**;
  po dodatkowym teście niezmiennego celu podczas nawigacji **3 testy wspólnego
  dialogu PASS**. Przypadki częściowo pokrywają się; nie sumujemy tych liczb.
- **Mypy 67 modułów PASS**, 22 nowe/zmienione pliki kodu i testów,
  największy **575 linii**. Usunięto pięć zastąpionych formularzy.
- **GUI X11 PASS** na TTMAPP i kontrolach: równość klatka/seria także
  maska piksel w piksel, brak ponownego
  fitu przy istniejącym katalogu (blokada PCA/KMeans), nawigacja, porównanie,
  bazowe ustawienia, raw/wyrównany, gamma, częściowe anulowanie, brak danych
  i wyjście podczas pracy. Osobno sprawdzono końcowy układ formularzy oraz
  dostęp do akceptacji przez przewijanie. Obejrzano zrzuty.
- Jawne kopiowanie ustawień z wyświetlanego wyniku potwierdzają testy
  kontrolek Qt offscreen; nie było osobnej próby tej operacji w X11.
- Okno główne **900×650** i **1250×850**; końcowe okno analizy **660×650**
  oraz minimum wyznaczone przez Qt **620×574**. Próba zmniejszenia do
  620×560 zachowała dostępność kontrolek przy tym minimum.
- TTMAPP: dopasowanie + klatka 259 około **7,06 s**, zastosowanie katalogu
  do 10 klatek około **6,80 s**. RSS około **698 MiB**, największa przerwa
  timera GUI **0,231 s**. Anulowana próba: 3 klatki gotowe, 265 niewykonanych.
  Po zamknięciu wszystkie trzy pule mają 0 aktywnych zadań.
- **0 odczytów historycznych zasobów v0.4**. SHA-256 MPP/JSON przed i po
  próbie bez zmian; wartości w `gui-smoke.json`.
- Pierwsza próba X11 w piaskownicy nie połączyła się z ekranem i zakończyła
  start Qt kodem 134. Powtórzenie z dostępem do lokalnego ekranu PASS;
  nie wymagało instalacji pakietów.

**Pełny zestaw po poprawce testu: 456 passed, bez pominięć, 153,60 s.**
Log: `pytest-full.log`.
Pierwszy przebieg: **455 PASS, 1 błąd nieaktualnego testu warstw domen**
(152,08 s). Test nadal oczekiwał obliczeń po przycisku przy obrazie;
dodano otwarcie wspólnego okna i jego przycisk Analizuj. Celowany test
po poprawce PASS (1,37 s); log pierwszej próby zachowano jako
`pytest-full-before-test-update.log`. Kod aplikacji nie wymagał zmiany.

Walidacja dokumentacji: **393 lokalne odnośniki z kotwicami w 8 dokumentach
PASS**; 25 unikalnych ticketów, zgodność zależności z indeksem i brak cykli.
`git diff --check` PASS.

Polecenia w aktywnym netcat:

```bash
python -m mypy --follow-imports=silent --ignore-missing-imports stmdomains/analysis stmdomains/core stmdomains/io stmdomains/ui stmdomains/tools
python -m stmdomains.tools.check_code_size --base c60e7fb
QT_QPA_PLATFORM=offscreen OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 python -m pytest -q tests/stmdomains
```

Artefakty poza Git: `.scratch/stmdomains-ui-11/`, w tym `gui_smoke.py`,
`gui-smoke.json`, `gui-smoke.log`, `layout_smoke.py`, `layout-smoke.log`,
PNG, przykłady i logi testów.

## Przegląd kodu

Skill `code-review`, `git diff c60e7fb...d18048b`; dwie niezależne osie.

### Standards

**0 uwag.** Zmiany pozostają w katalogach aplikacji i jej testów.
Wspólne okno składa się z osobnych modułów formularzy, prezentacji stanów
oraz obliczeń. Konfiguracja przebiegu jest niemutowalna, a testy sprawdzają
publiczne obliczenia i kontrolki UI. Zachowano rozróżnienie braku danych,
odmowy i obliczonego wyniku.

### Spec

**0 uwag funkcjonalnych.** Sprawdzono kompletne przekazanie parametrów,
rozdzielenie zakresów, lokalny/wspólny katalog, niezmienność przebiegu,
niezależność szkicu od porównania i zachowanie wcześniejszych wyników.
Recenzent wykonał 7 celowanych testów (10,12 s), bez pełnego zestawu.
Dodatkowo sprawdził poprawkę testu warstw domen i raport; skorygowano liczbę
zmienionych plików oraz rozdzielono próbę kopiowania offscreen od X11.
Brak otwartych uwag: **Standards 0 / Spec 0**.

## Ograniczenia

To ujednolicenie obsługi i konfiguracji, bez nowej metody detekcji.
Podane liczniki są kontrolą działania programu, nie oceną trafności.
Rzędy mogą przechodzić test periodyczności bez potwierdzenia sieci 2D;
zerowe domeny na kontrolach obejmują też odmowę klasy.
**12 — Auto pozostaje niewykonany** i będzie rozszerzał zakładkę Klasy.
Zapis pracy na dysku, eksport i ręczna edycja są kolejnymi ticketami.
