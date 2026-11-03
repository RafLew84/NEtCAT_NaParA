# Opcjonalne modele rejestracji — instalacja

Ta część jest potrzebna dopiero dla Deep Matchera, LightGlue,
EfficientLoFTR, MatchAnything lub RoMa. Najpierw uruchom
[podstawowy program](installation.md). AKAZE nie wymaga modelu ani wag.

**Biblioteki** instaluje pip. **Wagi** to osobne pliki wyuczonego modelu.
Niektóre metody potrzebują również folderu kodu autorów. Program nie pobiera
tych elementów podczas obliczeń.

## 1. Przygotuj Torch: wybierz CPU albo GPU

Zamknij STM Viewer. Otwórz terminal / Miniforge Prompt, aktywuj środowisko
i przejdź do folderu programu zgodnie z instrukcją podstawową.

### Bez karty NVIDIA — CPU

~~~text
conda activate stmviewer
python -m pip install "torch>=2.9,<3" "torchvision>=0.24,<1" --index-url https://download.pytorch.org/whl/cpu
~~~

Obliczenia modeli będą działać na procesorze; na dużych filmach mogą trwać długo.

### Z kartą NVIDIA — CUDA

Na [oficjalnej stronie PyTorch](https://pytorch.org/get-started/locally/)
wybierz **Stable**, swój system, **Pip**, **Python** i wariant **CUDA**
zgodny z kartą oraz sterownikiem. Użyj wskazanego tam polecenia w aktywnym
środowisku; początkowe `pip` / `pip3` można zastąpić `python -m pip`.
Dobieraj Torch i torchvision razem. Viewer deklaruje Torch 2.9 lub nowszy
z rodziny 2; dla RoMa osobny zestaw zaczyna się od 2.11.

Nie kopiuj numeru CUDA tylko dlatego, że był użyty na innym komputerze.
W razie wątpliwości dobór wariantu dla karty zleć opiekunowi stanowiska.
Samo zainstalowanie pakietu o nazwie `torch` nie potwierdza obsługi GPU.

Sprawdź instalację:

~~~text
python -c "import torch; print('Torch:', torch.__version__); print('CUDA:', torch.version.cuda); print('GPU dostepne:', torch.cuda.is_available())"
~~~

Dla wybranego GPU ostatnia wartość powinna być `True`.
Dodatkowa krótka próba wykonania:

~~~text
python -c "import torch; print((torch.ones(2, device='cuda') + 1).cpu())"
~~~

Oczekiwany wynik zawiera dwie wartości 2. Dla instalacji CPU pomiń
drugie polecenie; `GPU dostepne: False` jest wtedy prawidłowe.
Dobór platformy i binariów opiera się na [instrukcji PyTorch](https://pytorch.org/get-started/locally/).

## 2. Doinstaluj tylko wybrane metody

Polecenia wykonuj w środowisku `stmviewer`, z folderu repozytorium:

| Metoda | Polecenie |
| --- | --- |
| Deep Matcher i jego warianty | `python -m pip install -r stmviewer/requirements-deep.txt` |
| LightGlue + SuperPoint | `python -m pip install -r stmviewer/requirements-lightglue.txt` |
| EfficientLoFTR | `python -m pip install -r stmviewer/requirements-efficient.txt` |
| MatchAnything-ELoFTR | `python -m pip install -r stmviewer/requirements-matchanything.txt` |

Każda lista dołącza potrzebny zestaw podstawowy. Nie używaj `--upgrade`
bez potrzeby: zgodny zainstalowany Torch może zostać zachowany.
Na końcu wykonaj `python -m pip check` i powtórz próbę GPU, jeśli go używasz.
Uruchom program ponownie po instalowaniu bibliotek.

## 3. Skąd wziąć pliki modeli i gdzie je wskazać

Najłatwiejsza jest [paczka programu i modeli](distribution.md) od opiekuna.
Rozpakuj ją np. do Dokumentów i zachowaj folder `models` obok `stmviewer`.
Program sam uzupełni ścieżki modeli. Jeśli przechowujesz je osobno,
wskaż je ręcznie według tabeli. Zachowaj licencje i strukturę katalogów;
nie wskazuj archiwum ZIP zamiast rozpakowanego folderu.

| Metoda | Pliki do wskazania w aplikacji |
| --- | --- |
| Deep Matcher / Deep + ECC / Deep + lokalne fragmenty | `loftr_outdoor.ckpt` |
| LightGlue + SuperPoint | kod z podfolderem `lightglue`; `superpoint_lightglue.pth`; osobno `superpoint_v1.pth` |
| EfficientLoFTR | kod z `src/loftr`; `eloftr_outdoor.ckpt` |
| MatchAnything-ELoFTR | kod MatchAnything z `src/loftr`; `matchanything_eloftr.ckpt` |
| RoMa v2 | kod DINOv3 z `hubconf.py` i `dinov3`; `romav2.0.1.pt`; Python osobnego środowiska |

Jeśli pola nie zostały uzupełnione automatycznie, po wybraniu metody użyj **Wybierz wagi…**,
**Wybierz katalog kodu…**, a w LightGlue również **Wybierz wagi SuperPoint…**.
Wskaż katalog zawierający wymieniony podfolder, nie sam podfolder.
Wybierz CPU/CUDA/Auto i kliknij **Sprawdź model**.

Po sukcesie otwórz mały film i sprawdź **Porównaj parę…**.
Dopiero potem uruchom cały film. Auto wybiera GPU, jeśli Torch widzi CUDA;
jawne CUDA nie przełącza się po cichu na CPU przy błędzie.

### Dla osoby przygotowującej paczkę modeli

Biblioteki mają zakresy, ale adaptery nadal sprawdzają zgodny kod i wagi.
Nie wystarczy dowolny plik o podobnej nazwie.

| Zasób | Źródło zgodnego wydania |
| --- | --- |
| LoFTR outdoor | [Adres wag używany przez Kornia](http://cmp.felk.cvut.cz/~mishkdmy/models/loftr_outdoor.ckpt) |
| LightGlue | [Kod 5a650c4](https://github.com/cvg/LightGlue/tree/5a650c444718caffc2669dc0094cde908f42dd73), [wydanie z wagami v0.1_arxiv](https://github.com/cvg/LightGlue/releases/tag/v0.1_arxiv) |
| EfficientLoFTR | [Kod 07e9c14](https://github.com/zju3dv/EfficientLoFTR/tree/07e9c1401e71e9c556b1fda9d86d060af36ba176), [plik outdoor](https://drive.google.com/file/d/1jFy2JbMKlIp82541TakhQPaoyB5qDeic/view) |
| MatchAnything | [Kod z demonstratora](https://huggingface.co/spaces/LittleFrog/MatchAnything/tree/6a7bcb589ec8da3a9e861e799122beaa5eba2193/imcui/third_party/MatchAnything), [archiwum wag](https://drive.google.com/file/d/12L3g9-w8rR9K2L4rYaGaDJ7NqX1D713d/view) |
| RoMa | [Wagi 2.0.1](https://github.com/Parskatt/RoMaV2/releases/download/v2.0.1/romav2.0.1.pt), [DINOv3 adc2544](https://github.com/facebookresearch/dinov3/tree/adc254450203739c8149213a7a69d8d905b4fcfa) |

Dla kodu zachowaj oryginalne zakończenia linii; zmiana LF na CRLF
przez Git na Windows zmienia sumę kontrolną. Pobranie archiwum właściwej
rewizji i rozpakowanie jej bez edytowania plików tego unika.
Nie instaluj całych zależności treningowych repozytoriów modeli;
użyj list Viewera z poprzedniej tabeli. Te adresy identyfikują zasoby użyte
przez adaptery, nie listę najnowszych modeli.

## 4. RoMa v2 — osobne środowisko

Aplikacja pozostaje w `stmviewer` (lub Twoim dotychczasowym `netcat`).
RoMa uruchamia się jako osobny proces. Nie instaluj jej listy zależności
do głównego środowiska.

Z folderu repozytorium:

~~~text
conda create -n stmviewer-roma python=3.12 pip
conda activate stmviewer-roma
~~~

Zainstaluj parę Torch/torchvision wybraną według kroku 1,
z Torch co najmniej 2.11 i torchvision co najmniej 0.26.
Następnie:

~~~text
python -m pip install -r stmviewer/requirements-roma-worker.txt
python -m pip check
python -c "import sys; print(sys.executable)"
~~~

Po ponownym uruchomieniu głównego programu pole **Python środowiska RoMa**
powinno wskazać wykryte środowisko `stmviewer-roma`. Jeśli go nie wykryło,
skopiuj ostatnią ścieżkę i wybierz dokładnie ten plik `python` / `python.exe`.
Wagi i folder DINOv3 są wykrywane w paczce; w innym układzie wskaż je
według tabeli. Zacznij od wariantu **Turbo**.

Na Linux RoMa zależy od skompilowanego `fused-local-corr`.
Jego wydanie musi pasować do Torch/CUDA; sam pomyślny `pip check` nie
sprawdza wykonania rozszerzenia na GPU. Zależności tego pakietu mogą
narzucić dokładną wersję Torch mimo luźniejszej listy Viewera.
Nie obchodź ich przez `--no-deps`. W razie błędu kompilacji lub ładowania
potrzebny jest dobór zgodnej pary przez opiekuna środowiska.
Opis projektu: [RoMa v2](https://pypi.org/project/romav2/2.0.1/).

Wymaganie `romav2==2.0.1` pozostaje celowo ścisłe, ponieważ adapter
sprawdza wersję i sumę kodu tego konkretnego modelu.
Ogólne biblioteki mają zakresy. Nie oznacza to przetestowania każdej
kombinacji; zawsze wykonaj **Sprawdź model** w wybranym urządzeniu.

Wróć do głównego środowiska przed uruchomieniem GUI:

~~~text
conda activate stmviewer
python -m stmviewer.main
~~~

Dla dotychczasowej instalacji użyj `conda activate netcat`.
Nie trzeba ręcznie aktywować środowiska RoMa przed każdym obliczeniem;
program uruchomi wskazany interpreter.

## 5. Typowe problemy z modelami

| Objaw | Znaczenie / działanie |
| --- | --- |
| Niezgodna suma kodu albo wag | Nie ta rewizja, zmienione pliki lub niepełne pobranie. Wskaż zgodną paczkę; zmiana progu w GUI tego nie naprawi. |
| CUDA niedostępna | Sprawdź środowisko, wariant Torch i sterownik. Dla RoMa sprawdzaj jej osobne środowisko. |
| Za mało pamięci GPU | Spróbuj CPU; w RoMa mniejszego wariantu. Zamknij inne obliczenia zajmujące GPU. |
| Sprawdzenie modelu działa, ale para jest odrzucana | To może być problem treści obrazu lub parametrów, a nie instalacji. Obejrzyj diagnostykę i porównaj inną metodę. |
| Sesja z innego komputera się otwiera, ale model nie startuje | Obrazy są w sesji, modele nie. Popraw lokalne ścieżki i sprawdź model ponownie. |

Przykładowe lokalizacje `/home/rlew/...` w historycznych raportach są
ścieżkami stanowiska deweloperskiego. Nie wpisuj ich na innym komputerze.
Wybieraj rzeczywiste pliki na swoim dysku.
