# REG-10: EfficientLoFTR — próba ręczna

Uruchom z katalogu repozytorium, w środowisku `netcat`:

```bash
python -m stmviewer.main
```

## Model i wybór metody

Wybierz **EfficientLoFTR** w istniejącym polu metody. Dotyczy to głównego
okna rejestracji, **Porównaj parę…** i **Dopasowanie wieloklatkowe…**.

Przygotowane lokalne ścieżki są domyślnie wpisane:

- kod: `/home/rlew/.cache/stmviewer/efficientloftr/source`;
- wagi: `/home/rlew/.cache/stmviewer/efficientloftr/weights/eloftr_outdoor.ckpt`.

W razie przeniesienia plików użyj **Wybierz katalog kodu…** oraz
**Wybierz wagi…**. Przełączenie między Deep a Efficient pamięta osobno ścieżki
w bieżącym oknie. **Sprawdź model** w głównym oknie sprawdza zawartość plików,
zgodność modelu i urządzenie. Brak pliku lub biblioteki daje opis przyczyny.
Aplikacja używa wyłącznie lokalnych plików.

**Auto** wybiera CUDA, jeśli jest dostępna w Torch; w przeciwnym przypadku
CPU. Jawny wybór CUDA wymaga działającego CUDA. Błąd wykonania, brak pamięci
lub anulowanie nie zmienia metody ani urządzenia. Model jest ładowany raz
na zadanie i zwalniany po jego zakończeniu.

Wersje, źródła i SHA-256: [przygotowanie modelu](efficient-loftr-setup.md).
Opcjonalne zależności aplikacji: `stmviewer/requirements-efficient.txt`.
W `netcat` zostały już przygotowane; nie trzeba ponownie instalować Torch.

## Oglądanie wyniku pary

1. Otwórz `tests/stmviewer/fixtures/registration/cpu.mpp`, następnie
   **Porównaj parę…**. Wyznacz najpierw Deep i użyj **Zachowaj do porównania**.
2. Wybierz EfficientLoFTR i oblicz wynik. Używaj tego samego zoomu i gamma
   dla obu metod. Przełączaj klatkę bazową, przesuwaną i nakładkę.
3. Pod wynikiem są liczba zgodnych punktów, rozrzut przesunięć i zasięg X/Y.
   Dwie siatki 4 × 4 pokazują liczbę zgodnych punktów w częściach obu
   oryginalnych obrazów. Górny wiersz odpowiada górze obrazu.
4. **Szczegóły wybranego wyniku** zawierają ustawienia, przygotowanie obrazu
   objaśnione jako tekst. Pełne przygotowanie i pochodzenie modelu są zapisane
   w sesji. Liczba punktów i mały rozrzut nie są niezależnym
   potwierdzeniem jakości STM; wynik wymaga oględzin struktur.
5. Przy odmowie nie powstaje nowe XY. **Pokaż poparcie odrzuconej próby**
   pokazuje jej diagnozę i obrazy bez przesunięcia. Poprzedni wynik zostaje.
   Dla odrzuconej próby zastosowanie do filmu jest niedostępne.

EfficientLoFTR i stary Deep mają różne agregacje punktów do XY; porównanie
ocenia cały estymator. Wspólne pozostają oryginały, lista par, solver i renderer.

## Pełne filmy i graf

1. W `data/MOVIE_4.mpp` usuń dwie pierwsze klatki przed obliczeniami.
   Zostaje 362 klatek. Bieżące 29→30 odpowiada źródłowym 31→32.
   W `data/MOVIE_8.mpp` zachowaj wszystkie 84 klatki.
2. **Rejestruj** dopasowuje kolejne oryginalne pary. Po sukcesie pokazuje
   aligned; pojedyncza odmowa przerywa tę nową próbę z numerem pary.
   Dotychczasowy aligned pozostaje dostępny.
3. W **Dopasowanie wieloklatkowe…** wybierz EfficientLoFTR i okno 3 albo 5.
   Lokalna odmowa pozostawia brakującą relację. W **Relacje i rozbieżności**
   wybierz parę i **Obejrzyj wybraną parę**, także dla odmowy.
4. Kompletny graf można oglądać, przeliczyć Huberem i jawnie zastosować
   przez **Zastosuj wynik do filmu**. Rozłączny graf zachowuje diagnozę;
   nie daje kompletu pozycji do zastosowania. Huber nie uzupełnia brakujących
   połączeń i używa już zapisanych pomiarów.
5. Sprawdź anulowanie przy istniejącym aligned. Po anulowaniu pozostają
   poprzednie obrazy i eksport. Duże zadanie anuluje się po bieżącym kroku.

Oglądaj pary i zakresy z [protokołu](manual-protocol.md), w tym MOVIE_4
29→30, 35→36, 44–46, 61→62 oraz 94–97 po odrzuceniu pierwszych dwóch klatek.
Stan prób automatycznych i odmowy opisuje [raport](efficient-loftr-results.md).
Brak pełnego wyniku jest możliwym wynikiem eksperymentu z tym modelem.

## Sesja, korekty i eksport

Na krótkim kompletnym wyniku zastosuj ręczną korektę jednej pary. Sprawdź,
że następne klatki zachowują względne dopasowanie. Zapisz sesję i otwórz ją
ponownie: obraz, aktywny wynik, osobny kandydat i diagnostyka mają zostać.
Oglądanie sesji działa bez wag i kodu modelu; nowe obliczenie ich wymaga.

Zapisz aligned do MPP i małe AVI, ponownie otwórz MPP w Viewerze oraz AVI
w VLC. Eksport zawiera poprawione obrazy; siatki poparcia nie trafiają do filmu.
MPP zachowuje geometrię i pochodzenie; pełne relacje grafu zachowuje sesja.

## Wzorce dodatkowe

Generator dostarcza znane przesunięcia, nieruchomy pas, ruch różnych części
obrazu i wzorzec okresowy:

```bash
PYTHONPATH=.:tests/stmviewer python tests/stmviewer/make_local_consensus_fixtures.py \
  --output /tmp/reg10-patterns
```

W `stationary-artifact.mpp` pas pozostaje nieruchomy, a struktury przesuwają
się o (+7, −5) px. W `one-band.mpp` tekstura jest skupiona w jednym pasie.
Sprawdź, czy metoda pokazuje rozproszone poparcie albo uczciwą odmowę.
W `split-motion.mpp` pojedyncze globalne XY nie dopasuje obu połówek.
Generator i manifest określają znane ruchy; wyniku na STM nie oceniamy
przez samą zgodność solvera lub gładkość filmu.
