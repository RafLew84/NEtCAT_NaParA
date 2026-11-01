# REG-08a — ręczna próba dopasowania wieloklatkowego

Status: implementacja gotowa do próby (`ready-for-review`); odbiór użytkownika niewykonany.

## Uruchomienie

W `NEtCAT-viewer`, środowisko `netcat`:

```bash
python -m stmviewer.main
```

Do obliczeń wybierz lokalne `loftr_outdoor.ckpt` i CPU lub CUDA. Otwarcie
zapisanej sesji oraz podgląd jej wyników nie wymagają modelu. Program nie
pobiera wag. Na tym stanowisku checkpoint znajduje się pod:

```text
/home/rlew/projekty/tracker-import-20261008/trackers-windows-20261008/model_cache/torch/hub/checkpoints/loftr_outdoor.ckpt
```

## Znane XY i przypadki solvera

Generator przygotowuje rzeczywisty film z teksturą oraz sesje z zadanymi
pomiarami. Te ostatnie sprawdzają solver i prezentację, nie działanie Deep:

```bash
PYTHONPATH=.:tests/stmviewer python tests/stmviewer/diagnostics/graph_fixtures.py /tmp/stmviewer-reg08a-fixtures
```

`known-xy.mpp` zawiera siedem wycinków większej sceny; brak zawijania brzegów.
Oczekiwane przesunięcia względem pierwszej klatki w pikselach:
`(0,0), (7,-4), (18,-9), (11,2), (-4,10), (-9,3), (3,-5)`.

1. Otwórz MPP, kliknij **Dopasowanie wieloklatkowe…**, wybierz wagi Outdoor,
   urządzenie i okno 3. Sprawdź liczbę planowanych par, uruchom obliczenie.
   Okno 3 oznacza dopasowanie do maksymalnie trzech wcześniejszych klatek;
   okno 5 — do pięciu. Dla siedmiu klatek daje to odpowiednio 15 i 20 par.
2. Obejrzyj film i przełącz wynik grafu oraz łańcuch sąsiednich dopasowań.
   Oba mają wspólny kadr, kontrast i zoom. Wypróbuj Play/Pause, wybór klatki,
   gamma, kółko myszy i przeciąganie. Pierwsza klatka ma XY `(0,0)`.
3. Oblicz okno 5. Dotychczasowe relacje przy niezmienionych danych i ustawieniach
   są ponownie użyte. Nie jest ponownie ładowany model dla każdej pary.
4. Wybierz relację z tabeli, także niesąsiednią, i otwórz podgląd pary.
   Sprawdź nazwy obu źródeł, pomiar Deep i różnicę wynikającą z położeń grafu.
   Próby takiej pary nie można zastosować jako ręcznej korekty aktywnego filmu.
5. Otwórz kolejno `solver-bypass.stmsession`, `solver-bridge.stmsession`
   i `solver-disconnected.stmsession`. Brak przejścia 3→4 w pierwszej sesji
   ma obejście, więc graf jest pełny, lecz łańcuch nie. Most w drugiej sesji
   jest oznaczony. Trzecia zawiera dwie składowe i odmawia pełnego wyniku XY.
6. `solver-periodic-alias.stmsession` zawiera celowo błędne, spójne pomiary.
   Reszty są bliskie zeru, lecz film jest źle dopasowany. To przykład, dlaczego
   mała reszta nie jest oceną poprawności obrazu.

## MOVIE_4 i MOVIE_8

Gotowe do otwarcia przez **Otwórz sesję…**, a potem **Dopasowanie wieloklatkowe…**:

- `/tmp/reg08a-movie4-final/window-3.stmsession` i `window-5.stmsession`.
- `/tmp/reg08a-movie8-final/window-3.stmsession` i `window-5.stmsession`.
- Wzorzec z rzeczywistym Deep: `/tmp/reg08a-known-final/window-3.stmsession`
  i `window-5.stmsession`.

Te sesje mają aktywną bazę łańcuchową z tych samych pomiarów Deep oraz osobny
kandydat grafu. Źródłowe klatki 1 i 2 MOVIE_4 są już usunięte. Wyniki w `/tmp`
są tymczasowe — do trwałego zachowania użyj **Zapisz sesję…**.

Poniższe kroki pozwalają również odtworzyć obliczenia samodzielnie:

1. Otwórz `data/MOVIE_4.mpp`. Usuń pierwszą klatkę dwukrotnie **przed**
   obliczaniem. Zostają 362 klatki, źródłowe 3–364.
2. Przy tych samych wagach i urządzeniu oblicz okno 3, potem 5. Zapisz osobną
   sesję dla każdego wyniku, jeśli chcesz zachować oba. Bieżąca sesja zachowuje
   jeden kandydat grafu oraz niezależny aktywny aligned.
3. Porównaj łańcuch i graf w miejscach 29→30, 35→36, 44–46, 61→62 i 94–97
   (numeracja po usunięciu). Obejrzyj pierwsze 150 klatek i cały film.
4. Powtórz dla pełnego `MOVIE_8.mpp`. Oceń te same kontury w różnych częściach
   obrazu. Zanotuj poprawę, pogorszenie lub niejednoznaczność. Nie oceniaj
   jakości wyłącznie na podstawie mniejszego kadru lub łagodniejszej trajektorii.
5. Obejrzyj relacje z największymi rozbieżnościami i brakami. Pomiar modelu
   i reszta LS to różne informacje; wskaźnik modelu nie jest wagą solvera.

## Sesja, anulowanie i aktywny film

1. Przygotuj aktywny aligned i ewentualną ręczną korektę. Oblicz graf.
   Podgląd głównego okna, jego korekty oraz eksport MPP/AVI nadal używają
   aktywnego aligned. Kandydat grafu jest oznaczony jako podgląd.
2. Zamknij okno grafu, zapisz `.stmsession`, zamknij program i otwórz sesję.
   Ponownie otwórz dopasowanie wieloklatkowe: relacje, XY i diagnozy pozostają.
   Sam odczyt nie uruchamia rejestracji ani nie wymaga plików źródłowych lub wag.
3. Rozpocznij nowe obliczenie i anuluj. Poprzedni kandydat i aktywny aligned
   pozostają. Podczas obliczeń zmiana serii i zapis są zablokowane;
   przeglądanie głównego obrazu i zoom pozostają dostępne.
4. Zapis MPP/AVI przed i po obejrzeniu grafu ma przedstawiać ten sam aktywny
   wynik. **Zastosowanie grafu do filmu i jego eksport dodaje dopiero REG-08c.**
5. Usunięcie klatki lub poprawne otwarcie innej serii usuwa dotychczasowy graf,
   ponieważ zmienia powiązania z klatkami. Nieudane otwarcie zachowuje pracę.

W karcie odbioru zapisz system, checkpoint, urządzenie, okno i obserwacje
osobno dla obu filmów. Qt offscreen i raport liczbowy nie zastępują tego odbioru.
