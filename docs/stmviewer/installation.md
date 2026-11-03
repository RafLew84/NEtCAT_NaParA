# Instalacja STM Viewer — krok po kroku

Instrukcja dla Ubuntu 24.04 i Windows 11, komputerów Intel/AMD 64-bit.
Stan programu: 3 listopada 2026. Zacznij od instalacji podstawowej; pozwala
oglądać i wyrównywać filmy oraz zapisywać wyniki. Modele neuronowe można
dołączyć później według [osobnej instrukcji](installation-models.md).

## Co będzie potrzebne

- Paczka STM Viewer lub całe repozytorium, rozpakowane do zwykłego folderu.
- Internet podczas instalacji. Podstawowy program później działa lokalnie.
- Dla dużych serii: SSD i około 16 GB **wolnego** RAM. Małe filmy można
  otworzyć na słabszym komputerze.
- Karta NVIDIA nie jest potrzebna do podstawowej instalacji.
  Dla modeli na GPU przyjmujemy co najmniej 8 GB VRAM; wymagania konkretnego
  modelu i rozmiaru filmu mogą być większe.

**Repozytorium** oznacza folder z kodem programu. **Środowisko** to osobny
zestaw Pythona i bibliotek, przygotowany dla tej aplikacji. Utworzymy
środowisko o nazwie `stmviewer`, aby nie zmieniać innych programów na komputerze.

Jeżeli masz już działający program w środowisku `netcat`, nie musisz
instalować go ponownie. Do uruchomienia wystarcza aktywowanie `netcat`
zamiast `stmviewer` i przejście do folderu repozytorium.

## 1. Przygotuj folder programu

Najprościej otrzymać od opiekuna projektu [paczkę ZIP programu i modeli](distribution.md).
Zawiera potrzebne części repozytorium oraz wagi; nie trzeba ich pobierać osobno. Jeśli pobierasz je przez GitHub, wybierz
właściwą gałąź, potem **Code → Download ZIP**. Domyślna gałąź może nie
zawierać bieżących funkcji; tę instrukcję przygotowano na
`viewer/registration-difficult-movies`.

W menedżerze plików wybierz **Wyodrębnij wszystko…** / **Rozpakuj**.
Nie uruchamiaj programu z wnętrza ZIP-a. Nazwij rozpakowany folder `NEtCAT`.
W jego środku powinny znajdować się m.in. foldery:

- `stmviewer`
- `napara`
- `nanotrack`
- `tests`
- `docs`

Potrzebne są również pliki repozytorium leżące obok tych folderów.
Samo skopiowanie `stmviewer` nie wystarczy. Przykładowe lokalizacje:

| System | Folder programu |
| --- | --- |
| Windows | `C:\NEtCAT` albo inny folder, w którym możesz zapisywać |
| Ubuntu | `NEtCAT` w katalogu domowym, czyli `~/NEtCAT` |

Możesz wybrać inną lokalizację. Wtedy w poleceniach `cd` poniżej wstaw
własną ścieżkę, zachowując cudzysłowy.

## 2. Przygotuj Miniforge

Miniforge udostępnia Pythona i polecenie `conda`.
Jeśli masz już działającą Minicondę/Anacondę/Miniforge, pomiń instalator.

### Windows

1. Na [oficjalnej stronie Miniforge](https://github.com/conda-forge/miniforge)
   pobierz **Miniforge3-Windows-x86_64.exe**.
2. Uruchom plik; wybierz instalację **Just Me** i folder dla swojego konta.
   Pozostaw dodawanie do PATH wyłączone.
3. Po instalacji otwórz menu Start i wyszukaj **Miniforge Prompt**.
   Dalsze polecenia wpisuj w tym oknie.

### Ubuntu

1. Z tej samej [strony Miniforge](https://github.com/conda-forge/miniforge)
   pobierz **Miniforge3-Linux-x86_64.sh**.
2. Otwórz folder z pobranym plikiem. Kliknij tło prawym przyciskiem
   i wybierz **Otwórz w terminalu**.
3. Wpisz:

~~~bash
bash Miniforge3-Linux-x86_64.sh
~~~

4. Przejdź przez licencję, zaakceptuj ją po przeczytaniu, pozostaw
   domyślny folder instalacji. Na pytanie o inicjalizację conda odpowiedz `yes`.
5. Zamknij terminal i otwórz nowy: **Ctrl+Alt+T**.

To procedura oparta na instrukcji autorów Miniforge, bez przypinania
wydania instalatora.

## 3. Jak wklejać polecenia

Każdy wiersz to jedno polecenie. Wklej je i naciśnij **Enter**.
Czekaj na zakończenie, zanim przejdziesz dalej.

- Ubuntu: wklejanie przez **Ctrl+Shift+V**.
- Windows Miniforge Prompt: zwykle **Ctrl+V** lub prawy przycisk myszy.
- Nie przepisuj tekstu `(base)`, `(stmviewer)`, znaku `>` ani znaku `$`
  z przykładów ekranu. To fragmenty wyglądu terminala.
- Jeżeli zobaczysz `>>>`, jesteś w konsoli Pythona. Wpisz `exit()` i Enter,
  aby wrócić do terminala.
- Po uruchomieniu programu terminal pozostaje zajęty do zamknięcia jego
  okna. To prawidłowe zachowanie.

## 4. Utwórz środowisko — tylko przy pierwszej instalacji

W terminalu / Miniforge Prompt:

~~~text
conda create -n stmviewer python=3.12 pip
~~~

Gdy pojawi się pytanie `Proceed ([y]/n)?`, wpisz `y` i Enter.
Potem:

~~~text
conda activate stmviewer
~~~

Na początku wiersza powinno pojawić się `(stmviewer)`.
Python 3.12 to sprawdzony punkt startu, z dowolną aktualizacją poprawkową;
nie jest to wymaganie jednej konkretnej wersji wszystkich bibliotek.
Inne wydania Pythona wymagają sprawdzenia także wybranych modeli.
Tworzenie i aktywację opisuje [dokumentacja conda](https://docs.conda.io/projects/conda/en/latest/user-guide/tasks/manage-environments.html).

Jeżeli środowisko `stmviewer` już istnieje, użyj tylko `conda activate stmviewer`.
Nie twórz go ponownie.

## 5. Przejdź do folderu programu

**Windows, w Miniforge Prompt:**

~~~bat
cd /d "C:\NEtCAT"
~~~

**Ubuntu:**

~~~bash
cd "$HOME/NEtCAT"
~~~

Własną ścieżkę możesz skopiować z paska adresu menedżera plików.
W Ubuntu kliknij ten pasek lub użyj Ctrl+L. W Windows
`cd /d` zmienia również dysk, np. z C: na D:.

## 6. Zainstaluj biblioteki

W aktywnym środowisku, z folderu programu:

~~~text
python -m pip install --upgrade pip
python -m pip install -r stmviewer/requirements-ecc.txt
python -m pip check
~~~

Plik o nazwie `requirements-ecc.txt` zawiera **cały zestaw podstawowy**:
interfejs, odczyt, sesje, Phase, korelację bez normalizacji,
Tile+RANSAC, ECC, Optical Flow, AKAZE i zapis AVI.
Nie trzeba osobno instalować `requirements.txt`.

Ostatnie polecenie powinno wypisać `No broken requirements found`.
Samo to sprawdza zależności pakietów; działanie okna sprawdzisz za chwilę.
Instalowanie z listy wymagań opisuje [dokumentacja pip](https://pip.pypa.io/en/stable/cli/pip_install/).

Nie instaluj osobno `PyQt6-Qt6`, `PyQt6-sip` ani kilku odmian OpenCV.
PyQt6 dobiera swoje komponenty, a ten zestaw używa `opencv-python`.
Odmiany OpenCV dzielą jeden moduł `cv2`, więc nie powinny współistnieć.
[Instrukcja autorów OpenCV](https://pypi.org/project/opencv-python/).

## 7. Pierwsze uruchomienie i krótka próba

~~~text
python -m stmviewer.main
~~~

Powinno pojawić się okno **STM Viewer**.

1. Kliknij **Otwórz STP/S94/MPP…**.
2. W folderze programu otwórz
   `tests/stmviewer/fixtures/registration/cpu.mpp`.
3. Kliknij **Play**, następnie **Pause**. Film ma trzy klatki.
4. Wybierz metodę **Phase** i kliknij **Rejestruj**.
5. Po zakończeniu wybierz `original` i `aligned`, porównując obrazy.
6. Kliknij **Zapisz sesję…**, zapisz plik w swoim folderze z wynikami,
   potem otwórz go przyciskiem **Otwórz sesję…**.

To kontrola instalacji na małym wzorcu. Nie jest oceną jakości dopasowania
Twoich pomiarów. Dalsze kroki opisuje [instrukcja obsługi](user-guide.md).

## 8. Następne uruchomienia

Instalację wykonujesz raz. Przy następnej pracy wystarczą trzy polecenia.

**Windows — otwórz Miniforge Prompt:**

~~~bat
conda activate stmviewer
cd /d "C:\NEtCAT"
python -m stmviewer.main
~~~

**Ubuntu — otwórz terminal:**

~~~bash
conda activate stmviewer
cd "$HOME/NEtCAT"
python -m stmviewer.main
~~~

Nie zamykaj terminala podczas pracy programu. Zakończ przez krzyżyk
okna STM Viewer albo **Plik → Zakończ**, a potem zamknij terminal.
Zapisz wcześniej sesję, jeżeli chcesz kontynuować tę pracę.

## 9. Co oznaczają poluzowane wersje

Listy bibliotek stosują zakresy, np. `PyQt6>=6.9,<7`.
Oznacza to wersję 6.9 lub nowszą z rodziny 6, zamiast jednej konkretnej
poprawki. Podobnie potraktowano biblioteki numeryczne, OpenCV i większość
zależności modeli. Instalator rozwiązuje ich wspólne wymagania.

Dolne granice są punktami startowymi deklarowanego wsparcia, nie dowodem,
że każda kombinacja została przebadana. Górne ograniczenia oddzielają
większe zmiany API. Już działającego środowiska nie trzeba aktualizować:
zwykłe `pip install -r ...` pozostawia zainstalowaną zgodną wersję,
o ile inne zależności nie wymagają jej zmiany.
[Zasady pip](https://pip.pypa.io/en/stable/cli/pip_install/).

**Kod modelu i jego wagi są osobną sprawą.** Aplikacja sprawdza ich zgodność.
RoMa wymaga obecnie `romav2==2.0.1`; inne wydanie odrzuci istniejący adapter.
To wyjątek wynikający z działania programu, a nie ogólne przypięcie bibliotek.

Przed większą aktualizacją zachowaj działające środowisko i zapisz sesję.
Opiekun może utworzyć drugie środowisko i sprawdzić aktualizację tam.
Nie trzeba wykonywać aktualizacji przy każdym uruchomieniu.

## 10. Najczęstsze problemy

| Komunikat lub objaw | Co zrobić |
| --- | --- |
| `conda` nie jest rozpoznawana | Windows: otwórz **Miniforge Prompt**. Ubuntu: otwórz nowy terminal po instalacji; jeśli nie pomogło, użyj polecenia poniżej. |
| `No module named stmviewer` | Polecenie uruchomiono z niewłaściwego folderu. Wróć do kroku 5; w bieżącym folderze musi być katalog `stmviewer`. |
| Nie znaleziono `requirements-ecc.txt` | Wróć do kroku 1 i 5. Nie wchodź dodatkowo do podfolderu `stmviewer`. |
| `No module named PyQt6`, `numpy` lub `cv2` | Sprawdź `(stmviewer)` i powtórz krok 6 w tym środowisku. |
| Metoda z modelem jest niedostępna | Podstawowa instalacja nie zawiera modeli. Przejdź do instrukcji modeli; inne funkcje mogą działać. |
| Błąd `xcb` / biblioteki graficznej w Ubuntu | Zastosuj kroki poniżej. Nie ustawiaj trybu `offscreen` do zwykłej pracy. |
| `pip check` zgłasza konflikt | Zapisz pełny komunikat. Nie używaj `--no-deps`; najlepiej przygotować świeże środowisko zgodnie z tą instrukcją. |
| Okno otworzyło się, ale późniejsze obliczenie nie działa | Zapisz komunikat i nazwę metody. Poprawny start GUI nie sprawdza jeszcze wszystkich modeli i kodeków. |

Ubuntu, gdy conda nadal nie jest rozpoznawana przy domyślnym folderze
instalacji Miniforge:

~~~bash
source "$HOME/miniforge3/etc/profile.d/conda.sh"
conda activate stmviewer
~~~

Ubuntu 24.04, gdy brakuje bibliotek Qt/X11:

~~~bash
sudo apt update
sudo apt install libxcb-cursor0 libxkbcommon-x11-0 libxcb-icccm4 libxcb-keysyms1 libxcb-render-util0 libgl1
~~~

`sudo` poprosi o hasło użytkownika Ubuntu. Podczas wpisywania nie widać
znaków — to prawidłowe. Są to biblioteki systemowe okna, opisane w
[wymaganiach Qt dla Linuksa](https://doc.qt.io/qt-6/linux-requirements.html).
Jeżeli błąd nadal występuje, prześlij pełną treść; przyczyny `xcb` mogą być różne.

Do zgłoszenia problemu dołącz zrzut/tekst komunikatu, system i wersje.
Po zamknięciu programu wykonaj:

~~~text
python --version
python -m pip list
~~~

Nie trzeba znać znaczenia wszystkich nazw. Lista pomaga odtworzyć problem.
Szczegóły wykonanych sprawdzeń tej instrukcji są w
[raporcie instalacji](installation-validation.md).
