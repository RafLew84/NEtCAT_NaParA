# Integracja STM Viewer do main — 2026-11-03

Użytkownik zlecił zakończenie bieżących prac Viewera, scalenie worktree do
`main` i publikację na GitHub. Źródłem jest gałąź
`viewer/registration-difficult-movies`, commit
`8e417f84a52c9eff0aa4837a34ce60a2acef8b2b`, obejmujący też `viewer/start`.

## Zakres

- Poprzednie `origin/main`: `a36beaec09980c7d26bacaa5df2d00f47f32bdb2`.
  Jest przodkiem źródła; integracja zachowuje historię wszystkich commitów.
- Baza przygotowania dwóch aplikacji: `0e8bc5302384988f11f420c8e1af40e8d52f99dd`.
  Od tej bazy Viewer zmienia swój kod, testy i dokumentację. Wyjątkiem są trzy
  wcześniejsze dokumenty badawcze Domains z `1f28b63`.
- W stosunku do starego `main` dochodzi też odziedziczona historia istniejących
  aplikacji, w tym MolTrack. Aktywna implementacja z worktree `NEtCAT-domains`
  pozostaje na jego gałęzi; na `main` trafia szkielet Domains.
- Główne README opisuje teraz rzeczywiste funkcje i zależności Viewera.
  Zasady współpracy opisują publikację z sesji nadrzędnej.
- Lokalne modele, środowiska, paczka dystrybucyjna, dane i nieśledzone pliki
  sesji/prób pozostają poza tym scaleniem. Zależności modeli opisuje
  [instrukcja instalacji](installation-models.md).

## Sprawdzenia

Kod sprawdzono w głównym worktree po scaleniu źródła do `stm-next`.
Python 3.12.12 ze środowiska `netcat`; Qt w trybie offscreen.

```bash
QT_QPA_PLATFORM=offscreen PYTHONPATH=.:tests/moltrack:tests/stmviewer \
python -m pytest -q --import-mode=importlib -p no:cacheprovider
python -m mypy --config-file stmviewer/mypy.ini
```

Pełny przebieg: **2611 passed, 63 failed, 50 skipped** (295,40 s).
Z tego **STM Viewer: 872 passed, 38 skipped, bez awarii**.
50 błędów NanoTrack wynikało z braku lokalnego `data/MOVIE_3.MPP`.
Po skopiowaniu tego pliku z worktree Viewera powtórzono tylko dotknięte testy:
**47 passed, 1 failed, 2 skipped** (5,42 s). Plik pozostaje ignorowany przez Git.

Łączny wynik po zastąpieniu tych 50 rezultatów ponowną próbą:
**2658 passed, 14 failed, 52 skipped**. To połączenie pełnego przebiegu
i wąskiego powtórzenia, a nie drugi pełny przebieg. Pozostałe 14 identyfikatorów
błędów jest zgodnych z [raportem REG-15](registration/reviews/REG-15.md):
11 MolTrack/SAM2 i trzy NanoTrack. Na osobnej kopii bazy `0e8bc53` dodatkowo
odtworzono 13 z nich; scenariusz `test_edge_correction_and_resume_replace_suffix`
przeszedł osobno, choć zawodził w pełnym zestawie. Moduły tych aplikacji
i ich testy nie zmieniły się od tej bazy. Całe repo nie jest opisane jako zielone.

Logi i raporty JUnit tej integracji są lokalnie w
`/tmp/netcat-viewer-main-integration/`: `pytest-full`, `with-sample`, `baseline`.
Pierwsza próba bez `--import-mode=importlib` zatrzymała się na sześciu
kolizjach nazw modułów podczas zbierania testów; nie jest zaliczonym przebiegiem.

Mypy: **106 plików bez błędów**. W lokalnym `.venv` głównego worktree
zainstalowano `stmviewer/requirements-ecc.txt` i sprawdzono utworzenie okna,
pętlę zdarzeń oraz zakończenie aplikacji: kod wyjścia 0.

Dwa niezależne przeglądy skilla `code-review` objęły przypięty zakres
`a36beae..8e417f8`, instrukcje, mapy i wybrane miejsca integracji:
sesje, eksport, wykrywanie modeli, rejestrację oraz uruchamianie aplikacji.
**Standards: 0 uwag; Spec: 0 uwag blokujących.** Był to przegląd punktowy,
nie ponowny audyt wszystkich 408 odziedziczonych commitów.

## Granice weryfikacji

Automatyczny start Qt nie zastępuje ręcznego odbioru GUI. W tej integracji
nie powtarzano prób na Windows ani rzeczywistych modeli CPU/CUDA; ich
dotychczasowe wyniki i ograniczenia pozostają w [przekazaniu](handoff.md)
oraz [raporcie instalacji](installation-validation.md).

Zlecenie publikacji nie zmienia historycznych statusów ticketów ani nie
dodaje odłożonego zakresu, m.in. REG-15a/15b. Program przyjmuje STP/S94/MPP
i eksportuje MPP/AVI; nie deklarujemy zapisu STP/S94.
