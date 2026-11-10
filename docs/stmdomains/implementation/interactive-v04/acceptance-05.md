# SD-V4-05 — klasy i domeny obliczane z bieżącej klatki

Data: **2026-11-02**. Baza `2d01c5e`, implementacja **`fb37431`**,
gałąź `domains/interactive-v04-ui`. Ręczny odbiór użytkownika pozostaje
do wykonania. To implementacja metody eksperymentalnej, bez odbioru
trafności domen ani zamknięcia badawczych 04/13.

## Uruchomienie i test ręczny

W `/home/rlew/projekty/NEtCAT-domains`:

```bash
conda activate netcat
python -m stmdomains.main
```

1. Otwórz `data/TTMAPP/detection_full.moltrack.json`. Jeśli pojawi się
   potwierdzenie MPP, sprawdź ścieżkę i wybierz **Użyj tego pliku**.
   Nie otwierasz żadnego modelu ani wyniku v0.4.
2. Wybierz klatkę **259** i kliknij **Analizuj klatkę · K5**. Postęp pokazuje
   przygotowanie otoczeń, ocenę/kalibrację porządku, dopasowanie klas i domeny.
   Po zakończeniu obraz pokazuje końcowe kolory domen i licznik **120 / 312,
   6 domen** w opisanej lokalnej próbie. Zmaksymalizuj okno, wybierz
   **Oryginał**, włącz **Centra** i wyłącz ramki/maski, aby ocenić molekuły.
3. Przełącz **Domeny / Klasy**. Domeny mają lokalne identyfikatory; różne
   domeny tej samej klasy mają różne kolory. Klasy to końcowe przypisania
   spośród pięciu dopasowanych grup, a nie same etykiety wstępne. Legenda
   podaje liczbę molekuł; dłuższą legendę przewiń poziomo.
4. Kliknij szarą molekułę. Opis pod obrazem i jego dymek podają odmowę;
   **Dane oznaczenia…** zawierają jej szczegóły. Pominięty duplikat jest
   odrębny od aktywnej nieprzypisanej molekuły i nie wchodzi do mianownika.
   Przy nakładających się punktach aktywny ma pierwszeństwo wyboru/rysowania
   w trybach Domeny/Klasy; tryb **Wejściowe** zachowuje inspekcję zapisu.
5. Zmień zoom, gamma i **Oryginał/Wyrównany**. Przypisania pozostają na tych
   samych molekułach. Wybierz **Dane…** przy legendzie: status, parametry,
   źródło, skala, kalibracja i rzeczywiście dopasowany model są dostępne
   w osobnym oknie. Jego otwarcie zatrzymuje odtwarzanie.
6. Przejdź do jeszcze nieanalizowanej **268**: widok pokazuje **Brak analizy**.
   Uruchom obliczenia. Powtórz je na 259 i sprawdź powtarzalność; sprawdź
   też 7 i 120. Klasy są lokalne dla każdej klatki: ta sama liczba/kolor
   na różnych klatkach nie oznacza tego samego typu ani śledzonej domeny.
7. Podczas analizy wybierz inną klatkę lub kliknij **Anuluj**. Spóźniony
   wynik nie podmienia nowego obrazu, poprzedni ukończony wynik zachowuje się
   przy powrocie do jego klatki. Zmiana serii usuwa jej poprzednie wyniki.
   Zamknij program również w trakcie kalibracji — terminal wraca bez traceback.

Wyniki są przechowywane w pamięci bieżącej serii, po jednym na klatkę.
Trwały zapis projektu należy do 13. Ręczne K i zakres dopasowania należą
do 07, regulacja tworzenia domen do 06; teraz analizowana jest jedna klatka
z jawnym bazowym **K5**. Zbyt mało danych nie powoduje ukrytej zmiany K.

### Kontrole do otwarcia w tym samym UI

```bash
python -m stmdomains.tools.analysis_demo
```

Otwórz `.scratch/stmdomains-ui-05/demo/series.moltrack.json`. Generator
tworzy wyłącznie MPP i oznaczenia — wynik za każdym razem oblicza aplikacja.

| Klatka | Scenariusz | Oczekiwany stan po Analizuj |
| --- | --- | --- |
| 1 | Pięć odseparowanych pól sieci, jeden duplikat | `complete`, 357 / 405 aktywnych, 17 domen, 1 duplikat |
| 2 | Wsparcie do K5, silne bariery obrazu | `complete`, **0 / 405, 0 domen** |
| 3 | Brak oznaczeń | **Brak oznaczeń do analizy**, nie potwierdzona pusta powierzchnia |
| 4 | Cztery oznaczenia | **Brak dopasowania klas**, wyjaśnienie zbyt małej ilości danych do K5 |
| 5 | Powtórzona geometria klatki 1 | Przed kliknięciem **Brak analizy**; po kliknięciu 357 / 405, 17 domen |

Osobny `single.moltrack.json` zawiera tylko pierwszą klatkę: daje ten sam
wynik bez pozostałych obrazów. Pięć geometrycznych pól rozpadło się na
**17 domen**: kontrola jawnie pokazuje rozdrobnienie tej metody, nie dowodzi
poprawności podziału. Klatka 2 służy sprawdzeniu poprawnie obliczonego zera,
które trzeba odróżnić od niemożliwego dopasowania i braku analizy.

## Wykonane sprawdzenia

W istniejącym **netcat**, bez instalacji:

- Testy publicznego obliczenia jednej klatki: K5, brak/puste/niepełne dane,
  minimum próbek, ID, powtarzalność, kolejność oznaczeń, skalowanie obrazu,
  duplikaty, proweniencja i anulowanie kalibracji; dodatkowo zakończony zerowy
  wynik po barierach. Osobno testy prezentacji, kontrolera oraz całego okna.
- Pełny zestaw STM Domains: **340 passed, bez pominięć, 26,92 s**,
  w tym 32 nowe testy. Uruchomiony raz po poprawkach i przeglądach:

  ```bash
  QT_QPA_PLATFORM=offscreen OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 python -m pytest -q tests/stmdomains
  ```
- Mypy **38 modułów PASS**:

  ```bash
  python -m mypy --follow-imports=silent --ignore-missing-imports stmdomains/analysis stmdomains/core stmdomains/io stmdomains/ui stmdomains/tools
  ```

- Kontrola długości nowych/zmienionych plików: **20 plików, maksimum 394 linie**;
  `python -m stmdomains.tools.check_code_size --base 2d01c5e`.
- **316 lokalnych odnośników do plików w 9 zmienionych dokumentach PASS**;
  `git diff --check` PASS.
- Rzeczywiste dane TTMAPP: każdą wskazaną klatkę obliczono dwukrotnie,
  uzyskując identyczne członkostwo. Nie porównywano wyłącznie numerów domen.

  | Klatka | Aktywne | Przypisane | Domeny | Pominięte duplikaty |
  | --- | ---: | ---: | ---: | ---: |
  | 7 | 317 | 245 | 12 | 1 |
  | 120 | 248 | 67 | 3 | 1 |
  | 259 | 312 | 120 | 6 | 0 |
  | 268 | 308 | 145 | 5 | 0 |

- Podczas próby obliczeń i GUI mechanizm kontroli odczytów odrzucał dostęp
  do paczek i starych artefaktów v0.4: **0 takich odczytów**, obliczenia PASS.
  SHA-256 wejściowego MPP i JSON przed/po identyczne. Wyniki różnią się
  od dawnego eksportu, ponieważ dopasowanie i skala są teraz lokalne.
- Rzeczywiste GUI X11/xcb sterowane Qt: analiza przez przycisk, cztery klatki
  TTMAPP w raw/aligned, powtórzenie 259, klasy/domeny, kliknięcie odmowy,
  zoom/gamma, nawigacja/anulowanie podczas pracy, wszystkie kontrole i osobna
  seria jednej klatki. Układ 900×650 stabilny, panel wyniku ma jeden wiersz
  35 px; sam obraz ma tam około 132 px wysokości. W zmaksymalizowanym oknie
  raw259 ma około 853 px wysokości. Obejrzano zrzuty obu rozmiarów.
- Wyjście podczas komunikatu kalibracji kończy proces kodem **0**, obie pule
  mają zero aktywnych workerów. GUI osiągnęło maksymalną przerwę pomiędzy
  sygnałami testowego timera **0,227 s**, szczyt RSS około **1288 MiB**.
- Samo obliczenie około **0,66–0,72 s/klatkę**, RSS procesu próby około
  **523 MiB**. Próba 259 bez OMP/MKL/OPENBLAS_NUM_THREADS: **0,704 s**, ten sam
  wynik. Zwykłe uruchomienie nie wymaga ręcznego ustawiania tych zmiennych.
  Są to pomiary lokalne, nie gwarancja czasu dla innych danych.

Sprawdzenie agenta w GUI jest odrębne od ręcznego odbioru użytkownika.
Artefakty: `.scratch/stmdomains-ui-05/` — `method-smoke.json`, `gui-smoke.json`,
`default-threads.json`, skrypty, zrzuty i demo; pozostają poza Git.

SHA-256 użytych danych w `data/TTMAPP/`:

- `detection_full.moltrack.json`:
  `d0c4cb999bede28edb5dfd18ddbe146054711382f1c78363055be2330b3cdd2e`.
- `MOVIE_23raw_TTMAPP_I_AU111.MPP`:
  `8fbbfa5d515a90552c13cee2dbd289ff5cc16f000315547185c2a57bfe9f7c66`.

## Przegląd code-review

Dwa niezależne przeglądy przypięte do `2d01c5e...fb37431`.

### Standards

**0 naruszeń reguł repozytorium, 0 usterek blokujących.** Jedna nieblokująca
uwaga: bazowe stałe raportu są powtórzone w modułach obliczeń. Obecnie są
zgodne; w [06](06-tune-domain-formation.md) zapisano wymaganie wspólnego
źródła ustawień dla obliczeń i proweniencji. Nie wprowadzamy kontrolek 06
w ramach tego ticketu. Próba anulowania barier na silnie fragmentowanych
obrazach 1024² i 2048² zakończyła się odpowiednio 0,012 i 0,074 s po żądaniu;
nie wykazała blokującej regresji.

### Spec

**Brak niezgodności wymagających poprawki.** Oceniono wszystkie kryteria
05, wspólny kontrakt UI, rzeczywistą ścieżkę obliczeń, przypisania po ID,
stany braku danych oraz ochronę przed publikacją spóźnionych wyników.
Recenzent niezależnie uruchomił **21 testów obliczeń i prezentacji — PASS**.
Nie traktuje to skuteczności naukowej metody jako zaakceptowanej.

Przed przeglądem usunięto dodatkowo rozbieżność wyniku i widoku, kiedy analiza
kończyła się podczas przygotowania gamma, a przygotowanie obrazu zgłaszało
błąd. Test kontrolera odtworzył błąd i potwierdził, że ukończony wynik jest
publikowany na zachowanym obrazie tej samej klatki. Iterowanie po składowych
barier ograniczono do ich obszarów zamiast powtarzanych skanów całego obrazu.

## Metoda, pochodzenie i ograniczenia

Kod źródłowy v0.4 posłużył do adaptacji opisu wektorów par, oceny porządku,
grupowania, barier i segmentacji do modułów aplikacji. Nie uruchamiamy
skryptów paczki i nie korzystamy z jej zapisanych modeli, etykiet ani kalibracji.
Wejście analizy zawiera wyłącznie oryginalny obraz jednej klatki i jej
oznaczenia. Gamma i wyrównanie służą podglądowi, nie zmieniają wejścia obliczeń.

Skala jest medianą najbliższego sąsiada po deterministycznym tłumieniu
duplikatów. Wstępna skala trzeciego sąsiada wyznacza próg ich bliskości;
pierwszeństwo mają oznaczenia ręczne, potem większa pewność i stabilne ID.
Histogram par 14×36 przechodzi do opisu Hellingera, PCA do najwyżej
24 składowych (ograniczonego liczbą próbek) oraz KMeans K5, seed 24.
Nie mapujemy etykiet na dawne q/w/e/r/t.

Ocena porządku korzysta z maksimum koherencji Fouriera skorygowanej o liczbę
punktów, z promieniem 3 rozstawów i sigma 4/3 rozstawu. Kalibrację generujemy
deterministycznie (seed 20261102): pola 12×12 rozstawów, 60/120/180 punktów,
Poisson oraz wykluczenie odległości 0,6 rozstawu, dwa powtórzenia. Próg
95. percentyla zależy od efektywnego wsparcia; bardziej zachowawczy z dwóch
typów kontroli trafia do oceny. Wymagane wsparcie: 10 lokalnych punktów,
8 efektywnych. To próg eksploracyjny, nie skalibrowane prawdopodobieństwo
poprawności domeny. Jeden kierunek okresowości nie potwierdza sieci 2D.

Klasy mają margines 0,075 i promień 95. percentyla ×1,10. Graf łączy punkty
tej samej zaakceptowanej klasy do 1,5 rozstawu, z odległością Hellingera
do 0,20 i średnicą całego regionu do 0,50. Minimum 8 molekuł obowiązuje
także po rasteryzacji wsparcia i rozcięciu barierami. Raster służy sprawdzeniu
spójności, nie jest zwalidowaną miarą powierzchni domeny.

Bariery obrazu zakładają jasne przejścia w dół obrazu bliskie poziomym;
nie stanowią uniwersalnej detekcji tarasów. Długości wynikają z rozstawu
bieżącej klatki, a użyte wartości i progi kontrastu są zapisane w wyniku.
Klasy nie mają wspólnego znaczenia między niezależnie analizowanymi klatkami.
K5 może dzielić jednorodne struktury lub dawać rozdrobnione domeny.

Wynik zachowuje SHA-256 obrazu i oznaczeń z informacją używaną do priorytetu
duplikatów, indeks roboczy/źródłowy, parametry, kalibrację oraz rzeczywiście
dopasowane PCA/centroidy/promienie i identyfikator modelu. Limity pierwszej
wersji: **3000 oznaczeń, 4 194 304 piksele**, skończony obraz 2D; przekroczenie
lub nieprawidłowe dane ma jawne wyjaśnienie. Kalibracja fizyczna/rejestracja
zachowują dotychczasowe ograniczenia źródła; analiza jest opisana w pikselach.

## Przekazanie integracyjne

Zmiany tylko w STM Domains, jego testach i dokumentacji. Nowa ścieżka używa
NumPy/SciPy, scikit-learn i threadpoolctl, dostępnych w `netcat`.
Integrator powinien uwzględnić scikit-learn/threadpoolctl w deklaracji
zależności STM Domains obok wcześniej zgłoszonych NumPy/SciPy i pytest-qt
dla testów. Konfiguracji wspólnej nie zmieniano. Następny ticket: **06 —
strojenie tworzenia domen**; ręczne K i zakres w 07, Auto w 12.
