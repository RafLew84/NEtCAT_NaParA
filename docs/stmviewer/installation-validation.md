# Sprawdzenie instrukcji i zakresów zależności

Data: 2026-11-03. Dotyczy dokumentacji dla początkujących oraz zmiany list
bibliotek Viewera. Nie zmieniano algorytmów ani działającego środowiska netcat.

## Co zmieniono

- Podstawowa instrukcja z Miniforge dla Ubuntu 24.04 i Windows 11,
  osobna instrukcja obsługi oraz dodatków z modelami.
- Samodzielny guide.html do otwarcia w przeglądarce, wysłania jako jeden
  plik i drukowania do PDF.
- Zakresy wersji zamiast dokładnych przypięć w listach Viewera, w tym
  podstawowych, modeli i narzędzi deweloperskich.
- PyQt6 sam dobiera Qt6 i sip. Viewer ma własne wymaganie PyQt6;
  requirements/stm-apps.txt dla wspólnego szkieletu pozostawiono bez zmian.
- Kornia dobiera kornia_rs. Torch/torchvision instalowane są jako zgodna
  para dla wybranego CPU/CUDA.
- RoMa zachowuje romav2==2.0.1, zgodnie z walidacją kodu w adapterze.
  Pozostałe wymagania mają zakresy. RoMa na Linux zależy od fused-local-corr;
  jego własne wymagania mogą nadal przypinać Torch dla zgodności binarnej.
  Lokalny fused-local-corr 0.3.211 wymaga torch==2.11.0.
- Historyczne wersje w raportach eksperymentów pozostawiono jako zapis
  faktycznie użytych środowisk, a nie wymagania nowej instalacji.

## Nowe środowisko Linux

Utworzono izolowany venv z Pythonem 3.12, poza repozytorium:
`/tmp/stmviewer-install-check-20261103`. Instalacja requirements-ecc.txt
oraz narzędzi pytest/pytest-qt zakończona poprawnie; pip check bez konfliktów.
Nie korzystano z pakietów głównego netcat.

| Biblioteka | Faktycznie zainstalowana wersja |
| --- | --- |
| PyQt6 / Qt6 | 6.12.0 / 6.12.0 |
| NumPy | 2.5.4 |
| SciPy | 1.18.1 |
| scikit-image | 0.26.0 |
| OpenCV | 4.14.0.94 |
| pytest / pytest-qt | 9.2.0 / 4.5.0 |

To wyniki sprawdzenia, nie lista wersji do ręcznego przypięcia.

Wybrano 181 przypadków: STP/S94/MPP, seria, zoom/gamma, odtwarzanie,
Phase i pozostałe metody CPU, AKAZE/parametry, MPP, AVI i sesje.
180 zaliczono od razu. Jeden test nieobecnej Kornia zakładał zainstalowany
Torch; w podstawowym środowisku poprawnie zgłaszany był wcześniejszy brak
Torch. Dodano jawne pominięcie tego wariantu przy braku Torch,
bez zmiany zachowania aplikacji.

Po poprawce cały dotknięty plik: **33 passed, 1 skipped**.
W istniejącym netcat, gdzie Torch jest dostępny, wszystkie pięć wariantów
braku bibliotek: **5 passed**. Tym samym 180 przypadków zakresu jest
zaliczonych, a jeden ma jawnie niespełniony warunek środowiskowy.
Testy GUI wykonano automatycznie przez Qt offscreen, nie ręcznie na ekranie.

Lokalne logi i raporty:

- /tmp/stmviewer-install-20261103.log i .json — instalacja.
- /tmp/stmviewer-install-tests-20261103.log i .xml — pierwsze 181 przypadków.
- /tmp/stmviewer-install-cpu-final.log — 33/1 po poprawce testu.
- /tmp/stmviewer-install-netcat-check.log — 5 przypadków w netcat.

## Windows

Resolver pip z `--dry-run --ignore-installed --only-binary=:all:`,
platformą `win_amd64` i Pythonem 3.12 dobrał wszystkie zależności
requirements-ecc.txt, w tych samych głównych wersjach co tabela.
Raport: /tmp/stmviewer-install-windows-20261103.json i .log.

To sprawdza dostępność pakietów i zgodność deklarowanych zależności.
Nie uruchomiono aplikacji na Windows, nie wykonano instalatora Miniforge
na obu systemach ani interaktywnego odbioru tej instrukcji przez nowego użytkownika.

## Pozostałe granice weryfikacji

Istniejące pakiety netcat i netcat-romav2 spełniają nowe zakresy;
sprawdzono to bez zmiany tych środowisk.

Nie instalowano nowego pełnego stosu GPU ani RoMa w świeżym środowisku.
Nowe zakresy bibliotek modeli nie oznaczają, że sprawdzono każdą kombinację.
Dotychczasowe rzeczywiste próby modeli są opisane w dokumentacji rejestracji;
nowe stanowisko wymaga Sprawdź model i własnej próby na danych.

Instrukcje pobrania Miniforge, wyboru PyTorch oraz użycia pip/conda
zweryfikowano w podlinkowanych dokumentacjach autorów. Opisy przycisków
i zapisu porównano z aktualnym kodem Viewera.

Pełnego zestawu repozytorium nie uruchamiano: zmiana dotyczy instrukcji,
list zależności i warunku jednego testu, bez zmian kodu aplikacji ani modułów
współdzielonych. Sprawdzono lokalne odnośniki, strukturę HTML, wymagania
pakietów oraz git diff --check.

## Aktualizowanie wersji HTML

Źródłem są distribution.md, installation.md, user-guide.md, installation-models.md
i niniejszy raport. Dla opiekuna dokumentacji, z katalogu repozytorium:

~~~text
python -m pip install -r docs/stmviewer/requirements-docs.txt
python docs/stmviewer/build-guide.py
~~~

Markdown jest potrzebny tylko do zbudowania dokumentu.
Użytkownik gotowego guide.html nie potrzebuje Pythona ani serwera do czytania
instrukcji. Dostęp do zewnętrznych stron instalatorów wymaga internetu.
