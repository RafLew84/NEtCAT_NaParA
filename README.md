# NEtCAT / NaParA

Repozytorium kilku aplikacji do pracy z obrazami STM. Każda aplikacja pozostaje
w swoim katalogu głównym i jest uruchamiana jako moduł Pythona.

| Katalog | Przeznaczenie |
| --- | --- |
| `napara/` | Istniejąca aplikacja oraz współdzielone modele obrazów, czytniki i viewer |
| `nanotrack/` | Istniejące śledzenie cząstek i krawędzi oraz rejestracja sekwencji |
| `moltrack/` | Istniejąca analiza obrazów molekularnych |
| `stmbrowser/` | Istniejąca przeglądarka obrazów i eksport par |
| `stmviewer/` | STM Viewer: odczyt STP/S94/MPP, rejestracja, sesje i eksport MPP/AVI |
| `stmdomains/` | Szkielet programu do wykrywania i analizy domen molekularnych |

STM Viewer zawiera przeglądanie obrazów i filmów, rejestrację par oraz sekwencji,
korekty ręczne i zapis sesji `.stmsession`. Rozwój STM Domains trwa na osobnych
gałęziach `domains/*`; ta wersja repozytorium zawiera jego okno startowe.

## Uruchomienie STM Viewer

W katalogu głównym danego worktree, z Pythonem 3.12:

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -r stmviewer/requirements-ecc.txt
python -m stmviewer.main
```

Na Windows utwórz środowisko przez `py -3.12 -m venv .venv`, a w PowerShell
aktywuj je przez `.venv\Scripts\Activate.ps1`. Można też bez aktywacji wywołać
bezpośrednio `.venv/bin/python` lub `.venv\Scripts\python.exe`.

Ten zestaw obejmuje podstawowe zależności oraz OpenCV do ECC i eksportu AVI.
Metody korzystające z modeli wymagają dodatkowych bibliotek i lokalnych wag:
zobacz [instalację](docs/stmviewer/installation.md),
[opcjonalne modele](docs/stmviewer/installation-models.md)
i [obsługę programu](docs/stmviewer/user-guide.md).

Każdy worktree używa własnego `.venv`. Zależności istniejących aplikacji są
opisane w ich katalogach. Sam szkielet STM Domains można uruchomić przez
`python -m stmdomains.main`; do jego osobnego środowiska wystarcza
`python -m pip install -r requirements/stm-apps.txt`.

W VS Code otwórz cały katalog worktree i wybierz jego `.venv` przez
**Python: Select Interpreter**. **Run and Debug** udostępnia konfiguracje
**STM Viewer** i **STM Domains**; te same aplikacje są dostępne w **Run Task**.

## Plany i współpraca

- [STM Viewer](docs/stmviewer/README.md) — instrukcje, mapa i status funkcji.
- [Integracja Viewera do main](docs/stmviewer/integration-main.md) — zakres i sprawdzenia.
- [STM Domains](docs/stmdomains/README.md) — miejsce na mapę i zadania analizy domen.
- [Praca równoległa](docs/PARALLEL_DEVELOPMENT.md) — role sesji, worktree i scalanie.

Gałąź `stm-next` zaczyna się od `ea41c8e`, sprzed październikowej mapy NanoTrack.
Dotychczasowe prace nad tą mapą pozostają na `nanotrack-registration`.
