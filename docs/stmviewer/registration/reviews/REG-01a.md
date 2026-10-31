# REG-01a — karta odbioru

Status: **done**. Ręczny odbiór użytkownika zaliczony 2026-10-31 po wdrożeniu układu C.

Po uwagach użytkownika wdrożono wybrany układ C. Aktualne sprawdzenia i instrukcja:
[wdrożenie układu C](REG-01a-layout-c.md). Poniższy raport opisuje pierwszą
implementację; historyczne A/B oznaczają wynik zachowany i bieżący.
Data sprawdzeń: 2026-10-31, Linux, środowisko `netcat`.
Implementacja `846a479`, poprawki przeglądu `2276755`; baza `c5ec70a`.
Gałąź: `viewer/registration-difficult-movies`.

[Ticket](../issues/01a-manual-alignment.md) · [Instrukcja manualna](../manual-alignment-manual.md)

## Automatyczne sprawdzenia

- **14 nowych testów**: 7 modelu oraz 7 GUI. Punkt startu, kroki, części
  ułamkowe, reset/odrzucenie, niezmienne A/B, pochodzenie, brak jakości,
  brak pokrycia, widok/warstwy/gamma/zoom, zmiana pary/import/usunięcie/zamknięcie,
  niedostępna metoda oraz blokada ręcznej edycji podczas zadania pełnej rejestracji.
- TDD: kolejne red→green dla modelu i brakujących operacji GUI. Wykryte na
  rzeczywistym oknie przycinanie czterech przycisków w wierszu odtworzono testem;
  układ 2×2 usuwa przewijanie poziome. Dalsze regresje sprawdzają istniejące
  publiczne zachowania; nie dopisywano zmian tylko po to, by uzyskać stan red.
- Po poprawkach przeglądu: **28 passed** dla nowych i wcześniejszych testów par.
- Cały Viewer na końcowym kodzie: **398 passed, 2 skipped in 63.41s (0:01:03)**.
- Pełne repozytorium, jedno wywołanie uruchomione dla `846a479`: **14 failed, 2184 passed, 16 skipped in 276.92s (0:04:36)**.
  Zestaw 14 błędów jest identyczny z wcześniejszym REG-01: 11 MolTrack/SAM2
  i 3 NanoTrack. Nie są zaliczeniem całego repozytorium; nowych aplikacyjnych
  błędów w zestawie nazw nie ma. Poprawki przeglądu sprawdzono osobnym zestawem
  par i całego Viewera, bez ponownego uruchamiania całego repo.
- Rzeczywisty eksport aligned MPP oraz AVI FFV1 z GUI przed/po zastosowaniu
  celowo innej ręcznej próby: ten sam obraz główny, te same ponownie odczytane
  próbki/geometria MPP i zdekodowane klatki AVI. Oryginały pozostają niezmienne.
- Mypy strict **38 plików**, Ruff, `git diff --check`: bez błędów.
  Największy zmieniony plik kodu: `pair_dialog.py`, **409 linii**; limit 1500 zachowany.
- Wzorzec ułamkowego startu: `tests/stmviewer/manual_pair_fixture.py`;
  jawnie syntetyczny backend daje (2.4, −1.25), nie jest próbą jakości Phase.

## Rzeczywiste GUI sterowane skryptem

Qt **xcb**, lokalne MOVIE_4/MOVIE_8: sześć stałych par z protokołu zaliczonych
funkcjonalnie (start od zera, kroki, zastosowanie B, przypięcie A, korekta/reset/
odrzucenie, przełączanie obrazów i A/B). SHA obu filmów przed/po jest niezmienione.
Na MOVIE_8 2→3 ECC zgłosił rzeczywisty błąd `OpenCV ECC translation refinement failed`;
następnie ręczny start i zastosowanie XY=(1, −1) były dostępne.
Ułamkowy wzorzec i końcowy układ panelu sprawdzono również w xcb; poziomy zakres
przewijania wynosi 0. Agent obejrzał zrzuty.

To automatyczna próba funkcji. Zadane ręczne XY nie oznacza poprawnego
fizycznego dryfu; nie oceniano jakości dopasowania rzeczywistych struktur.
Nie wykonywano ręcznej próby użytkownika, Windows ani VLC.
Artefakty poza Git: `data/registration-manual-pair-review/` — logi pytest,
raporty JSON, skrypty xcb i zrzuty.

Polecenia z katalogu repo, w środowisku `netcat`:

```bash
PYTHONDONTWRITEBYTECODE=1 QT_QPA_PLATFORM=offscreen OPENBLAS_NUM_THREADS=1 \
  PYTHONPATH=.:tests/stmviewer python -m pytest -q -p no:cacheprovider tests/stmviewer
python -m mypy --config-file stmviewer/mypy.ini --cache-dir /tmp/reg01a-mypy
PYTHONDONTWRITEBYTECODE=1 QT_QPA_PLATFORM=offscreen OPENBLAS_NUM_THREADS=1 \
  PYTHONPATH=.:tests/moltrack:tests/stmviewer python -m pytest -q \
  --import-mode=importlib -p no:cacheprovider
```

## Standards

Początkowo jedna uwaga obowiązkowa i jedna sugestia; **0 pozostałych uwag**.
Asercja oparta na `asdict` nie mogła wykryć zatrzymania zagnieżdżonej dataclass;
usunięto ją, zachowując test ograniczonego opisu i niezmienności prób.
Powielone instrukcje kroku i formatowanie szkicu przeniesiono do jednej metody
kontrolek. Niezależny przegląd potwierdził poprawki w `2276755`; brak nowych uwag.

## Spec

**0 potwierdzonych usterek** w `c5ec70a…846a479`. Zgodne kroki i kopia ułamków,
reset/odrzucenie, pochodzenie bez automatycznej jakości, niezmienne A/B,
renderowanie z oryginałów, cykl życia i ochrona pełnego aligned/eksportów.
Wyjaśniono zakres blokady: szkic blokuje automatyczne obliczenie **tej pary**;
zadanie pełnej rejestracji w głównym oknie czasowo blokuje ręczną edycję.
Opis kolejnej ręcznej próby obejmuje bezpośrednie źródło, bez łańcucha przodków.

Wynik po poprawkach: Standards 0 pozostałych uwag; Spec 0 usterek.

## Ręczny odbiór użytkownika

- Data / osoba: 2026-10-31, użytkownik; system niepodany.
- Potwierdzenie: „testy manualne ok”, po wdrożeniu układu C.
- Odebrany kod: `b7aaf37` i `a9a072f`; dokumentacja: `8574886`.
- Funkcja: odbiór zaakceptowany przez użytkownika.
- Szczegółowe kroki, dane oraz ocena XY i resztkowego tearingu nie zostały
  podane w potwierdzeniu; nie dopisujemy wyników poszczególnych prób.
- Decyzja: zamknąć REG-01a jako `done`.

Zależność REG-02 jest spełniona; późniejszą implementację i oczekujący odbiór
opisuje [karta REG-02](REG-02.md). Ręczne próby par nie podmieniają pełnego aligned;
zapis na dysk jest zakresem REG-07. Wspólne moduły i algorytmy nie były zmieniane.
