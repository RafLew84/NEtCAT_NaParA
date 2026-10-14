# NEtCAT / NaParA

Repozytorium kilku aplikacji do pracy z obrazami STM. Każda aplikacja pozostaje
w swoim katalogu głównym i jest uruchamiana jako moduł Pythona.

| Katalog | Przeznaczenie |
| --- | --- |
| `napara/` | Istniejąca aplikacja oraz współdzielone modele obrazów, czytniki i viewer |
| `nanotrack/` | Istniejące śledzenie cząstek i krawędzi oraz rejestracja sekwencji |
| `moltrack/` | Istniejąca analiza obrazów molekularnych |
| `stmbrowser/` | Istniejąca przeglądarka obrazów i eksport par |
| `stmviewer/` | Nowy program: przeglądanie, zapis STP/MPP/S94 i rejestracja |
| `stmdomains/` | Nowy program: wykrywanie i analiza domen molekularnych |

Nowe programy mają obecnie uruchamialne okna startowe z akcją zakończenia.
Odczyt, zapis, rejestracja i analiza będą wdrażane według nowych map użytkownika.

## Uruchomienie nowych aplikacji

W katalogu głównym danego worktree, z Pythonem 3.12:

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements/stm-apps.txt
python -m stmviewer.main
# albo:
python -m stmdomains.main
```

Na Windows utwórz środowisko przez `py -3.12 -m venv .venv`, a w PowerShell
aktywuj je przez `.venv\Scripts\Activate.ps1`. Można też bez aktywacji wywołać
bezpośrednio `.venv/bin/python` lub `.venv\Scripts\python.exe`.

Każdy worktree używa własnego `.venv`. Zależności w `requirements/stm-apps.txt`
obejmują tylko nowe szkielety; istniejące aplikacje wymagają swoich bibliotek.

W VS Code otwórz cały katalog worktree i wybierz jego `.venv` przez
**Python: Select Interpreter**. **Run and Debug** udostępnia konfiguracje
**STM Viewer** i **STM Domains**; te same aplikacje są dostępne w **Run Task**.

## Plany i współpraca

- [STM Viewer](docs/stmviewer/README.md) — miejsce na mapę i zadania przeglądarki.
- [STM Domains](docs/stmdomains/README.md) — miejsce na mapę i zadania analizy domen.
- [Praca równoległa](docs/PARALLEL_DEVELOPMENT.md) — role sesji, worktree i scalanie.

Gałąź `stm-next` zaczyna się od `ea41c8e`, sprzed październikowej mapy NanoTrack.
Dotychczasowe prace nad tą mapą pozostają na `nanotrack-registration`.
