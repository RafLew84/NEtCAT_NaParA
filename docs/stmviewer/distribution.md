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

**Program automatycznie wykrywa modele w folderze `models` obok programu.**
Po wybraniu metody pola wag i kodu powinny być już uzupełnione.
Przy innym układzie folderów użyj przycisków wyboru wag i kodu.
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

Dla RoMa sprawdź również pole **Python środowiska RoMa**. Program wykrywa
środowiska o nazwach opisanych niżej. Jeśli pole nie wskazuje właściwego
Pythona, wybierz go ręcznie. Jego ścieżkę uzyskasz
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

Po wykryciu lub wskazaniu plików kliknij **Sprawdź model**, a następnie wypróbuj jedną
parę klatek. Zapisy sesji zachowują konfigurację pracy i ścieżki modeli;
po przeniesieniu sesji na inny komputer może być konieczne ich poprawienie.

## Skąd biorą się domyślne ścieżki

Przy pierwszym wyborze modelu program sprawdza:

1. Folder `models` obok uruchomionego `stmviewer` — w tej samej paczce.
2. Dotychczasowy cache `~/.cache/stmviewer`.

Wybierany jest pierwszy komplet wymaganych plików danego modelu:
kod i wagi pochodzą z jednego katalogu, bez łączenia niepełnych zestawów.
Odnalezione ścieżki pojawiają się w polach aplikacji. To wykrycie plików,
nie potwierdzenie zgodności modelu: służy do tego **Sprawdź model**.

Możesz rozpakować ZIP np. do **Dokumentów**, również w OneDrive.
Nazwa użytkownika, nazwa folderu paczki i bieżący katalog terminala nie
wpływają na wykrywanie — punktem odniesienia jest uruchomiony kod programu.
Zachowaj układ:

~~~text
NEtCAT/
    stmviewer/
    napara/
    nanotrack/
    models/
        loftr/
        efficientloftr/
        lightglue/
        matchanything/
        romav2/
~~~

**Ręcznie wybrane ścieżki i ustawienia odczytane z sesji mają pierwszeństwo.**
Nie są zastępowane po przełączeniu metody, nawet jeśli wskazany plik zniknął.
Dla Deep Matcher zmienna `STMVIEWER_LOFTR_WEIGHTS` także ma pierwszeństwo
przed wykrywaniem. Jeśli wskazuje stary komputer, popraw ją albo usuń.

Gdy plików nie ma, Deep pozostawia puste pole, a pozostałe modele pokazują
dotychczasowe propozycje ścieżek w cache. Nadal można użyć **Wybierz wagi…**
i **Wybierz katalog kodu…**. Nie ma pobierania wag ani przeszukiwania całego
dysku. Przy dodaniu modeli do już uruchomionego programu wskaż je ręcznie
lub uruchom program ponownie.

### Wykrywanie środowiska RoMa

Program szuka istniejącego Pythona w środowiskach o nazwach
`stmviewer-roma`, a następnie `netcat-romav2`. Sprawdza rodzeństwo bieżącego
środowiska conda, foldery `miniforge3`, `miniconda3`, `anaconda3` i `.conda`
w katalogu domowym oraz wpisy w `~/.conda/environments.txt`.
Środowisko, w którym działa sama aplikacja, jest pomijane.

Na Windows szukany jest `python.exe`, na Linux `bin/python`.
Samo odnalezienie pliku nie uruchamia interpretera, nie instaluje bibliotek
i nie sprawdza jego wersji RoMa. Po instalacji kliknij **Sprawdź model**.
Jeśli używasz innej nazwy środowiska, wskaż Python przyciskiem **Wybierz…**.

Przy braku środowiska pozostaje edytowalna propozycja
`~/miniconda3/envs/netcat-romav2/bin/python` (Linux) albo
`~/miniconda3/envs/netcat-romav2/python.exe` (Windows).

## Krótka próba po rozpakowaniu

1. Rozpakuj całą paczkę do wybranego folderu w Dokumentach.
2. Przygotuj środowiska według instrukcji i uruchom `python -m stmviewer.main`.
3. Wybierz kolejno Deep Matcher, EfficientLoFTR, LightGlue, MatchAnything
   i RoMa. Pola wag i kodu powinny wskazywać folder `models` tej paczki.
4. Przy RoMa sprawdź również ścieżkę do Pythona utworzonego środowiska.
5. Wybierz CPU albo CUDA i kliknij **Sprawdź model**.
6. Zmień ręcznie jedną ścieżkę, wybierz inną metodę i wróć.
   Ręczny wybór powinien pozostać.
7. Otwórz `tests/stmviewer/fixtures/registration/cpu.mpp` i wypróbuj parę.
