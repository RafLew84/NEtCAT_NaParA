# REG-01 — karta odbioru

Status: **done**. Użytkownik potwierdził „testy manualne ok” 2026-10-29.
Data sprawdzeń: 2026-10-28, Ubuntu, środowisko `netcat`.
Implementacja: `4a61ba4`, gałąź `viewer/registration-difficult-movies`.
Baza przeglądu: `b1050103d255f366697887619590bd76d734557e`.

[Ticket](../issues/01-pair-comparison.md) · [Instrukcja próby](../pair-comparison-manual.md)

## Automatyczne sprawdzenia

- TDD na publicznym renderowaniu pary i operacjach GUI: **14 passed**.
  Znane dodatnie/ujemne XY, interpolacja przed gamma, zamrożony wspólny kontrast,
  ważność próbek i brak części wspólnej; A/B, zmiana pary/import/usunięcie,
  ochrona pełnego aligned, błędy, anulowanie i Escape podczas pracy.
- Testy Viewera: łącznie **384 passed, 2 skipped**. Pierwsze osobne wywołanie
  miało 383 passed i błąd importu helpera w teście procesu MJPG; po uzupełnieniu
  `PYTHONPATH=.:tests/stmviewer` ten test przeszedł. Pełny zestaw repo uruchomiony
  z poprawnym PYTHONPATH nie ma błędów testów Viewera.
- Pełny zestaw repo raz na końcu: **2170 passed, 14 failed, 16 skipped**, 264,13 s.
  Zestaw nazw 14 błędów jest identyczny z końcowym logiem ticketu 19
  (`/tmp/stmviewer19-full-suite.log`): MolTrack/SAM2 oraz NanoTrack.
  Nie jest to zaliczenie całego repozytorium; w tym tickecie nie zmieniano tych aplikacji.
- Mypy strict: **36 plików**, bez błędów. Ruff zmienionego kodu i testów: bez uwag.
  Największy zmieniony plik ma **850 linii**; limit 1500 zachowany.
- Rzeczywiste GUI Qt **xcb**, sterowane skryptem: **16 prób zaliczonych**.
  CPU: Phase (+2,−1), następna para (−3,+2), Optical Flow około (+2,−1);
  A/B zachowuje odniesienie, zoom, kontrast i pełny aligned.
- MOVIE_8: Phase na 1→2, 16→17, 56→57; błąd ECC 2→3 zachowuje wcześniejszą próbę.
  MOVIE_4: Phase na 1→2, 33→34, 120→121; Deep Matcher **CUDA:0 / RTX 5090**
  na 1→2 daje (−14,427; −2,24127), błąd zbyt małej liczby inlierów 2→3 zachowuje B.
  Wyjścia backendów nie są dowodem prawidłowego dopasowania rzeczywistych struktur.
- Rzeczywiste anulowanie Optical Flow na dostarczonym wzorcu 1536²: **7,955 s**
  do zakończenia obliczenia, wynik odrzucony, poprzednie B i aligned zachowane.
  SHA-256 wszystkich czterech wejść przed/po identyczne. W tej próbie nie wykonywano eksportów.
- Po skróceniu etykiet ponowna krótka próba MOVIE_8 w xcb: kontrolki mieszczą się,
  zakres poziomego przewijania panelu wynosi 0. Agent obejrzał zrzuty ekranu.

Qt offscreen, skrypt xcb i oglądanie zrzutów przez agenta są sprawdzeniami
automatycznymi, **nie ręcznym odbiorem użytkownika**. Windows nie był sprawdzany.
Lokalne artefakty poza Git: `data/registration-pair-review/` (log pytest,
skrypt i raport GUI, zrzuty, pomiar wzorca). Dane do anulowania:
`data/registration-pair-cancel.mpp`; odtwarzalny generator w
`tests/stmviewer/make_pair_comparison_fixture.py`.

Polecenia sprawdzeń z katalogu repo i aktywnego `netcat`:

```bash
PYTHONDONTWRITEBYTECODE=1 QT_QPA_PLATFORM=offscreen OPENBLAS_NUM_THREADS=1 \
  PYTHONPATH=.:tests/stmviewer python -m pytest -q -p no:cacheprovider \
  tests/stmviewer/test_pair_comparison.py tests/stmviewer/test_pair_comparison_gui.py
python -m mypy --config-file stmviewer/mypy.ini --cache-dir /tmp/reg01-mypy
PYTHONDONTWRITEBYTECODE=1 QT_QPA_PLATFORM=offscreen OPENBLAS_NUM_THREADS=1 \
  MPLCONFIGDIR=/tmp/reg01-mpl PYTHONPATH=.:tests/moltrack:tests/stmviewer \
  python -m pytest -q --import-mode=importlib -p no:cacheprovider
```

## Standards

**0 uwag wymagających poprawki** dla `b105010…4a61ba4`.

Sprawdzono twarde reguły repozytorium i heurystyki projektowe ze skilla code-review.
Zmiany pozostają w zakresie Viewera, wykorzystują istniejące backendy i rozdzielają
estymację, renderowanie oraz obsługę zadania w tle. Największy zmieniony plik ma 850 linii.

Nie znaleziono naruszenia cyklu życia pracownika, ochrony poprzedniego wyniku ani
niezależności prób od pełnego aligned. Testy sprawdzają publiczne operacje i widoczne
kontrolki; nie wiążą asercji z prywatnymi helperami implementacji.

Niezależny przegląd statyczny, tylko do odczytu; bez powtarzania testów i oceny specyfikacji.

## Spec

**0 uwag blokujących** dla `b105010…4a61ba4`.

Porównano diff z REG-01, kontraktami planu i protokołem ręcznym. Implementacja obejmuje
wybór sąsiedniej pary, źródłowe numery, obliczenie pojedynczej próby, A/B z własnymi
ustawieniami i statusem oraz wspólne warunki wyświetlania. Stały kadr odniesienia
odpowiada uzgodnionej geometrii; ograniczenie podglądu jest jawnie opisane.

Ścieżki błędu/anulowania zachowują poprzednią próbę; zamknięcie i Escape oczekują
na zakończenie pracownika. Blokady chronią serię podczas obliczeń, a udany import
i usuwanie klatek unieważniają porównanie. Pełny aligned i eksport są niezależne.
Zakres jasności pomija próbki nieważne, a nakładka pokazuje część wspólną
i komunikuje jej brak. Nie znaleziono nowych algorytmów ani rozszerzenia zakresu.

Niezależny przegląd kodu i testów, bez ponownego uruchamiania GUI. W chwili
przeglądu odbiór użytkownika pozostawał wymagany; potwierdzenie zapisano poniżej.

Wynik przeglądu: Standards 0 uwag, Spec 0 uwag; brak problemu wymagającego poprawki w obu osiach.

## Ręczny odbiór użytkownika

- Data / osoba: 2026-10-29, użytkownik; system niepodany.
- Potwierdzenie: „testy manualne ok”.
- Commit aplikacji: `4a61ba4`; przekazanie: `893b4b1`.
- Dane i kroki przewidziane w instrukcji: cpu.mpp, MOVIE_4.mpp, MOVIE_8.mpp,
  registration-pair-cancel.mpp; A/B, błąd, anulowanie, zamknięcie i ochrona aligned.
- Szczegółowy przebieg, metody A/B, pary, fragmenty i ustawienia podglądu:
  niepodane w potwierdzeniu; nie dopisujemy pomiarów ani wyników poszczególnych kroków.
- Funkcja: odbiór zaakceptowany przez użytkownika.
- Jakość XY i tearing: REG-01 służy porównaniu, algorytmy nie zostały zmienione.
- Decyzja: zamknąć REG-01 jako `done`.

Potwierdzenie spełnia warunek ręcznego odbioru REG-01; REG-02 czeka na osobne
zlecenie. Nie oznacza to końcowego odbioru obu platform. Aktualizacja wyłącznie
dokumentacyjna: sprawdzono statusy, odnośniki i `git diff --check`, bez ponawiania
testów kodu.
