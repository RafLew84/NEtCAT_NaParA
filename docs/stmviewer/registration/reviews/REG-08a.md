# REG-08a — karta wykonania i odbioru

Data: 2026-11-01. Status: **ready-for-review**; ręczny odbiór użytkownika oczekuje.
Baza przeglądu: `e12a79440b806a9f44c3fe5b112212052ae6ce29`.
Kod: `ae32f1d`; poprawki: `665a1ed`. Gałąź: `viewer/registration-difficult-movies`.

[Ticket](../issues/08a-window-graph.md), [instrukcja manualna](../window-graph-manual.md),
[rzeczywiste próby i ograniczenia](../window-graph-results.md).

## Standards

Niezależny przegląd: brak twardych naruszeń. Zakres aplikacji, podział modułów,
limity plików i publiczne granice testów zachowane. Jedna uwaga projektowa P3:
powielona reguła wspólnego rozmiaru piksela w grafie, rejestracji i AVI.
Usunięto duplikację przez `stmviewer/calibration.py`; wszyscy trzej odbiorcy
korzystają z tej samej reguły. Dotychczasowe testy geometrii i proporcji przechodzą.
Końcowy niezależny przegląd `ae32f1d..665a1ed`: **0 otwartych ustaleń Standards**.

## Spec

Niezależny przegląd: **0 ustaleń** dla `e12a794…ae32f1d`.
Sprawdzono znaki i kotwicę LS, równe wagi, okna 3/5, lokalne braki, komponenty,
mosty, ograniczony cache z pochodzeniem, podgląd na żądanie, separację aktywnego
filmu, anulowanie oraz wersjonowaną sesję. Nie stwierdzono braków ani rozszerzenia
zakresu. Ręczna ocena jakości pozostaje osobnym, niewykonanym odbiorem.
Końcowa kontrola delty `ae32f1d..665a1ed`: **0 nowych ustaleń**;
pełny zakres `e12a794…665a1ed` pozostaje zgodny ze specyfikacją.

## Testy automatyczne

Środowisko: lokalny `netcat`, Qt offscreen, `OPENBLAS_NUM_THREADS=1`.

- Pełny zestaw repozytorium uruchomiono raz: **2331 passed, 16 failed,
  16 skipped**, 279,45 s. W tej próbie STM Viewer: **545 passed, 2 failed,
  2 skipped**. Log `/tmp/reg08a-full-suite.log`, JUnit `/tmp/reg08a-full-suite.xml`.
- **Dwie nowe regresje naprawione:** uruchomienie programu bez SciPy albo
  scikit-image. Wczesne importy nowego grafu wymagały tych bibliotek przy starcie.
  Importy przeniesiono do obliczeń; pięć istniejących prób brakujących zależności
  oraz 28 testów silnika przeszło. Podgląd zapisanej sesji i pary bez biblioteki
  renderującej teraz pokazuje przyczynę, czyści nieaktualny obraz i zachowuje wyniki.
- **Pozostałe 14 błędów to dokładnie wcześniejszy zestaw** z
  `/tmp/stmviewer-session-full-suite.log`: 11 MolTrack/SAM2 oraz 3 NanoTrack.
  Nie usuwano ich w tej zmianie aplikacji; nie są nowymi regresjami REG-08a.
- Po wszystkich poprawkach uruchomiono **134 testy dotyczące zmiany: wszystkie
  przechodzą**, 6,05 s (`/tmp/reg08a-postfix-tests.log`). Obejmują graf, pomiary,
  sesję, GUI, zależności opcjonalne, rejestrację, geometrię/napisy AVI i dotychczasowe
  porównanie par oraz ręczne korekty. Pełnego zestawu repozytorium nie powtarzano;
  powtórzono zakres dotknięty poprawkami i oba wcześniej zawodzące przypadki.
- Strict mypy: **67 modułów bez błędów**. Ruff zmienionych plików i
  `git diff --check`: bez błędów. Największy zmieniony plik kodu:
  `ui/main_window.py`, **984 linie**, poniżej celu 1000 i limitu 1500.
- TDD: kolejne testy znanych XY, braków/topologii, cache i awarii, sesji oraz
  publicznego GUI. Atrapa jest wyłącznie na granicy zewnętrznego LoFTR/importów;
  solver, serializacja, zadania i akcje aplikacji pozostają rzeczywiste.

Pełny zestaw:

```bash
PYTHONDONTWRITEBYTECODE=1 QT_QPA_PLATFORM=offscreen OPENBLAS_NUM_THREADS=1 \
PYTHONPATH=.:tests/moltrack:tests/stmviewer python -m pytest --import-mode=importlib \
-q -p no:cacheprovider -o faulthandler_timeout=120 --junitxml=/tmp/reg08a-full-suite.xml
```

## Rzeczywisty model i materiały manualne

Po finalnej poprawce importów ponowiono wszystkie sześć obliczeń: wzorzec,
MOVIE_4 bez dwóch pierwszych klatek i pełne MOVIE_8, okna 3 oraz 5, lokalny Outdoor
na RTX 5090/CUDA. Każda sesja została zapisana/odczytana, wszystkie rastry obu
wariantów wyrenderowane. Pełne parametry, braki i pomiary zasobów są w raporcie.
Pięć dodatkowych sesji o zadanych pomiarach obejmuje m.in. brak z obejściem,
most, rozłączenie i spójny fałszywy alias. Wyniki są tymczasowo w `/tmp`.

Zrzuty Qt offscreen obejrzano pod kątem układu, nazw i dostępności kontrolek.
To automatyczne sprawdzenie prezentacji, nie ręczny odbiór programu ani jakości.

## Odbiór manualny

**Niewykonany.** Użytkownik ma ocenić jakość na obu filmach oraz przepływ opisany
w instrukcji. Windows 11, stanowisko GPU 8 GB i VLC nie były sprawdzane w tym
etapie. Obecny eksport pozostaje aktywnym aligned; eksport kandydata jest poza
zakresem REG-08a. REG-08b nie może zastąpić odbioru tej funkcji.

Podsumowanie przeglądów: Standards — 0 naruszeń, 1 uwaga P3 usunięta;
Spec — 0 ustaleń. Brak pozostawionych usterek nowej funkcji w wykonanych sprawdzeniach.
