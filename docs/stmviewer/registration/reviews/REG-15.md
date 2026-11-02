# REG-15 — karta testów i przeglądów

Data: 2026-11-03. Baza: f61a6aea65c8078ffc168731c8b8cb18b76bc0b1.
Implementacja: 53c6d69; poprawki po przeglądzie: 0032ace.
Status: **ready-for-review**. [Instrukcja ręczna](../method-parameters-manual.md),
[próby STM](../method-parameters-results.md).

## Zakres i TDD

Osobne niezmienne konfiguracje i walidacja; wspólne przygotowanie obrazów;
dialog i kontroler ustawień; przekazanie tej samej konfiguracji do pary,
łańcucha i grafu; niezależne metadane wyniku oraz stan sesji.

RED/GREEN: percentyle/CLAHE, walidacja profili, rzeczywiste parametry
OpenCV, spójność wyników trzech dróg i cache grafu, odczyt sesji/MPP,
atomowe OK/Anuluj/reset, małe progi, blokada zapisu w trakcie zadania,
zmiana konfiguracji w już otwartych oknach. Po przeglądzie dodano czerwone
testy parametrów po odczycie MPP i tolerancji podanej jako liczba całkowita.
Testy używają publicznych granic oraz rzeczywistych bibliotek;
sterowane opóźnienie w teście zajętości jest na granicy zewnętrznego OpenCV.

## Sprawdzenia automatyczne

- Pełne repo: **2637 passed, 14 failed, 52 skipped**, 293,77 s.
  Log /tmp/reg15-full-final.log, JUnit /tmp/reg15-full-final.xml.
  Zestaw 14 identyfikatorów awarii jest dokładnie taki sam jak
  data/registration-reg14/baseline-test-failures.json: 11 MolTrack/SAM2,
  dwa scenariusze GUI/sesji NanoTrack i ścieżka SAM2 w NanoTrack.
  Nie zmieniano tych modułów. Cały zestaw nie jest opisany jako zielony.
- W tym przebiegu **STM Viewer: 851 passed, 38 skipped**, bez awarii.
  Część rzeczywistych modeli wymaga osobnego jawnego włączenia.
- Osobne rzeczywiste modele: **10 passed**, CPU/CUDA oraz Qt offscreen,
  konfiguracje domyślne i zmienione, znane XY, sesja/MPP, anulowanie
  i błędne zasoby. Log /tmp/reg15-real-model-tests.log.
- Po poprawkach z przeglądu: **32 passed**, 21,45 s, obejmujące konfiguracje,
  integrację, GUI, MPP i ponownie rzeczywisty LightGlue.
  Log /tmp/reg15-review-fixes.log. Niezależny recenzent dodatkowo
  potwierdził trzy testy zgłoszonych regresji.
- Strict mypy: **105 plików bez błędów**. Kontrola Ruff F, git diff --check,
  lokalne odnośniki i limit długości zmienionych plików.
  Największy plik ma 1001 linii; cel 1000 przekroczony o jedną,
  twardy limit 1500 zachowany.
- 24 automatyczne próby parametrów na STM, z pełnymi profilami,
  diagnostyką, czasem i obrazami porównania; nie zastępują oceny jakości.
- Automatyczne zrzuty obu formularzy obejrzano pod kątem układu i tekstu:
  /tmp/reg15-akaze-editor.png, /tmp/reg15-lightglue-editor.png.

Polecenie pełnego repo (netcat):

```bash
QT_QPA_PLATFORM=offscreen PYTHONPATH=.:tests/moltrack:tests/stmviewer \
python -m pytest -q --import-mode=importlib --continue-on-collection-errors
python -m mypy --config-file stmviewer/mypy.ini
```

Rzeczywiste modele włączono przez STMVIEWER_TEST_LIGHTGLUE=1 oraz
STMVIEWER_TEST_LIGHTGLUE_ROOT=/home/rlew/.cache/stmviewer/lightglue,
dla test_lightglue_real_backend.py, test_lightglue_real_integration.py
i test_lightglue_real_gui.py. Żadne zasoby nie zostały pobrane.

Pierwsze uruchomienie Viewera ujawniło problem cyklu referencji kontrolera
do rodzica Qt; usunięto silne pole rodzica i użyto QObject.parent().
Potwierdzono 71 testami dotkniętych scenariuszy, a następnie pełnym repo.
Pierwsze polecenie pełnego repo bez importlib zatrzymało się na sześciu
kolizjach nazw testów przy kolekcji; nie zaliczono go. Raport powyżej
dotyczy poprawnego polecenia z importlib i ścieżkami obu zestawów testów.

## Standards

Niezależny agent sprawdził bazę → implementację wobec AGENTS i zasad
Viewera oraz heurystyk Fowlera. **0 naruszeń.** Jedna uwaga nieblokująca:
mapowanie pełnych obliczeń LightGlue na depth/width było powtórzone
w workerze i metadanych. W 0032ace oba miejsca korzystają z
LightGlueParameters.adaptive_thresholds. Recenzent potwierdził zamknięcie.

**Końcowo: 0 otwartych uwag Standards.**

## Spec

Niezależny agent zgłosił dwa P2:

1. Opis parametrów po otwarciu MPP nie uwzględniał konfiguracji grafu
   oraz klatki odniesienia łańcucha, która nie ma własnej diagnostyki pary.
   Odczyt korzysta teraz z zapisu grafu lub diagnostyki zgodnego wyniku
   z tego samego MPP. Brak danych historycznych jest jawnie opisany.
2. Tolerancja radius=3 była poprawnym wejściem API, ale tekst konfiguracji
   różnił się od radius=3.0 odtworzonego z metadanych, blokując zapis sesji.
   Pola zmiennoprzecinkowe są normalizowane w niezmiennych konfiguracjach.

Oba naprawiono w 0032ace. Recenzent ponownie wykonał dwa przypadki GUI
eksport→odczyt MPP oraz zapis/odczyt sesji z całkowitą tolerancją:
**3 passed**. Potwierdził zamknięcie obu P2 i brak niezleconego zakresu.

Dodatkowa obserwacja: walidator grafu nie zestawia wszystkich powtórzonych
pól consensus_* z diagnostyką krawędzi przy ręcznie niespójnym zapisie.
Recenzent potwierdził istnienie tej luki przed REG-15 i brak osłabienia
walidacji przez tę zmianę. Normalny zapis generuje zgodne wartości;
uwaga jest nieblokująca i poza zakresem tego ticketu.

**Końcowo: 0 otwartych usterek Spec dotyczących REG-15.**

## Odbiór ręczny

Odbiór użytkownika jeszcze niewykonany. Testy Qt offscreen są automatyczne.
Nie potwierdzono interaktywnego przebiegu GUI, oglądania AVI w VLC,
Windows 11 ani stanowiska referencyjnego. Ocena wizualna dopasowania STM
pozostaje do wykonania. REG-14 zachowuje swój otwarty status;
REG-15a/15b nie są zaimplementowane. Zmiany współdzielone nie są potrzebne.
