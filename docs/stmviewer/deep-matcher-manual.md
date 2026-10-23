# Próba ręczna — Deep Matcher z lokalnymi wagami (ticket 10)

Z katalogu `NEtCAT-viewer`, w środowisku `netcat`:

```bash
python -m stmviewer.main
```

Wybór **Deep Matcher** odsłania plik wag, urządzenie **Auto/CPU/CUDA**
i przycisk **Sprawdź model**. Import bibliotek, ładowanie oraz sprawdzanie
modelu pracują w tle. Sam wybór pliku jest wstępnym sprawdzeniem — do momentu
załadowania panel podaje „Model niesprawdzony”. Rejestruj również sprawdza
model, więc osobne naciśnięcie Sprawdź model nie jest wymagane.

## Lokalne wagi i dane

W tym środowisku znaleziono i sprawdzono plik:

```text
/home/rlew/projekty/tracker-import-20261008/trackers-windows-20261008/model_cache/torch/hub/checkpoints/loftr_outdoor.ckpt
```

Rozmiar: 46 341 978 bajtów. SHA-256 użytej kopii:
`21f5bec5968178e8bc8b7633441836fe5de4f47d861dd2cd7dc38e271b0479ec`.
Model zawiera 11 561 456 parametrów. Plik pozostaje poza Git, nie jest kopiowany
ani modyfikowany przez aplikację. Na innym komputerze wskaż własną lokalizację.

Wagi outdoor wskazane w [kodzie Kornia 0.8.2](https://github.com/kornia/kornia/blob/v0.8.2/kornia/feature/loftr/loftr.py)
można przygotować poza aplikacją, pobierając [plik LoFTR outdoor](http://cmp.felk.cvut.cz/~mishkdmy/models/loftr_outdoor.ckpt)
lub przenosząc istniejącą kopię. W aplikacji używamy `LoFTR(pretrained=None)`
i odczytu wskazanego pliku; nie uruchamiamy pobierania przez `pretrained="outdoor"`.
Oczekiwany format to checkpoint ze słownikiem `state_dict` zgodnym z tym modelem.
Odczyt używa `weights_only=True` i ścisłego sprawdzenia zgodności parametrów.

Opcjonalnie ustaw ścieżkę przed uruchomieniem, aby od razu wypełnić pole:

```bash
STMVIEWER_LOFTR_WEIGHTS=/sciezka/do/loftr_outdoor.ckpt python -m stmviewer.main
```

```powershell
$env:STMVIEWER_LOFTR_WEIGHTS = "C:\modele\loftr_outdoor.ckpt"
python -m stmviewer.main
```

Domyślnie pole jest puste. Program nie wyszukuje ani nie pobiera wag.
Plik i urządzenie są zapamiętane dla bieżącego zadania. Zmiana wyboru nie
modyfikuje starego aligned; opis wyniku nadal pokazuje faktycznie użyte urządzenie.
Sprawdzenie modelu nie zmienia obrazu. Rejestruj ładuje plik ponownie, także po
udanej próbie sprawdzenia, aby nie używać nieaktualnych wag.

Dane do próby:

- `tests/stmviewer/fixtures/registration/cpu.mpp`: 3 klatki 80 × 80,
  znane przesunięcia XY (0,0), (2,−1), (−1,1). Generator:
  `python tests/stmviewer/make_cpu_registration_fixtures.py`.
- `tests/stmviewer/fixtures/registration/invalid-loftr.txt`: celowo błędny plik,
  nie jest modelem; wybierz filtr **Wszystkie pliki** w dialogu wag.
- `data/MOVIE_3.MPP`: 17 klatek pomiarowych, do dłuższej próby i anulowania.
  Można też użyć dłuższego `data/TTMAPP/MOVIE_23raw_TTMAPP_I_AU111.MPP`.

## Kroki i oczekiwane wyniki

1. Otwórz `cpu.mpp`, wykonaj Phase, powiększ obraz. Wybierz Deep Matcher,
   pozostawiając puste pole wag: widać przyczynę niedostępności, przyciski
   Rejestruj i Sprawdź model są nieaktywne. Poprzedni wynik pozostaje.
2. Przez **Wybierz wagi…** wskaż lokalny plik, wybierz **CPU** i naciśnij
   **Sprawdź model**. Widać postęp i możliwość anulowania. Po sukcesie panel
   podaje „Sprawdzono model. Urządzenie: CPU”; dotychczasowy aligned się nie zmienia.
   Sprawdzenie można też wykonać przed otwarciem serii.
3. Wybierz klatkę 2 i kliknij **Rejestruj**. Po sukcesie widok aligned jest
   dopasowany, gamma zachowana, a opis wyniku podaje Deep Matcher i CPU.
   Na sprawdzonym wzorcu ΔX ≈ 1,955 px, ΔY ≈ −1,072 px, obszar 83 × 83 px.
   Przejdź przez klatki: znaczniki powinny pozostać w zbliżonym miejscu;
   test automatyczny dopuszcza błąd do 0,75 px względem znanych przesunięć.
4. Powtórz z **CUDA**, a następnie **Auto**. Przy działającym CUDA opis podaje
   numer i nazwę GPU. Na stanowisku próby: `CUDA:0 — NVIDIA GeForce RTX 5090`.
   Jawny wybór CUDA przy niedostępności kończy się błędem, zachowując stary wynik.
   Auto wybiera CPU, gdy Torch zgłasza brak CUDA, i jawnie to pokazuje.
   Błąd uruchomienia dostępnego CUDA nie powoduje ponowienia na CPU.
5. Zmień listę metod lub urządzenie po uzyskaniu wyniku. Obraz, przesunięcia
   i opis urządzenia starego aligned pozostają. Następna próba dopiero może je
   zastąpić. Original/aligned zachowują osobne kadry, a usuwanie klatki zachowuje
   dopasowanie i urządzenie pozostałych obrazów.
6. Przy istniejącym wyniku wskaż `invalid-loftr.txt` i uruchom Sprawdź model
   albo Rejestruj. Czytelny błąd wag nie usuwa wyniku. Przywróć prawidłowy plik:
   ponowne sprawdzenie oraz rejestracja powinny działać.
7. Otwórz MOVIE_3 i uzyskaj aligned. Ponów rejestrację Deep Matcher, po czym
   kliknij **Anuluj rejestrację**. Na szybkim komputerze użyj dłuższej serii.
   W trakcie pracy zmień oglądaną klatkę, gamma i zoom. Po anulowaniu zostaje
   poprzedni wynik wraz z bieżącym kadrem; nie jest publikowany częściowy aligned.
   Otwarcie innej serii, usuwanie, Play i ustawienia modelu są w tym czasie
   zablokowane. Zamknięcie okna najpierw anuluje i czeka na koniec bieżącego kroku.

Dopasowanie nadal jest jedną translacją XY na klatkę, z domyślnymi progami
NanoTrack. Klatki są dopasowywane do poprzednich oryginałów i odnoszone do
pierwszej klatki serii. Model jest używany ponownie dla kolejnych par tej samej
próby. Niska pewność pozostaje oznaczona; metoda nie gwarantuje poprawnego
fizycznie wyniku na każdym pomiarze. LoFTR nie zmienia rozdzielczości wejść;
nieobsługiwany rozmiar/za mało dopasowań jest błędem próby, bez zmiany algorytmu.

## Przygotowanie zależności poza aplikacją

Python 3.12, podstawowe środowisko według [README](README.md#uruchomienie).
W przygotowanym netcat nie trzeba nic instalować. Dla nowego środowiska
wybierz jeden wariant Torch. [Oficjalne instrukcje PyTorch 2.9.1](https://pytorch.org/get-started/previous-versions/#v291)
podają indeksy CPU oraz CUDA 12.8 dla Linuksa i Windows.

W aktywnym środowisku Ubuntu 24.04 lub Windows 11:

```bash
# Wariant CPU
python -m pip install torch==2.9.1 --index-url https://download.pytorch.org/whl/cpu
python -m pip install -r stmviewer/requirements-deep.txt
```

Albo na stanowisku NVIDIA z odpowiednim sterownikiem:

```bash
# Wariant CUDA 12.8
python -m pip install torch==2.9.1 --index-url https://download.pytorch.org/whl/cu128
python -m pip install -r stmviewer/requirements-deep.txt
```

Zestaw przypina Torch 2.9.1, Kornia 0.8.2 i kornia_rs 0.1.10. Polecenia dotyczą
wybranego lokalnego środowiska, nie aktualizacji wspólnego stosu repozytorium.
Do odtworzenia CUDA potrzebny jest wariant binarny Torch i działający sterownik;
sama nazwa GPU nie wystarcza. Przed próbą aplikacji sprawdź rzeczywiste wykonanie:

```bash
python -c "import torch; print(torch.__version__, torch.version.cuda, torch.cuda.is_available()); print((torch.ones(2, device='cuda') + 1).cpu())"
```

Gdy nie ma bibliotek, program nadal uruchamia się i przegląda obrazy;
Deep Matcher podaje powód. Obecność modułu i pliku jest jedynie wstępną
kontrolą. Uszkodzona instalacja, niezgodne wagi lub błąd CUDA zostaną zgłoszone
przez Sprawdź model/Rejestruj. Po zmianach instalacji uruchom program ponownie.

## Rozdzielenie prób

Testy kontrolowane używają prawdziwego Torch do odczytu małego checkpointu
oraz algorytmu konsensusu NanoTrack, lecz zastępują model Kornia. To test
integracji i obsługi błędów, nie potwierdzenie rzeczywistych wag.
Osobny test rzeczywistego LoFTR uruchomisz po wskazaniu istniejącego pliku:

```bash
STMVIEWER_TEST_LOFTR_WEIGHTS=/sciezka/do/loftr_outdoor.ckpt QT_QPA_PLATFORM=offscreen python -m pytest -q tests/stmviewer/test_deep_registration_real.py
```

```powershell
$env:STMVIEWER_TEST_LOFTR_WEIGHTS = "C:\modele\loftr_outdoor.ckpt"
$env:QT_QPA_PLATFORM = "offscreen"
python -m pytest -q tests/stmviewer/test_deep_registration_real.py
```

Bez ścieżki te dwie próby są jawnie pomijane. Wykonano je w netcat na CPU
oraz CUDA — obie przeszły, przy zablokowanych funkcjach pobierania.
Automatyczna próba prawdziwego GUI Qt xcb potwierdziła brak wag, wybór pliku,
sprawdzanie modelu, CPU/CUDA/Auto, błędny plik, rzeczywiste anulowanie i pełne
17 klatek MOVIE_3 (obszar 312 × 291 px). Źródła i wagi zachowały SHA-256.
Obejrzano zrzuty. To próby automatyczne; odbiór manualny użytkownika oraz
Windows pozostają niewykonane. Szczegóły: [przekazanie](handoff.md).
