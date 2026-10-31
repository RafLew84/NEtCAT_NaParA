# REG-03 — maski oryginalnych klatek

Data: 2026-10-31. Status: `ready-for-review`; odbiór użytkownika niewykonany.
[Ticket](../issues/03-manual-masks.md), [instrukcja manualna](../manual-masks-manual.md).
Baza przeglądu: `270097b` (zamknięcie zaakceptowanego REG-02a).
Implementacja: `868dae4`; poprawka kart porównania: `b318e1d`;
obsługa NaN w renderowaniu: `5bc7175`, uproszczenie transportu integer: `61fa45c`.
Gałąź `viewer/registration-difficult-movies`. Brak zmian wspólnych modułów.

## Wynik i ograniczenia

Edytor pokazuje original, przechowuje prostokąty „użyj”/„pomiń” przy źródle
klatki i wyświetla rzeczywistą maskę dostępnych próbek. Bez „użyj” podstawą
jest cała dostępna klatka; potem odejmowana jest suma „pomiń”. Zoom, przesuwanie,
proporcje i gamma nie zmieniają współrzędnych. Usunięcie klatki usuwa jej maskę;
nowy poprawny import czyści komplet, nieudany zachowuje go.

**Korelacja z maskami (v1)** używa obu masek w masked NCC scikit-image 0.25.2.
Wyłączenie oznaczeń uruchamia ten sam algorytm na wszystkich skończonych próbkach.
Nie jest to Phase ani wariant bez normalizacji z REG-02. Maski nie sterują
Deep Matcher, Optical Flow, ECC ani Tile+RANSAC. Parametry v1: overlap_ratio=0,3,
minimum 64 próbki i rozpiętość 4 px w obu osiach, również kontrola wspólnego
obszaru po przesunięciu. Odmowa jest jawna, bez próby zastępczej.
Nie ma niezależnie potwierdzonej pewności: status „Do sprawdzenia”, quality=None.
Zerowe XY pierwszej klatki nadal oznacza ustalone odniesienie.

Para i pełna seria korzystają z tego samego estymatora, z niezmienną kopią
masek z chwili startu. Zmiana oznaczeń zachowuje wcześniejsze próby i aligned;
wynik podmieniany jest dopiero po udanym kolejnym obliczeniu. Blokady, postęp,
anulowanie i zachowanie poprzedniego filmu działają również z maskami.
Wartości pominięte podczas estymacji pozostają w obrazach oraz MPP/AVI.
MPP zachowuje nazwę/wersję metody i stan włączenia masek; edytowalne prostokąty
żyją w sesji programu. Ich zapis na dysku jest zakresem REG-07.

## Automatyczne sprawdzenia

- Nowe granice: model masek i rzeczywista estymacja, GUI z oryginalnymi
  współrzędnymi, utrzymanie źródeł i prób, eksport wartości pod wykluczonym pasem.
  RED/GREEN obejmował kolejne publiczne przypadki. Logi `reg03-*-red*.log`
  zachowano lokalnie; nazwa `reg03-gui-pair-red.log` dotyczy próby, która od razu
  była zielona dzięki wcześniej podłączonemu zachowaniu, nie dowodu RED.
- Wzorzec `masked-artifact.mpp`: 3×64×80. Górne 12 wierszy to silny nieruchomy
  artefakt, reszta przedstawia przesuwaną strukturę. Pierwsza para bez oznaczeń
  daje (0,0), po ich uwzględnieniu (−4,+3). Pełny film: (0,0), (−4,+3), (−7,+1).
  To niezależnie znane pozycje wzorca, a nie porównanie wyniku z samym sobą.
- Eksport: dokładne wartości wszystkich źródłowych pikseli, w tym wykluczonego
  pasma, skala, pochodzenie, czasy, geometria i maska ważności MPP po odczycie.
  FFV1 odczytany rzeczywistym dekoderem: 3 klatki, 7 FPS, zgodność obrazów,
  brak zielonej/czerwonej nakładki. AVI nie zastępuje wartości pomiarowych MPP.
- Pełne repo na `868dae4`: **2237 passed, 14 failed, 16 skipped**, 271,41 s.
  Porównano identyfikatory wszystkich błędów z końcowym logiem REG-02a:
  identyczne 11 błędów MolTrack/SAM2 i 3 NanoTrack; zero nowych, zero błędów Viewera.
  Pełny log i exit status w lokalnym katalogu dowodów. Po poprawkach poniżej
  powtarzane są testy Viewera, nie całego repo.

- Końcowy pełny zestaw Viewera na `61fa45c`: **454 passed, 2 skipped**, 57,47 s.
  Dwa pominięcia to opcjonalne próby rzeczywistych wag LoFTR CPU/CUDA;
  nie ustawiano `STMVIEWER_TEST_LOFTR_WEIGHTS`. REG-03 używa CPU masked NCC.
  Powiązany zestaw regresji NaN/GUI/zasobów: 37 PASS.
- Mypy strict: **49 plików bez błędów**. Ruff dla zmienionych plików PASS,
  `git diff --check` PASS. 21 nowych/zmienionych plików Python, największy
  `main_window.py`: 915 linii; `pair_dialog.py`: 561. Wszystkie poniżej 1000,
  zatem także limitu 1500. Lokalne odnośniki instrukcji sprawdzone.

Komendy końcowego sprawdzenia w środowisku netcat:

```bash
PYTHONDONTWRITEBYTECODE=1 QT_QPA_PLATFORM=offscreen OPENBLAS_NUM_THREADS=1 \
PYTHONPATH=.:tests/moltrack:tests/stmviewer python -m pytest tests/stmviewer \
  --import-mode=importlib -q -p no:cacheprovider
python -m mypy --config-file stmviewer/mypy.ini --cache-dir /tmp/reg03-mypy
```

Pełny zestaw repo używał tej samej komendy pytest bez `tests/stmviewer`.
Log końcowego Viewera: `data/registration-reg03-review/reg03-viewer-final.log`.

## Widoczne GUI — próby sterowane skryptem

Ubuntu, Qt/xcb, rzeczywiste okna. To odrębny dowód od automatycznych prób
Qt offscreen i od manualnego odbioru użytkownika.

- Wzorzec: narysowano trzy pasy 12 px, sprawdzono 4160/5120 używanych próbek,
  kółko, pan z zachowaniem zoomu i gamma. Wynik zachowany bez masek (0,0)
  pozostał niezmieniony po edycji; bieżący z maskami (−4,+3). Pełny film
  daje znane skumulowane XY. Obejrzano edytor i okno główne.
- Pierwsza próba xcb wykryła poziome przewijanie panelu pary (39 px), którego
  nie ujawniła domyślna czcionka offscreen. Powtórzono problem w teście z
  czcionką 11 pt (56 px), rozdzielono opis metody i stan masek w kartach.
  Końcowa próba przy 1080×760: zakres poziomy 0; wszystkie cztery wiersze
  kart są czytelne. Wcześniejsze sterowanie ręczne pozostaje dostępne.
- MOVIE_8: edycja oryginałów 1/2, pełna seria 84 klatek z maskami ukończona
  w 12,03 s. Wykluczenie całej źródłowej 17 daje czytelną odmowę i identyczny
  poprzedni aligned. Następne obliczenie anulowano przyciskiem; poprzedni
  wynik pozostaje. Edycja była zablokowana, gamma i przeglądanie dostępne.

Końcową syntetyczną próbę xcb powtórzono na `61fa45c`: PASS.
Zrzuty, raporty i skrypty: `data/registration-reg03-review/gui-xcb/` i katalog nadrzędny.

## Rzeczywiste MOVIE_4 i MOVIE_8

Źródłowe pliki oraz SHA-256 są w lokalnym `real-data/report.json` i
[rozpoznaniu](../../registration-difficult-movies.md#dane). MOVIE_4 obejmuje
362 klatki źródłowe 3–364, MOVIE_8 wszystkie 84. Dla każdego oznaczono pasy
w sześciu klatkach: źródłowe 3/4, 33/34, 120/121 oraz 1/2, 16/17, 56/57.
Pozostałe klatki używają całych dostępnych obrazów. Dokładne prostokąty zapisano
w raporcie oraz w skrypcie odtworzenia poniżej; nie są rekomendacją optymalnej maski.

| Film / para źródłowa | Maski wyłączone, XY px | Maski włączone, XY px |
| --- | --- | --- |
| MOVIE_4 3→4 | (20, 12) | (20, 12) |
| MOVIE_4 33→34 | (−23, −32) | (−23, −32) |
| MOVIE_4 120→121 | (4, −157) | (4, −157) |
| MOVIE_8 1→2 | (14, 0) | (14, 0) |
| MOVIE_8 16→17 | (−26, −31) | (−26, −34) |
| MOVIE_8 56→57 | (−39, 6) | (−39, 6) |

| Pełny film | Bez oznaczeń | Z oznaczeniami | Końcowe XY z oznaczeniami |
| --- | --- | --- | --- |
| MOVIE_4, 362 klatki | 13,50 s | 13,79 s | (−249, 1628) px |
| MOVIE_8, 84 klatki | 10,27 s | 10,36 s | (−180, −271) px |

Wszystkie próby ukończone. Sprawdzono mały eksport MPP po ponownym odczycie,
3 klatki FFV1 przy 7 FPS oraz rzeczywiste anulowanie podczas renderowania aligned.
Źródłowe MPP zachowały SHA. **Wynik jakości pozostaje niepotwierdzony**:
MOVIE_4 nadal ma duży błędny dryf; wybór tych pasów nie stanowi rozwiązania
trudnych filmów. Zmiana XY lub ukończenie obliczeń nie jest oceną wizualną.
Jedno przesunięcie całej klatki nie naprawia tearingu wewnątrz obrazu.

Odtworzenie prób z katalogu repo, w środowisku netcat (katalog wyniku musi być nowy):

```bash
PYTHONPATH=. python tests/stmviewer/diagnostics/masked_registration_trial.py data /tmp/reg03-new-trial
```

## Standards

Przegląd `270097b...868dae4`: **0 naruszeń, 0 sugestii wymagających zmiany**.
Zakres aplikacji zachowany; osobne moduły modelu, estymacji, edytora i integracji
GUI. Kontroler masek odpowiada za sesję, edytor i dostępność, nie jest zbędnym
pośrednikiem. Podgląd wykorzystuje istniejący zoom i przeliczenie geometrii.
Testy badają publiczne zachowanie i rzeczywiste wyniki, a kontrola asynchronicznego
wywołania scikit-image mieści się w uzgodnionej granicy zewnętrznej.
Dwa przeglądy uzupełniające objęły poprawki do `61fa45c`: wspólny renderer
usunął powielanie przeliczeń i zachował granicę SciPy, a testy obserwują publiczne
wyniki, nie prywatny helper. **Końcowo 0 uwag Standards** dla `270097b..61fa45c`.
Końcowa dokumentacja nie była częścią tego przeglądu implementacji.

## Spec

Przegląd `270097b...868dae4`: **1 potwierdzona uwaga P2**. Dopuszczony przez
masked NCC oryginał z NaN tracił poprawne próbki obok luki podczas interpolacji.
Przy XY=(0,0) liczba ważnych próbek spadała z 5119 do 5116. Naruszało to
zachowanie wartości w aligned i eksporcie. Pozostałe wymagania implementacji
spełnione; brak stwierdzonego rozszerzenia zakresu.

Naprawiono w `5bc7175` i `61fa45c`: para oraz pełny film używają wspólnego
renderera. Całkowite przesunięcia przenoszą dokładne próbki przez `order=0`;
ułamkowe wymagają kompletu próbek o dodatnich wagach interpolacji. Braki nie
są uzupełniane ani renormalizowane. Regresje obejmują XY zerowe, całkowite,
ułamkowe, podgląd pary oraz rzeczywisty MPP roundtrip z 5119 próbkami.
Recenzent niezależnie sprawdził 64 przypadki względem bezpośredniej interpolacji:
oba znaki przesunięć, brzegi, wyjście poza obraz, NaN/Inf. Wszystkie zgodne.
**Końcowo 0 otwartych uwag Spec** na `61fa45c`.

Pierwsza wersja poprawki używała ręcznego kopiowania dla integer i ominęła
obserwowaną przez stare testy granicę alokacji SciPy. Przejściowy pełny Viewer:
447 PASS, 7 FAIL, 2 SKIP; błędy dotyczyły bramek anulowania/MemoryError i słabych
referencji obrazów w trzech plikach testów. Zastąpienie ręcznego kopiowania
przez dokładny transport SciPy zachowało te sprawdzenia bez zmiany starych
testów. Powiązane 37 testów przeszło, a pełny końcowy Viewer podano wyżej.
Log pierwszej próby zachowano jako `reg03-viewer-integer-boundary.log`.

Zestawienie przeglądu: Standards 0 uwag; Spec 1 P2 naprawiona, 0 otwartych.
Najpoważniejsza uwaga Spec dotyczyła utraty wartości obok NaN; Standards nie
zgłosił naruszeń ani sugestii wymagających zmiany.

## Odbiór użytkownika

Oczekuje na wykonanie [scenariusza manualnego](../manual-masks-manual.md).
Należy osobno ocenić działanie funkcji i jakość struktur próbki dla par i pełnych
filmów. Prób w VLC oraz na Windows 11 w tym tickecie nie wykonano.
REG-04 nie został rozpoczęty; wymaga odbioru REG-03 i osobnego zlecenia.
Lokalne dowody: `data/registration-reg03-review/`; dane i duże wyniki poza Git.
