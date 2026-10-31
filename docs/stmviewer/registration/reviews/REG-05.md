# REG-05 — wykonanie i odbiór

Data: 2026-10-31. Baza przeglądu: `a59029d`.
Implementacja: `303e401`; poprawka po przeglądzie: `75eb70f`.
Status: **ready-for-review**.
Ręczny odbiór użytkownika: **niewykonany**.

## Dostarczona funkcja

Osobna metoda **Deep Matcher + lokalne fragmenty (v1)** działa dla pary i całej
serii. Dokładny Deep bez ECC inicjalizuje lokalne poszukiwanie. Przestrzennie
rozdzielone fragmenty i odporna agregacja dają jedno końcowe XY albo jawną odmowę.
Konfiguracja jest wspólna dla filmów i opisana wersją; model ładuje się raz
na serię. Końcowy aligned powstaje z oryginałów z jedną interpolacją.

GUI pokazuje położenie fragmentów, wektory, zgodność/odrzucenie/brak dopasowania,
przyczyny i miary heurystyczne. Można przełączyć dokładny start Deep oraz wynik
lokalny bez ponownego modelu. Zachowana próba, zoom, kadr, gamma i kontrast
pozostają. Odmowa ma osobny podgląd diagnostyczny i nie staje się wynikiem
możliwym do zastosowania. Konkurujące grupy są jawnie niepewne.

Pełny film używa tego samego estymatora. Odmowa jednej pary lub anulowanie
odrzuca nową próbę, pozostawiając poprzedni aligned oraz ręczne korekty.
Po udanym przebiegu działają ręczne korekty, usuwanie i eksport MPP/AVI;
diagnostyka automatyczna pozostaje historią. Żadna nakładka nie trafia do
wartości pomiarowych. MPP zapisuje końcowe XY, nazwę/wersję metody, geometrię,
ważność próbek i status `manual_review` bez procentu pewności. Pełny zapis
próby wraz z mapą fragmentów pozostaje w REG-07.

## Testy automatyczne

TDD objął publiczne granice: para → XY/dowody, GUI → podgląd/niezmienność próby,
seria → jedna translacja/ręczna korekta/eksport. Kontrolowana jest granica
zewnętrznego LoFTR; lokalne korelacje, agregacja, render i zapisy są rzeczywiste.
Wzorce obejmują subpikselowe XY obu znaków, duży artefakt, dwie grupy ruchu,
periodyczność, jeden pas tekstury, jednostki wartości, NaN i anulowanie.

Początkowy próg NCC 0,45 odrzucał również znane ruchy przy niezależnym szumie.
Test regresyjny najpierw był RED; wprowadzono minimum NCC 0,1 oraz względne
wyróżnienie maksimum 3,5 względem mediany/MAD tła odpowiedzi. Zachowano
margines maksimów 0,025 i wymagania poparcia przestrzennego. Test jest GREEN;
niezależne obrazy szumu białego/skorelowanego nadal powodują odmowę. Miara
nie jest skalibrowanym prawdopodobieństwem ani niezależną walidacją.

Pełne repo wykonano raz: **2258 passed, 14 failed, 16 skipped**, 278,49 s.
Wszystkie 14 identyfikatorów błędów jest identyczne z historycznym logiem
`/tmp/reg02a-full-suite-final.log`: 11 MolTrack/SAM2, 3 NanoTrack. Nie zmieniano
wspólnych aplikacji. Przebieg rozpoczął się przed końcową poprawką kryterium
szumu; po niej sprawdzono celowany zakres i pełny Viewer.
Log repo: `/tmp/stmviewer-reg05-full-pytest.log`.

- 19 nowych przypadków: 12 rdzenia, 3 integracji/eksportu, 3 GUI pary i 1 GUI filmu.
- Pełny Viewer po zamrożeniu implementacji: **474 passed, 2 skipped**, 58,05 s.
  Dwa pominięcia wymagają zmiennej z lokalnymi wagami; rzeczywisty model
  sprawdzono oddzielnie. Log: `/tmp/stmviewer-reg05-viewer-frozen-pytest.log`.
- Po poprawce samego opisu konfiguracji: **6 testów integracji/GUI PASS**.
  Mypy strict: **49 plików PASS**. Ruff i `git diff --check`: PASS.
  Zmienione pliki kodu mają mniej niż 1000 linii; największy ma 908.
- Wcześniejszy przebieg Viewera zakończył się 473 PASS, 1 FAIL, 2 SKIP:
  trafił na fazę RED równoległej poprawki etykiety kontrastu maksimum w GUI.
  Po zakończeniu zmian powtórzono cały Viewer ze wskazanym wyżej wynikiem.

Polecenia (`netcat`, katalog `NEtCAT-viewer`):

```bash
python -m mypy --config-file stmviewer/mypy.ini --no-incremental
PYTHONDONTWRITEBYTECODE=1 QT_QPA_PLATFORM=offscreen OPENBLAS_NUM_THREADS=1 \
PYTHONPATH=.:tests/stmviewer python -m pytest -q -p no:cacheprovider tests/stmviewer
```

Pełne repo używało `PYTHONPATH=.:tests/moltrack:tests/stmviewer` oraz
`python -m pytest --import-mode=importlib -q -p no:cacheprovider`.

## Rzeczywiste dane i GUI

[Wyniki prób](../local-consensus-results.md) rozdzielają znane syntetyczne ruchy,
pomiary STM, CPU/CUDA, zasoby i ponowny odczyt MPP. Finalne ustawienia dały
lokalne XY dla **2 z 14** wskazanych par; pozostałe próby odmówiły. Bazowy Deep
daje XY dla 14/14. To porównanie kompletności, nie fizycznej poprawności XY.
MOVIE_4 po usunięciu źródłowych 1 i 2 odmawia w bieżącej parze 2→3;
MOVIE_8 w 1→2. Nie powstał kompletny lokalny aligned tych pomiarów.
Wzorzec translacji z prawdziwym modelem na CPU kończy się oraz eksportuje.

Automatyczne rzeczywiste Qt (`xcb`) z wagami LoFTR i CUDA obejmowało odmowę
MOVIE_4 bieżąca 29→30, źródłowa 31→32, i udaną parę wzorca translacji.
Sprawdzono mapę, tabelę, dokładny start, zachowanie wcześniejszej próby oraz
obejrzano zrzuty. Raport i obrazy: `/tmp/stmviewer-reg05-real-gui/`.
To nie jest ręczny odbiór jakości przez użytkownika ani sprawdzenie Windows/VLC.

## Standards

Końcowy zakres `a59029d…75eb70f`: **0 otwartych uwag**.
Jedna heurystyczna uwaga P3 została naprawiona w `75eb70f`: szczegóły próby
ponownie dopisywały parametry już zawarte w opisie wrappera lokalnego.
Teraz wrapper jest jedynym źródłem tego opisu; zwykłe backendy zachowują
wcześniejsze zachowanie. Nie stwierdzono twardych naruszeń zasad repozytorium
ani nowych uwag w przeglądzie poprawki.

## Spec

Końcowy zakres `a59029d…75eb70f`: **0 otwartych uwag** dotyczących braków,
nieprawidłowej implementacji lub rozszerzenia zakresu. Potwierdzono dokładny
start Deep, rozszerzone lokalne szukanie, rozdzielone poparcie, konkurujące
grupy/odmowy, diagnostykę GUI, wspólny estymator pary/serii i eksport.
Poprawka opisu nie zmienia tych zachowań. Odbiór jakości pozostaje manualny.

Standards: 1 uwaga naprawiona, 0 otwartych. Spec: 0 uwag.

## Pozostały odbiór i ograniczenia

[Instrukcja ręczna](../local-consensus-manual.md) podaje uruchomienie, dane,
stałe pary, odmowy, anulowanie, ręczne korekty i eksporty. Kryteria ticketu
pozostają otwarte do jawnego odbioru użytkownika. W szczególności nie
potwierdzono poprawy jakości STM względem Deep, odbioru Windows/VLC ani
pracy na GPU 8 GB. Poparcie estymatora nie jest kontrolą na niewykorzystanych
fragmentach z REG-06. NaN/Inf są jawnie odrzucane przed Deep; nie wypełniamy
braków. Nie ma nowych zmian wymaganych w modułach współdzielonych.
