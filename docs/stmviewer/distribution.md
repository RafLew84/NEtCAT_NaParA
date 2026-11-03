# Paczka do przekazania użytkownikom

Paczka ZIP zawiera jeden folder **NEtCAT**. Rozpakuj go w wybranej
lokalizacji, np. `C:\NEtCAT` na Windows lub `~/NEtCAT` na Ubuntu.
Otwórz **Instrukcja.html**; instalację wykonuj z folderu NEtCAT.

## Co zawiera ZIP

| Element | Lokalizacja w folderze NEtCAT |
| --- | --- |
| Program STM Viewer | `stmviewer` |
| Potrzebne czytniki i algorytmy wspólne | `napara`, `nanotrack` — nie usuwaj tych folderów |
| Małe dane do pierwszej próby | `tests/stmviewer/fixtures` |
| Instrukcje i wymagania bibliotek | `Instrukcja.html`, `docs/stmviewer` i `stmviewer/requirements*.txt` |
| Wagi i kod modeli | `models` |
| Lista plików, SHA-256 i wersje źródeł | `manifest.json` |

Są tu pliki modeli potrzebne do wszystkich obecnych metod rejestracji.
Nie ma danych pomiarowych autora, jego sesji ani gotowych środowisk Python.
Biblioteki i sterownik GPU należy przygotować na komputerze odbiorcy.
Nie jest to instalator EXE ani całkowicie offline'owy instalator zależności.

Zachowaj licencję programu i dołączone licencje modeli. Kod modeli i pliki
wag pozostaw w otrzymanej postaci: ich zgodność jest sprawdzana przy ładowaniu.

## Jak wskazać modele z paczki

**Program nie wyszukuje automatycznie modeli w folderze `models`.**
Po wybraniu metody użyj przycisków wyboru wag i kodu.
Poniższe ścieżki są względem rozpakowanego NEtCAT:

| Metoda | Wagi | Katalog kodu |
| --- | --- | --- |
| Deep Matcher, Deep + ECC, Deep + lokalne fragmenty | `models/loftr/weights/loftr_outdoor.ckpt` | Nie wybierasz folderu; kod dostarcza instalowana Kornia |
| EfficientLoFTR | `models/efficientloftr/weights/eloftr_outdoor.ckpt` | `models/efficientloftr/source` |
| LightGlue + SuperPoint | `models/lightglue/weights/superpoint_lightglue.pth` oraz osobno `superpoint_v1.pth` w tym samym folderze | `models/lightglue/source` |
| MatchAnything-ELoFTR | `models/matchanything/weights/matchanything_eloftr.ckpt` | `models/matchanything/source` |
| RoMa v2 | `models/romav2/weights/romav2.0.1.pt` | `models/romav2/dinov3` |

AKAZE, Phase, korelacja bez normalizacji, Tile+RANSAC, ECC i Optical Flow
nie potrzebują osobnych wag. Po podstawowej instalacji można ich używać.

Dla RoMa wskaż również **Python środowiska RoMa**. Jego ścieżkę uzyskasz
poleceniem `python -c "import sys; print(sys.executable)"` wykonanym
w osobnym środowisku RoMa. Instrukcja utworzenia tego środowiska jest
w rozdziale [Opcjonalne modele](installation-models.md).

W paczce znajduje się kod pakietu RoMa w postaci koła instalacyjnego.
Po aktywowaniu środowiska **stmviewer-roma**, z folderu NEtCAT:

~~~text
python -m pip install models/romav2/romav2-2.0.1-py3-none-any.whl -r stmviewer/requirements-roma-worker.txt
~~~

Najpierw dobierz wariant Torch CPU/CUDA zgodnie z instrukcją modeli.
To polecenie może pobrać pozostałe zależności; sama paczka nie zawiera Torch.
Nie instaluj RoMa do głównego środowiska aplikacji.

Po wskazaniu plików kliknij **Sprawdź model**, a następnie wypróbuj jedną
parę klatek. Zapisy sesji zachowują konfigurację pracy i ścieżki modeli;
po przeniesieniu sesji na inny komputer może być konieczne ich poprawienie.

## Skąd biorą się domyślne ścieżki

Aplikacja wypełnia pola znanymi adresami, ale nie skanuje katalogów i dysków.

| Metoda | Wartości początkowe |
| --- | --- |
| Deep Matcher i warianty Deep | Puste pole albo plik ze zmiennej środowiskowej `STMVIEWER_LOFTR_WEIGHTS` |
| EfficientLoFTR | `~/.cache/stmviewer/efficientloftr/source` oraz `weights/eloftr_outdoor.ckpt` w tym katalogu modelu |
| LightGlue + SuperPoint | `~/.cache/stmviewer/lightglue/source` oraz oba pliki w `weights` |
| MatchAnything | `~/.cache/stmviewer/matchanything/source` oraz `weights/matchanything_eloftr.ckpt` |
| RoMa v2 | `~/.cache/stmviewer/romav2/dinov3` oraz `weights/romav2.0.1.pt` |

`~` oznacza katalog domowy użytkownika, np. `/home/anna` na Ubuntu
lub `C:\Users\Anna` na Windows. Na Windows aplikacja także używa podfolderu
`.cache\stmviewer`, nie przeszukuje AppData.

Domyślny Python RoMa wskazuje `~/miniconda3/envs/netcat-romav2/bin/python`
na Linux, a na Windows `~/miniconda3/envs/netcat-romav2/python.exe`.
To konkretna propozycja ścieżki, nie wykrywanie środowisk conda.
Przy użyciu Miniforge i nazwy `stmviewer-roma` z instrukcji musisz wskazać
właściwy interpreter samodzielnie.

Można ręcznie umieścić cztery katalogi modeli w `~/.cache/stmviewer`,
zachowując układ `source`/`weights` lub `dinov3`/`weights`. Wtedy domyślne
pola do nich trafią. Prostszą drogą dla tej paczki jest jednak pozostawienie
wszystkiego w `NEtCAT/models` i wybranie plików w GUI.
Przekopiowanie wag nie instaluje bibliotek i nie tworzy środowiska RoMa.
