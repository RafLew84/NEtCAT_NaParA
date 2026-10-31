# REG-04 — wykonanie i odbiór

Data: 2026-10-31. Baza przeglądu: `29d7fc9`.
Implementacja: `f639fd8`; poprawki po przeglądzie: `1a2766b`.
Status: **ready-for-review**. Ręczny odbiór użytkownika: **niewykonany**.

## Dostarczona funkcja

Osobna metoda **Deep Matcher + ECC (v1)** działa dla pary i całego filmu.
Deep wyznacza start, ECC dostaje dokładnie to XY oraz oryginalne obrazy.
Do sumowania trafia całkowite końcowe XY; aligned jest interpolowany raz
z oryginału. Model jest ładowany raz na serię.

W oknie pary lista **Wynik po ECC / Start Deep tej próby** przełącza estymaty
jednego przebiegu bez ponownego modelu. Zachowany wynik, kadr, gamma, kontrast
i zoom pozostają. UI podaje start, koniec, poprawkę oraz osobne miary i statusy.
Wynik ma `manual_review`, bez automatycznego werdyktu poprawy; ostrzeżenie Deep
pozostaje widoczne nawet przy wysokim score ECC. Pełny film zachowuje lekką
diagnostykę bez dwóch dodatkowych stosów obrazów.

Oba etapy mają postęp i bezpieczne punkty anulowania. Błąd wskazuje parę
oraz etap i zachowuje poprzedni aligned wraz z ręcznymi korektami. Nie ma
zastępowania metody. MPP zachowuje nazwę/wersję, końcowe XY, geometrię i status.
Zapis dokumentu próby z diagnostyką etapów pozostaje w REG-07.

## Testy automatyczne

- TDD: publiczna para, następnie seria, odmowy/anulowanie, GUI i eksport.
  Kontrolowana jest granica zewnętrznego LoFTR; ECC pozostaje rzeczywisty.
  Wzorce mają znane duże/subpikselowe XY obu znaków, niekwadratowe wymiary
  oraz prawdziwe brzegi bez zawijania.
- 21 nowych przypadków: 12 rdzenia, 6 GUI i 3 eksportu/ręcznych korekt.
  Zależności opcjonalne sprawdzono także w świeżych procesach bez bibliotek.
- Końcowy zestaw Viewera: **455 passed, 2 skipped**, 58,69 s. Dwa testy
  wymagają jawnie ustawionej zmiennej lokalnych wag. Oddzielne rzeczywiste
  próby LoFTR na CPU/CUDA opisano poniżej; nie zastępujemy pominięć etykietą PASS.
- Mypy strict: **46 plików PASS**. Ruff i `git diff --check`: PASS.
  Wszystkie zmienione pliki kodu mieszczą się poniżej 1000 linii;
  największy `main_window.py` ma 902 linie (twardy limit 1500).
- Pełne repo: **2236 passed, 18 failed, 16 skipped**, 307,45 s.
  Cztery błędy Viewera dotyczyły starego testu oczekującego dokładnie sześciu
  metod. Listę zaktualizowano o hybrydę; cały plik testów CPU GUI ma
  **34 PASS** i jest objęty końcowym przebiegiem Viewera.
  Pozostałe **14 błędów** (11 MolTrack/SAM2 i 3 NanoTrack) ma identyczne
  identyfikatory jak `/tmp/reg02a-full-suite-final.log`; poza Viewerem nie
  znaleziono nowego błędu. Nie zmieniano wspólnych aplikacji.
- Pierwszy osobny przebieg finalnego Viewera miał 454 PASS, 1 FAIL, 2 SKIP:
  proces potomny testu AVI nie widział `test_avi_raster`, ponieważ brakowało
  `PYTHONPATH`. Kontrolę ponowiono z poprawnym środowiskiem; nie zmieniano
  aplikacji, aby obejść błąd polecenia.

Polecenia końcowych kontroli (`netcat`, katalog `NEtCAT-viewer`):

```bash
python -m mypy --config-file stmviewer/mypy.ini
PYTHONDONTWRITEBYTECODE=1 QT_QPA_PLATFORM=offscreen OPENBLAS_NUM_THREADS=1 \
PYTHONPATH=.:tests/stmviewer python -m pytest -q -p no:cacheprovider tests/stmviewer
```

Pełne repo używało `PYTHONPATH=.:tests/moltrack:tests/stmviewer` i
`python -m pytest --import-mode=importlib -q -p no:cacheprovider`.
Logi: `/tmp/stmviewer-reg04-full-pytest.log` i
`/tmp/stmviewer-reg04-viewer-final-pytest.log`.
Pełny przebieg zaczął się przed poprawkami przeglądu; po nich wykonano
wskazane testy celowane oraz końcowy kompletny zestaw Viewera.

## Rzeczywiste dane i GUI

[Wyniki prób](../deep-ecc-results.md) opisują lokalne wagi, CPU/CUDA,
znane wzorce, 14 wskazanych par oraz oba pełne filmy. MOVIE_4 po usunięciu
źródłowych 1 i 2 (362 klatki) oraz MOVIE_8 (84 klatki) ukończyły Deep
oraz hybrydę bez pomijania par. Cztery MPP ponownie odczytano.
Wzorzec pasów pokazuje także pogorszenie znanego ruchu przez ECC.

Automatyczna próba rzeczywistego Qt (`xcb`) otworzyła MOVIE_4, usunęła dwie
pierwsze klatki i policzyła bieżącą parę 29→30, źródłową 31→32, na CUDA.
Start Deep wynosił (0,678604; 7,234718), wynik ECC (0,414056; 5,287070) px.
Przełączanie obu estymat i oględziny zrzutów potwierdziły działanie oraz
czytelność okna; potem skrócono zapis liczb w panelu diagnostyki do 3 miejsc.
Zrzuty lokalne: `/tmp/stmviewer-reg04-deep.png`, `/tmp/stmviewer-reg04-ecc.png`.
To automatyczne GUI i oględziny, odrębne od ręcznego odbioru jakości filmów.

## Standards

Końcowy zakres `29d7fc9…1a2766b`: **0 otwartych uwag**.
Dwie uwagi heurystyczne o niskim priorytecie naprawiono w `1a2766b`:
ustawienia ECC są opisywane z konfiguracji zamiast powielonych stałych,
a oba okna korzystają ze wspólnej kontroli dostępności metod.
Nie stwierdzono twardych naruszeń udokumentowanych zasad. Przegląd poprawek
nie wykazał nowych uwag.

## Spec

Końcowy zakres `29d7fc9…1a2766b`: **0 otwartych uwag**.
P2 naprawiony w `1a2766b`: ogólne tłumaczenie błędu „too little texture”
usuwało numer pary i etap ECC. Oba publiczne API zachowują teraz kontekstowy
błąd. Regresja była red, następnie green, z rzeczywistą odmową ECC po
kontrolowanym LoFTR. Pozostałe wymagania implementacyjne są zgodne;
nie stwierdzono rozszerzenia zakresu.

Standards: 2 uwagi naprawione, 0 otwartych. Spec: 1 uwaga naprawiona, 0 otwartych.

## Pozostały odbiór

[Instrukcja ręczna](../deep-ecc-manual.md) zawiera dane, kroki, oczekiwane
wyniki, generator i launcher kontrolowanego błędu ECC. Do wykonania przez
użytkownika pozostaje ocena struktur/tearing, odtworzenie AVI w VLC oraz
decyzja, czy zachować hybrydę. Próba Windows nie była wykonana w tym tickecie.
REG-05 czeka na ten odbiór. Lista kryteriów ticketu pozostaje otwarta.

OpenCV nie przekazuje osobnej flagi wyczerpania iteracji; obsługujemy odmowę
zgłoszoną przez bibliotekę, a skończony wynik nadal wymaga oceny wizualnej.
Brak deklaracji poprawy pomiarów na podstawie score, rozmiaru aligned czy
płynności trajektorii. Zmiany wspólnego kodu ani konfiguracji nie są potrzebne.
