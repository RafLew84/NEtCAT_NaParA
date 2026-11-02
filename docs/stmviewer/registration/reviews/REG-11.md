# REG-11 — testy i przeglądy

Data: 2026-11-02. Baza `3a3a684`. Implementacja `cfc1547`,
poprawka po przeglądzie `4e69d40`; zakres `3a3a684..4e69d40`.
Status: `ready-for-review`; odbiór ręczny pozostaje do wykonania.

## Testy

- Końcowy zestaw Viewera: **761 passed, 14 skipped**, 77,23 s.
  `QT_QPA_PLATFORM=offscreen PYTHONPATH=.:tests/stmviewer python -m pytest -q tests/stmviewer`.
  Pominięcia dotyczą opcjonalnych rzeczywistych modeli; nowy RoMa sprawdzono osobno.
- **4 rzeczywiste testy RoMa**: para CPU/CUDA, łańcuch CPU, graf CPU
  z LS/Huberem i zastosowaniem do filmu — wszystkie zaliczone.
- **2 rzeczywiste testy GUI Qt offscreen**: CPU/CUDA, sprawdzanie modelu,
  rejestracja, anulowanie, złe SHA checkpointu i zachowanie poprzedniego wyniku.
- Mypy strict: **94 moduły, bez błędów**:
  `python -m mypy --config-file stmviewer/mypy.ini --cache-dir /tmp/stmviewer-reg11-mypy`.
- Backend/proces: 17 testów publicznych granic, w tym kończenie procesu i wątku,
  EOF, protokół, OOM, ścieżki względne i gęste błędne skupisko.
- Pełne filmy i porównanie wzorców opisuje [raport rzeczywisty](../roma-results.md).
  Wszystkie cztery presety CUDA sprawdzono na znanym ruchu i nieruchomym pasie.
- Maksymalny rozmiar zmienionego pliku kodu poniżej 1000 linii;
  `git diff --check` bez uwag.

Pełny zestaw repozytorium w udokumentowanym trybie importlib:
**2539 passed, 18 failed, 26 skipped**, 299,25 s. Cztery niepowodzenia
Viewera dotyczyły dawnej zamkniętej listy nazw metod, której brakowało nowego
RoMa. Oczekiwanie poprawiono; końcowy zestaw Viewera powyżej jest zielony.
Pozostałe **14 identyfikatorów błędów MolTrack/NanoTrack jest identyczne**
z `/tmp/reg10-full-suite.log` i `/tmp/stmviewer-session-full-suite.log`;
porównanie zbiorów identyfikatorów nie wykazało nowych błędów tych aplikacji.
Ich kod nie został zmieniony.

Polecenie pełnego biegu:

```bash
PYTHONPATH=.:tests/moltrack:tests/stmviewer QT_QPA_PLATFORM=offscreen \
python -m pytest -q --import-mode=importlib --continue-on-collection-errors
```

Pierwszy bieg bez importlib zatrzymał się na 6 istniejących kolizjach nazw
modułów testowych. Dodatkowy bieg samego Viewera bez jawnego PYTHONPATH
miał jeden błąd importu pomocnika w procesie testu AVI; poprawne polecenie
końcowe zapewnia ten sam PYTHONPATH także procesowi potomnemu.
Nie wprowadzano zmian głównej konfiguracji testów.

Logi: `/tmp/stmviewer-reg11-full-importlib.log`,
`/tmp/stmviewer-reg11-viewer-final.log` oraz katalogi wyników z raportu.

## Standards

Przegląd `3a3a684...cfc1547`: **0 uwag**. Zachowano granice aplikacji,
odrębne odpowiedzialności matcher/process/worker, izolację modelu oraz
rozróżnienie prób automatycznych i ręcznych.

Ponowny przegląd `cfc1547...4e69d40`: **0 uwag**. Typowane `roma_options`
zachowuje konfigurację niezależnie od aktywnej metody, przy odczycie
bez uruchamiania procesu. Poprawiona etykieta opisuje punkty przed konsensusem.

## Spec

Pierwszy przegląd: **1 uwaga P2** — zapis po zmianie RoMa na Phase lub
EfficientLoFTR gubił nieaktywną konfigurację RoMa. Potwierdzono to rzeczywistym
zapisem/odczytem sesji przez Qt. Historia XY pozostawała zachowana.

Naprawa w `4e69d40`: sesja zapisuje niezależne `roma_options` w formacie v6,
z odczytem wcześniejszych v1–v5. Dwie regresje GUI i test serializacji
przeszły red→green. Recenzent powtórzył zapis/odczyt obu wariantów przy
blokadzie `Popen`: interpreter, wagi, DINOv3, preset i seed pozostają zachowane.

Przegląd zamknięty: **0 otwartych uwag Spec; 0 uwag Standards**.

## Odbiór ręczny i ograniczenia

Automatyczne Qt offscreen nie jest ręcznym odbiorem GUI. Użytkownik ma
wykonać [scenariusz](../roma-manual.md), w tym ocenę jakości na obu filmach,
ręczną korektę i VLC. Windows oraz karta 8 GB nie były stanowiskami próby.
RoMa wciąż potrafi dopasować nieruchomy artefakt. Huber osiągnął limit
iteracji na pełnych filmach; LS i łańcuch były kompletne. Tych ograniczeń
nie oznaczono jako sukcesu jakościowego modelu.
