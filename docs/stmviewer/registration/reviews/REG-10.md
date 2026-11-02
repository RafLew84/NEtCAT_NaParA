# REG-10 — karta wykonania i odbioru

Data: 2026-11-02. Status REG-10: **done**, użytkownik potwierdził
„testy manualne ok” po poprawce v2. Poniższy przegląd dotyczy pierwotnej
implementacji; [przegląd poprawki](REG-10-weak-results.md).
Gałąź: `viewer/registration-difficult-movies`. Baza: `03ad8d9`.
Implementacja: `6644d8c`; aktualizacja oczekiwania GUI i raportu: `7f96103`.
Commit dokumentacji odbioru w końcowym przekazaniu.
[Ticket](../issues/10-efficient-loftr.md),
[instrukcja manualna](../efficient-loftr-manual.md),
[rzeczywiste wyniki](../efficient-loftr-results.md).

## Standards

Niezależny przegląd `03ad8d9…6644d8c`: **0 ustaleń**.
Zmiana pozostaje w zakresie Viewera. Runtime modelu, przygotowanie obrazów,
agregacja, diagnostyka i zapis mają oddzielne odpowiedzialności. Para, seria
i graf zwalniają model także przy odmowie, awarii i anulowaniu. Testy są
na uzgodnionych granicach; silnik korespondencji jest granicą modelu zewnętrznego,
a rzeczywiste próby są wydzielone. Nie znaleziono naruszeń udokumentowanych
zasad ani istotnych problemów z listy heurystyk.

Przegląd delty `6644d8c..7f96103`: **nadal 0 ustaleń**. Lista metod GUI
uwzględnia nową pozycję; raport używa wspólnej interpretacji statusu i braku
oceny zamiast technicznego zera backendu. Kod aplikacji nie zmienił się w delcie.

## Spec

Niezależny przegląd `03ad8d9…6644d8c`: **0 ustaleń**. Sprawdzono wspólną
estymację pary/serii/grafu, odwzorowanie do original, padding, przestrzenne
odmowy, lokalne pliki i ich przypięcie, brak fallbacku, ponowne użycie oraz
zamknięcie modelu, sesje offline, kandydata i aktywny wynik, ręczne korekty
oraz MPP/AVI. Recenzent nie oceniał wizualnej jakości STM.

Przegląd delty `6644d8c..7f96103`: **nadal 0 ustaleń**. Oczekiwanie GUI
odpowiada nowej metodzie, a raport pokazuje `manual_review` i brak wskaźnika
jakości. Zakres i testowane zachowanie pozostają zachowane.

Podsumowanie przeglądów: Standards — 0 otwartych; Spec — 0 otwartych.

## Testy automatyczne

- Pełny zestaw repo uruchomiono **raz**: **2480 passed, 18 failed, 22 skipped**,
  286,19 s. Z tego Viewer: **694 passed, 4 failed, 8 skipped**.
- Cztery błędy Viewera dotyczyły jednej parametryzowanej listy metod GUI,
  która nadal oczekiwała ośmiu pozycji. W `7f96103` dodano EfficientLoFTR
  do oczekiwania. Bez zmiany kodu aplikacji.
- Po poprawce **66 celowanych testów zaliczonych**, 3,80 s: wszystkie cztery
  powyższe scenariusze oraz granice nowego backendu, agregacji, grafu,
  diagnostyki, sesji/MPP i GUI. Po połączeniu zakresów mamy **698 zaliczonych
  testów Viewera i 8 pominiętych**, bez pozostawionego błędu Viewera.
  Nie przedstawiamy tego jako drugiego pełnego przebiegu repo.
- Pozostałe **14 błędów** dokładnie odpowiada 14 identyfikatorom z
  `/tmp/reg08e-full-suite.xml` — wcześniejsze MolTrack SAM2 / NanoTrack.
  Nie naprawiano wspólnych aplikacji w tej sesji.
- Osiem pominiętych testów Viewera to dwa wcześniejsze testy rzeczywistych
  wag Deep i sześć nowych prób opt-in Efficient. Osobny końcowy przebieg
  z lokalnym modelem: **6 passed**, 6,65 s, CPU/CUDA, para/seria/graf,
  ręczna korekta, sesja, MPP i odczyt AVI FFV1. Stary Deep został dodatkowo
  wykonany na obu pełnych filmach i wzorcach porównawczych.
- RED→GREEN: znane XY, odrzucenie odstających/paddingu, wąski i ukośny pas,
  rozkład tylko w dwóch wierszach/kolumnach, brak/złe pliki, OOM/anulowanie,
  wybór metody, publiczna para → seria → graf, błędna geometria/metadane,
  sesja bez modelu, MPP, odmowa GUI i czytelna siatka 4 × 4.
- Strict mypy: **90 modułów bez błędów**. Ruff, odnośniki i diff-check
  poprawne. Największy zmieniony plik kodu: **970 linii**, poniżej limitu 1500.

Logi: `/tmp/reg10-full-suite.log`, `/tmp/reg10-full-suite.xml`,
`/tmp/reg10-targeted.log`, `/tmp/reg10-targeted.xml`,
`/tmp/reg10-real-final.log`, `/tmp/reg10-real-final.xml`.

Pełny zestaw (z `netcat`):

```bash
PYTHONDONTWRITEBYTECODE=1 QT_QPA_PLATFORM=offscreen OPENBLAS_NUM_THREADS=1 \
PYTHONPATH=.:tests/moltrack:tests/stmviewer python -m pytest --import-mode=importlib \
  -q -p no:cacheprovider -o faulthandler_timeout=120
```

## Odbiór i ograniczenia

Pełne filmy oraz wzorce rzeczywiście przeliczono; ich wyniki i źródła są
w osobnym raporcie. Pierwotny EfficientLoFTR odmawiał wielu relacji i nie
tworzył kompletnego aligned dla MOVIE_4/MOVIE_8; nie zastąpiono go inną metodą.
Działający cykl zastosowania/korekt/eksportów sprawdzono na kompletnych
wzorcach. Nie zadeklarowano poprawy STM na podstawie liczby punktów.

Qt offscreen, obejrzane zrzuty i odczyt AVI przez bibliotekę są automatycznymi
sprawdzeniami. Ręczny odbiór użytkownika zakończono po poprawce v2
2026-11-02. Windows 11, VLC i docelowa karta 8 GB VRAM nie mają
osobnego potwierdzenia. REG-11/12 nie zostały rozpoczęte; REG-06/09
pozostają odłożone. Nie zmieniono modułów wspólnych, nie publikowano ani
nie scalano gałęzi. Dane i modele pozostają lokalne.
