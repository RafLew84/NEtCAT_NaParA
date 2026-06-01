# MolTrack - dokumentacja aktualnego zakresu

Ten dokument opisuje funkcjonalnosci dodane do `moltrack`. Aktualny zakres obejmuje fundament aplikacji, import i przegladanie jednej serii obrazow, zapis/odczyt projektu, regiony analizy z geometriami aktywnymi na wybranych klatkach, opcjonalny workflow rejestracji globalnych przesuniec XY, detekcje YOLO na aktywnej klatce, batch YOLO po working frames, detekcje YOLO w wybranym ROI oraz zapis detekcji do `.moltrack`.

Review bboxow, metryki, maski i pelny tracking sa nadal etapami planowanymi.

## Uruchamianie

Aplikacje uruchamia sie z katalogu projektu:

```bash
python -m moltrack.main
```

W srodowisku uzytkownika:

```bash
/mnt/c/Users/rlewa/anaconda3/envs/netcat/python.exe -m moltrack.main
```

Po starcie otwierane jest glowne okno `MolTrack Workspace`.

## Podstawowe zalozenia projektu

MolTrack pracuje na dokladnie jednej serii obrazow w jednym projekcie.

W projekcie rozrozniane sa dwa porzadki klatek:

- `Source Frame Index` - indeks klatki w oryginalnej serii z pliku albo listy plikow.
- `Working Frame Index` - indeks klatki w roboczej serii po odwróceniu kolejnosci albo usunieciu klatek.

Przyklad:

```text
Source frames:  0, 1, 2, 3
Working frames: 0, 1, 2, 3
```

Po imporcie z opcja reversed order:

```text
Working 0 -> Source 3
Working 1 -> Source 2
Working 2 -> Source 1
Working 3 -> Source 0
```

Usuniecie klatki dotyczy `Working Image Series`. Po usunieciu pozostale `Working Frame Index` sa reindeksowane od zera, ale `Source Frame Index` pozostaje provenance do oryginalnej klatki. Ta funkcja istnieje obecnie w modelu domenowym/API; dedykowane UI do usuwania klatek nie jest jeszcze dodane.

## Import obrazow

Import jest dostepny w menu:

```text
File -> Import Image Series...
```

Obslugiwane wejscia:

- `.mpp` - jeden plik traktowany jako jedna seria.
- `.stp` / `.s94` - lista plikow traktowana jako jedna seria.

Opcja:

```text
File -> Import Reversed Order
```

Jest to checkowalna opcja. Gdy jest wlaczona, import nie odwraca danych w `SourceImageSeries.raw_frames`, tylko tworzy odwrocone mapowanie `Working Frame Index -> Source Frame Index`.

Przyklad API:

```python
from moltrack.io import import_image_series

project = import_image_series("movie.mpp")
reversed_project = import_image_series("movie.mpp", reverse_frame_order=True)
stack_project = import_image_series(["frame_001.stp", "frame_002.s94", "frame_003.stp"])
```

Po imporcie:

- projekt nie ma jeszcze sciezki `.moltrack`,
- `Save Project` dziala jak `Save Project As...`,
- pierwsza klatka robocza jest wyswietlana w viewerze.

## Viewer serii

Glowny viewer pokazuje aktywna klatke robocza. Pod viewerem znajduje sie slider klatek.

Etykieta klatki pokazuje:

```text
Working X/N | Source Y/M
```

Znaczenie:

- `Working X/N` - pozycja w roboczej serii.
- `Source Y/M` - odpowiadajaca klatka w oryginalnej serii.

Jesli projekt zostal otwarty z `.moltrack`, ale obrazy zrodlowe nie sa zaladowane do projektu, viewer jest pusty, a etykieta zawiera:

```text
Images not loaded
```

To jest oczekiwane, bo aktualny format `.moltrack` nie kopiuje obrazow zrodlowych.

## Format `.moltrack`

Projekt zapisywany jest jako zip-backed bundle z plikiem:

```text
manifest.json
```

Obecny schemat:

```text
moltrack.project.v1
```

Zapis zawiera:

- nazwe projektu,
- informacje o serii zrodlowej,
- `source_uri`,
- `source_uris`,
- `display_name`,
- `frame_count`,
- mapowanie `Working Frame Index -> Source Frame Index`,
- liste usunietych source frames,
- regiony analizy,
- informacje o regionach skopiowanych na serie,
- geometrie regionow aktywne na wybranych klatkach.
- shifty rejestracji `registration_shifts`.

Zapis nie zawiera:

- kopii obrazow zrodlowych,
- masek,
- detekcji YOLO,
- wynikow metryk,
- backendowych checkpointow.

Opcje w menu:

```text
File -> Open Project...
File -> Save Project
File -> Save Project As...
```

Przyklad API:

```python
from moltrack.persistence import save_project, load_project

save_project("analysis.moltrack", project)
loaded = load_project("analysis.moltrack")
```

## Regiony analizy

Region analizy opisuje obszar obrazu w natywnych wspolrzednych klatki.

Typy regionow:

- `terrace` - taras albo obszar powierzchni, dla ktorego beda liczone metryki.
- `step_edge` - krawedz stopnia albo pas krawedziowy.
- `ignore` - obszar ignorowany; ma najwyzszy priorytet przy przyszlym przypisywaniu detekcji.
- `custom` - pomocniczy region uzytkownika bez specjalnej semantyki.

Geometria regionu moze byc:

- `rect` - prostokat `x0, y0, x1, y1`,
- `polygon` - zamkniety wielokat/polyline.

Kazdy region ma:

- typ,
- nazwe,
- kolor RGB,
- geometrie w `coordinate_system="native"`.

Przyklad API:

```python
from moltrack.core import AnalysisRegion

terrace = AnalysisRegion.rectangle(
    kind="terrace",
    name="Terrace 1",
    color_rgb=(20, 120, 240),
    rect_xyxy=(10.0, 15.0, 180.0, 220.0),
)

ignore = AnalysisRegion.polygon(
    kind="ignore",
    name="Ignore artifact",
    color_rgb=(240, 40, 40),
    vertices_xy=[(5.0, 5.0), (40.0, 8.0), (35.0, 60.0), (8.0, 55.0)],
)
```

## UI regionow

Regiony sa dostepne w menu:

```text
Regions
```

oraz w prawym panelu `Regions`.

Lista regionow w panelu pokazuje logiczne nazwy regionow. Jeden logiczny region, np. `Terrace 1`, moze miec rozne geometrie aktywne na roznych klatkach.

### Add Rect Region...

Tworzy prostokatny region z dialogu.

Opcje dialogu:

- `Type` - `Terrace`, `Step edge`, `Ignore`, `Custom`.
- `Name` - logiczna nazwa regionu.
- `RGB` - kolor overlayu.
- `x0`, `y0`, `x1`, `y1` - wspolrzedne prostokata.

Geometria musi miec dodatnia szerokosc i wysokosc. Niepoprawny prostokat pokazuje ostrzezenie zamiast tracebacka.

Przyklad uzycia:

1. `Regions -> Add Rect Region...`
2. Wybierz `Type = Terrace`.
3. Wpisz `Name = Terrace 1`.
4. Ustaw kolor i wspolrzedne.
5. Zatwierdz.

Region zostanie dodany do listy, narysowany jako overlay i zapisany w stanie projektu.

### Draw Rect ROI

Tworzy edytowalny prostokatny ROI bez natychmiastowego zapisu regionu.

Przyklad uzycia:

1. `Regions -> Draw Rect ROI`
2. Przesun albo przeskaluj ROI w viewerze.
3. `Regions -> Commit Drawn Region...`
4. W dialogu wpisz typ, nazwe i kolor.

### Draw Polyline Region

Tworzy edytowalny zamkniety polygon/polyline w viewerze.

Przyklad uzycia:

1. `Regions -> Draw Polyline Region`
2. Ustaw punkty wielokata.
3. `Regions -> Commit Drawn Region...`
4. W dialogu wpisz typ, nazwe i kolor.

### Commit Drawn Region...

Zapisuje aktualnie narysowany ROI albo polygon jako `AnalysisRegion`.

Opcje dialogu:

- `Type` - typ regionu.
- `Name` - logiczna nazwa regionu.
- `RGB` - kolor overlayu.

Jesli podana nazwa jest nowa, powstaje nowy logiczny region.

Jesli podana nazwa juz istnieje, narysowana geometria zostaje zapisana jako alternatywna geometria tego samego logicznego regionu dla wybranego zakresu klatek. Wtedy pojawia sie dialog zakresu klatek.

### Clear Drawn Region

Usuwa niezapisany ROI/polygon z viewera.

Nie usuwa regionu juz dodanego do projektu.

### Edit Selected Region...

Edytuje zaznaczony region z listy. Obecnie dialog edycji wspiera prostokatne regiony.

Jesli na aktywnej klatce region ma frame-scoped geometrie, UI pyta o zakres edycji:

- `Current frame range` - zmienia tylko aktywna geometrie dla jej zakresu klatek.
- `Logical region` - zmienia bazowy logiczny region.

### Delete Selected Region

Usuwa zaznaczony logiczny region:

- z listy regionow,
- z overlayu,
- z projektu,
- z powiazanych zakresow frame-scoped,
- z powiazanych kopii `CopiedAnalysisRegion`.

### Copy Selected to Series

Kopiuje zaznaczony region na cala aktualna robocza serie z ta sama geometria.

To nie uzywa rejestracji. Wspolrzedne sa kopiowane w `native coordinates`.

Przyklad API:

```python
copied = workspace.copy_analysis_region_to_series("Terrace 1")
print(copied.working_frame_indices)
```

### Apply Selected to Current Frame

Tworzy frame-scoped geometrie zaznaczonego regionu tylko dla aktualnej klatki roboczej.

W praktyce oznacza to, ze aktywna geometria regionu dla tej jednej klatki jest zapisana jawnie w `frame_scoped_analysis_regions`.

### Copy Selected from Current to End

Tworzy frame-scoped geometrie zaznaczonego regionu dla zakresu:

```text
current working frame -> last working frame
```

Przyklad:

Jesli aktywna klatka to `Working 19`, a seria ma 50 klatek, zakres obejmie:

```text
19, 20, 21, ..., 49
```

### Copy Selected to Frame Range...

Tworzy frame-scoped geometrie zaznaczonego regionu dla recznie podanego zakresu klatek.

Opcje dialogu:

- `Start frame` - pierwszy `Working Frame Index`.
- `End frame` - ostatni `Working Frame Index`.

Zakres jest inkluzywny.

Przyklad:

```text
Start frame = 19
End frame = 49
```

Oznacza klatki:

```text
19, 20, ..., 49
```

## Regiony aktywne na zakresach klatek

Do tego sluzy `FrameScopedAnalysisRegion`.

Pozwala opisac jeden logiczny region, np. `Terrace 1`, przez kilka geometrii aktywnych w roznych fragmentach serii.

Przyklad koncepcyjny:

```text
Terrace 1, geometria A: frames 0-18
Terrace 1, geometria B: frames 19-49
```

Przyklad API:

```python
from moltrack.core import AnalysisRegion, FrameScopedAnalysisRegion

terrace_a = AnalysisRegion.rectangle(
    kind="terrace",
    name="Terrace 1",
    color_rgb=(20, 120, 240),
    rect_xyxy=(0.0, 0.0, 100.0, 100.0),
)

terrace_b = AnalysisRegion.rectangle(
    kind="terrace",
    name="Terrace 1",
    color_rgb=(20, 120, 240),
    rect_xyxy=(20.0, 5.0, 120.0, 105.0),
)

project = project.with_frame_scoped_analysis_regions(
    (
        FrameScopedAnalysisRegion(region=terrace_a, working_frame_indices=tuple(range(0, 19))),
        FrameScopedAnalysisRegion(region=terrace_b, working_frame_indices=tuple(range(19, 50))),
    )
)

active = project.region_for_working_frame("Terrace 1", 25)
```

Warunki:

- zakresy tej samej logicznej nazwy nie moga nachodzic na te same klatki,
- geometria jest przechowywana w natywnych wspolrzednych klatki,
- przy zmianie aktywnej klatki UI przerysowuje overlay na geometrie aktywna dla tej klatki,
- przy usunieciu working frame zakresy sa remapowane do nowych indeksow.

## Typowy workflow: kilka geometrii dla jednego tarasu

Przyklad: obraz przesuwa sie po klatce 18 i `Terrace 1` musi miec inna geometrie od klatki 19.

1. Zaimportuj serie.
2. Na klatce 0 dodaj `Terrace 1` przez `Draw Rect ROI` albo `Add Rect Region...`.
3. Przejdz do klatki 19.
4. Uzyj `Draw Rect ROI` albo `Draw Polyline Region`.
5. Dopasuj nowa geometrie.
6. Kliknij `Commit Drawn Region...`.
7. Wpisz ta sama nazwe: `Terrace 1`.
8. W dialogu zakresu ustaw:

```text
Start frame = 19
End frame = ostatnia klatka
```

Od tej pory:

- dla klatek przed 19 uzywana jest bazowa geometria,
- od klatki 19 uzywana jest nowa geometria,
- metryki w przyszlych krokach beda mogly agregowac po nazwie `Terrace 1`, ale dla kazdej klatki brac aktywna geometrie.

## Priorytety i overlap regionow

Aktualne sortowanie aktywnych regionow uzywa priorytetu:

1. `ignore`
2. `step_edge`
3. `terrace`
4. `custom`

`ignore` ma pozostac najwyzszym priorytetem przy przyszlym przypisywaniu detekcji i metryk.

UI ostrzega, gdy aktywne regiony typu `terrace` nachodza na siebie w tym samym zakresie klatek. Obecna walidacja overlapu jest oparta o bounds regionow, wiec jest konserwatywna dla polygonow.

## Rejestracja obrazow

MolTrack ma opcjonalny workflow rejestracji globalnej XY. Rejestracja nie wykonuje lokalnego warp/morphingu; wynik to jeden shift `dx, dy` dla kazdej klatki roboczej.

Workflow uzywa technicznie backendu rejestracji z NanoTrack, ale zapisuje wynik jako MolTrackowe `RegistrationShift`.

Menu:

```text
Registration -> Run Registration
```

W pasku narzedzi jest selektor backendu rejestracji:

```text
Registration: Phase | Optical Flow
```

Obecnie MolTrack celowo udostepnia tylko dwa backendy z NanoTrack:

- `Phase` -> `phase_correlation`,
- `Optical Flow` -> `optical_flow_median`.

Domyslne ustawienia:

```text
backend = phase_correlation
registration_view = raw
reference_strategy = adjacent
```

Po wykonaniu rejestracji:

- `MolTrackProject.registration_shifts` zawiera shifty dla klatek roboczych,
- UI automatycznie wlacza `Show Expanded Aligned`,
- podczas obliczen UI pokazuje modalny dialog postepu `Registration`,
- aktualny projekt moze zostac zapisany do `.moltrack`,
- etykieta aktywnej klatki pokazuje shift, np.:

```text
Working 2/3 | Source 2/3 | Registration dx=1.250px dy=-0.500px | Expanded aligned view
```

### Expanded aligned view

Po wyznaczeniu shiftow mozna wlaczyc albo wylaczyc widok expanded aligned:

```text
Registration -> Show Expanded Aligned
```

To jest checkowalna opcja UI. Po wlaczeniu:

- viewer pokazuje obraz aktywnej klatki po zastosowaniu globalnego `dx/dy` na wiekszym canvasie,
- canvas jest powiekszany o padding wyliczony z maksymalnych dodatnich i ujemnych shiftow,
- przesuniete krawedzie obrazu nie sa obcinane,
- etykieta klatki zawiera `Expanded aligned view`,
- regiony nadal sa przechowywane w native coordinates,
- overlaye regionow sa rysowane jako derived geometry przesunieta o `frame_origin_xy` aktywnej klatki w expanded canvas.

Dodawanie i kopiowanie regionow w expanded aligned view:

- ROI/prostokaty/polyline rysowane w expanded view sa traktowane jako wspolrzedne expanded canvasu,
- przy zapisie do projektu nowo rysowana geometria jest konwertowana do native coordinates aktywnej klatki przez odjecie jej `frame_origin_xy`,
- w prawym panelu `Regions` dostepny jest selector `Expanded region mode`, ktory kontroluje kopiowanie i aplikowanie regionow przy wlaczonym `Show Expanded Aligned`.

Tryby `Expanded region mode`:

- `Fixed expanded canvas` - nowy ROI/poly oraz `Add Rect Region...` od razu tworza frame-scoped geometrie dla calej serii. `Copy Selected to Series`, `Copy Selected from Current to End`, `Copy Selected to Frame Range...` oraz `Apply Selected to Current Frame` tez tworza frame-scoped geometrie przeliczone osobno dla kazdej klatki. Wizualnie region pozostaje w tym samym miejscu expanded canvasu, a obrazy przesuwaja sie pod nim zgodnie z rejestracja.
- `Move with image` - region jest kopiowany/aplikowany jako ta sama native geometry. W expanded view overlay dostaje `frame_origin_xy`, wiec przesuwa sie razem z obrazem.

Wylaczenie opcji wraca do natywnego obrazu bez zmiany danych projektu.

Ograniczenia:

- rejestracja wymaga, aby projekt mial zaladowane obrazy w `SourceImageSeries.raw_frames`,
- projekt otwarty z `.moltrack` nie ma aktualnie obrazow w bundle, wiec bez ponownego importu/zaladowania zrodla nie uruchomi rejestracji,
- bbox/centroid detekcji nie sa jeszcze dostepne, bo `MolecularDetection` zaczyna sie w kolejnym bloku planu.

Przyklad API:

```python
from moltrack.registration import run_project_registration
from moltrack.registration import expanded_registered_working_stack
from moltrack.registration import registered_working_frame, registered_working_stack

registered_project = run_project_registration(
    project,
    backend="phase_correlation",
    registration_view="raw",
)

flow_registered_project = run_project_registration(
    project,
    backend="optical_flow_median",
    registration_view="raw",
)

shift = registered_project.registration_shift_for_working_frame(1)
frame = registered_working_frame(registered_project, 1)
stack = registered_working_stack(registered_project)
expanded = expanded_registered_working_stack(registered_project)
expanded_frame = expanded.frames[1]
origin_xy = expanded.frame_origins_xy[1]
```

### Registered coordinates dla przyszlego linkingu

Dane domenowe pozostaja zapisane w `native coordinates`. Gdy rejestracja jest dostepna, kod linkingu moze pracowac na wspolrzednych widoku registered jako wartosci pochodnej.

Publiczne helpery:

```python
from moltrack.registration import (
    linking_xy,
    native_bbox_to_registered_xyxy,
    native_to_registered_xy,
    registered_bbox_to_native_xyxy,
    registered_to_native_xy,
)

centroid_native = (5.0, 7.0)
centroid_registered = native_to_registered_xy(project, 1, centroid_native)
centroid_native_again = registered_to_native_xy(project, 1, centroid_registered)

bbox_native = (10.0, 20.0, 30.0, 40.0)
bbox_registered = native_bbox_to_registered_xyxy(project, 1, bbox_native)
bbox_native_again = registered_bbox_to_native_xyxy(project, 1, bbox_registered)

candidate_position = linking_xy(project, 1, centroid_native)
native_candidate_position = linking_xy(project, 1, centroid_native, use_registered=False)
```

Semantyka:

- `native_to_registered_xy` i `registered_to_native_xy` obsluguja pojedynczy punkt `(x, y)` oraz tablice punktow o ksztalcie `(N, 2)`,
- bboxy sa transformowane jako `(x0, y0, x1, y1)` przez dodanie albo odjecie tego samego `dx/dy`,
- brak shiftu nie blokuje podstawowej analizy: domyslnie helpery zwracaja wspolrzedne bez przesuniecia,
- `require_shift=True` wymusza blad, jesli dla klatki nie ma `RegistrationShift`,
- `linking_xy(..., use_registered=True)` uzywa registered coordinates tylko wtedy, gdy shift jest dostepny; bez rejestracji zachowuje native coordinates,
- `linking_xy(..., use_registered=False)` zawsze zwraca native coordinates.

To przygotowuje przyszly linker bez wymuszania rejestracji dla zwyklej analizy.

## Publiczne klasy i API

Najwazniejsze publiczne importy:

```python
from moltrack.core import (
    AnalysisRegion,
    AnalysisRegionKind,
    CopiedAnalysisRegion,
    FrameScopedAnalysisRegion,
    MolTrackProject,
    RegistrationShift,
    SourceImageSeries,
    WorkingFrame,
    WorkingImageSeries,
)
```

### SourceImageSeries

Opisuje serie zrodlowa.

Najwazniejsze pola:

- `source_uri`
- `source_uris`
- `display_name`
- `frame_count`
- `raw_frames`
- `metadata`

Przyklad:

```python
from moltrack.core import SourceImageSeries

source = SourceImageSeries(
    source_uri="movie.mpp",
    frame_count=4,
    display_name="movie.mpp",
)
```

### WorkingImageSeries

Opisuje roboczy porzadek klatek.

Przyklad:

```python
working = source.create_working_series(reverse_frame_order=True)
print(working.source_frame_indices())
```

### MolTrackProject

Projekt laczy serie zrodlowa, serie robocza i stan analizy.

Przyklad:

```python
from moltrack.core import MolTrackProject

project = MolTrackProject.from_source_series(source, project_name="experiment A")
project = project.remove_working_frame(1)
```

### CopiedAnalysisRegion

Oznacza region uzywany na wielu klatkach bez zmiany geometrii.

Przyklad:

```python
from moltrack.core import CopiedAnalysisRegion

copied = CopiedAnalysisRegion.from_working_series(terrace, project.working_series)
```

### FrameScopedAnalysisRegion

Oznacza konkretna geometrie regionu aktywna tylko na wybranych klatkach roboczych.

Przyklad:

```python
from moltrack.core import FrameScopedAnalysisRegion

scoped = FrameScopedAnalysisRegion(
    region=terrace,
    working_frame_indices=(0, 1, 2),
)
```

### RegistrationShift

Opisuje opcjonalne globalne przesuniecie XY dla jednej klatki roboczej. Model zawiera tylko translacje `dx`, `dy`; nie przechowuje lokalnego flow, morphingu ani macierzy affine.

Przyklad:

```python
from moltrack.core import RegistrationShift

shift = RegistrationShift(
    working_frame_index=2,
    dx=1.25,
    dy=-0.5,
    method="phase_correlation",
)

print(shift.shift_xy)
```

Shifty moga byc zapisane w stanie `MolTrackProject` i sa round-tripowane przez `.moltrack`:

```python
project = project.with_registration_shifts(
    (
        RegistrationShift(working_frame_index=0, dx=0.0, dy=0.0, method="reference"),
        RegistrationShift(working_frame_index=1, dx=1.2, dy=-0.4, method="phase_correlation"),
    )
)

shift = project.registration_shift_for_working_frame(1)
missing = project.registration_shift_for_working_frame(2)
```

Warunki:

- `working_frame_index` musi istniec w `WorkingImageSeries`,
- dla jednej klatki roboczej moze istniec najwyzej jeden shift,
- `dx` i `dy` musza byc skonczone,
- brak shiftu oznacza, ze rejestracja dla tej klatki nie zostala jeszcze wyznaczona.

## YOLO detect current frame

Menu:

```text
YOLO -> Detect Current Frame
YOLO -> Detect Current Frame in Selected ROI
YOLO -> Detect All Working Frames
YOLO -> Detect Selected ROI on Frame Range...
```

Po wybraniu dowolnej akcji `Detect...` otwierany jest dialog `YOLO Detection Options`.
Dialog pozwala wybrac checkpoint i parametry wykrywania, a detekcja startuje dopiero po `OK`:

```text
nanotrack/yolo_models
```

Opcje:

- lista modeli pokazuje checkpointy znalezione w `nanotrack/yolo_models`,
- `Refresh Models` ponownie skanuje katalog checkpointow,
- `Conf` ustawia prog confidence przekazywany do YOLO,
- `IoU` ustawia prog NMS IoU przekazywany do YOLO,
- `Device` jest lista `Auto`, `CPU`, `GPU`; `GPU` przekazuje do runtime `cuda:0`.

Wszystkie akcje z menu `YOLO` uzywaja modelu i parametrow zaakceptowanych w dialogu.
Ostatnio zaakceptowany model i parametry sa pamietane jako domyslne wartosci kolejnego dialogu.

Kontrakt:

- runtime jest zgodny z `nanotrack.yolo.YoloRuntime.predict_frame(...)`,
- wejscie do runtime to natywna aktywna klatka z `SourceImageSeries`,
- bboxy sa zapisywane jako `MolecularDetection` w native coordinates,
- domyslny status detekcji YOLO to `candidate`,
- `backend_name = "yolo"`,
- `run_mode = "full_frame"`,
- pelnoklatkowy run usuwa tylko poprzednie detekcje `yolo/candidate` z aktywnej klatki,
- detekcje `accepted`, `manual` oraz inne nie-kandydackie zostaja zachowane,
- viewer rysuje bboxy jako zolte prostokatne overlaye.

Tryb `Detect Current Frame in Selected ROI`:

- wymaga zaznaczenia regionu na liscie regionow,
- obsluguje regiony `rect` i `polygon`,
- uzywa aktywnej geometrii regionu dla biezacej klatki, w tym geometrii frame-scoped,
- nadal przekazuje do runtime cala natywna klatke, bez cropowania,
- filtruje wynik po centroidzie bboxa w ROI,
- zapisuje nowe bboxy w pelnych native coordinates calej klatki,
- nie przycina bboxow do granicy ROI,
- usuwa/podmienia tylko istniejace detekcje na aktywnej klatce, ktorych centroid lezy w ROI,
- zostawia bez zmian detekcje poza ROI oraz detekcje na innych klatkach,
- zapisuje `run_mode = "roi_replace"` i `region_name` wskazujacy uzyty region.

Tryb `Detect All Working Frames`:

- iteruje po `WorkingImageSeries.frames`, dlatego klatki usuniete z serii roboczej nie sa przetwarzane,
- dla kazdej klatki przekazuje do runtime natywna klatke z odpowiadajacym `source_frame_index`,
- zapisuje wyniki jako `MolecularDetection` z `run_mode = "full_frame"`,
- wynik metody aplikacyjnej jest slownikiem `working_frame_index -> tuple[MolecularDetection, ...]`,
- dla przetworzonych klatek podmienia poprzednie detekcje `yolo/candidate`,
- zachowuje detekcje zaakceptowane/manualne oraz detekcje z klatek, ktore nie zostaly przetworzone,
- UI pokazuje dialog postepu i pozwala przerwac batch; po przerwaniu w projekcie zostaja wyniki juz ukonczonych klatek.

Tryb `Detect Selected ROI on Frame Range...`:

- wymaga zaznaczenia regionu na liscie regionow,
- pyta o zakres working frame przez dialog start/end,
- dla kazdej przetwarzanej klatki pobiera aktywna geometrie przez `project.region_for_working_frame(region_name, working_frame_index)`,
- dzieki temu obsluguje regiony frame-scoped po rejestracji i trybie `Fixed expanded canvas`,
- runtime nadal dostaje cala natywna klatke,
- nowe bboxy sa filtrowane po centroidzie wewnatrz aktywnego ROI danej klatki,
- bboxy pozostaja w pelnych native coordinates calej klatki,
- dla kazdej przetworzonej klatki podmieniane sa tylko istniejace detekcje, ktorych centroid lezy w aktywnym ROI tej klatki,
- detekcje poza ROI i detekcje na nieprzetworzonych klatkach zostaja zachowane,
- UI pokazuje dialog postepu z Cancel; po przerwaniu zapisane sa wyniki juz ukonczonych klatek.

Detekcje sa trzymane w `MolTrackProject.molecular_detections` i zapisywane w manifestcie `.moltrack` jako `molecular_detections`.
Panel boczny jest podzielony na sekcje:

- `Regions` - tryb regionow expanded/aligned i lista regionow aktywnej klatki,
- `Region Actions` - tworzenie, edycja, kasowanie i kopiowanie regionow,
- `Detections` - lista detekcji aktywnej klatki,
- `Manual Detection` - reczne dodawanie bboxa,
- `Review Current Frame` - zbiorcze zatwierdzanie detekcji na aktywnej klatce,
- `Delete Current Frame` - zbiorcze usuwanie detekcji aktywnej klatki,
- `Scale BBoxes` - zbiorcze skalowanie bboxow.

Kazda wazna kontrolka ma tooltip. Panel jest przewijany, zeby przy mniejszym oknie nie upychac wszystkich opcji w jednej nieczytelnej kolumnie.

Lista `Detections` pokazuje detekcje aktywnej klatki. Kazdy wpis pokazuje:

- `detection_id`,
- `review_status`,
- `confidence`,
- `region_name` albo `-`.

Po kliknieciu detekcji jej bbox jest przerysowany w viewerze jako zaznaczony overlay.
`Assign Regions` przypisuje detekcje z calej roboczej serii do aktywnych regionow po centroidzie bboxa. Dla kazdej klatki uzywana jest geometria regionu aktywna dla tej working frame. Gdy centroid lezy w kilku regionach, priorytet ma `ignore`, potem `step_edge`, `terrace` i `custom`. Detekcja przypisana do regionu `ignore` pozostaje w projekcie, ale nie wchodzi do domyslnej analizy.

Pojedyncze akcje bboxa sa dostepne przez prawy klik na bbox w viewerze:

- `Accept` ustawia status zaznaczonej detekcji na `accepted`,
- `Reject` ustawia status zaznaczonej detekcji na `rejected`,
- `Uncertain` ustawia status zaznaczonej detekcji na `uncertain`,
- `Edit BBox...` otwiera dialog edycji wspolrzednych,
- `Scale BBox...` otwiera dialog skali dla jednego bboxa,
- `Delete` usuwa wskazana detekcje.

W panelu `Review Detections` sa dostepne akcje zbiorcze:

- `Accept Current` ustawia status `accepted` dla wszystkich detekcji aktywnej klatki,
- `Accept All Frames` ustawia status `accepted` dla wszystkich detekcji ze wszystkich working frames,
- `Conf >= ...` ustawia prog confidence dla akcji zbiorczej,
- `Accept Above Conf` ustawia status `accepted` tylko dla detekcji aktywnej klatki z `confidence >= prog`.

Pod lista sa tez akcje recznego dodawania:

- `Draw BBox` tworzy edytowalny prostokat bbox na aktualnym widoku,
- `Commit Manual` zapisuje bbox jako `MolecularDetection` na aktywnej klatce,
- reczna detekcja ma `review_status = manual`, `backend_name = manual`, `model_name = manual`, `confidence = 1.0`,
- bbox jest zapisywany w native coordinates; jesli widok jest expanded/aligned, wspolrzedne sa przeliczane z canvasu expanded do natywnego ukladu aktywnej klatki.

Akcje dla pojedynczego bboxa:

- prawy klik na bbox na viewerze zaznacza detekcje i otwiera menu kontekstowe,
- menu kontekstowe zawiera `Accept`, `Reject`, `Uncertain`, `Edit BBox...`, `Scale BBox...` i `Delete`,
- `Edit BBox...` otwiera dialog wspolrzednych bboxa i zapisuje zmiane w tej samej detekcji,
- `Scale BBox...` otwiera dialog skali i skaluje tylko wskazana detekcje,
- `Delete` usuwa tylko wskazana detekcje,
- jesli edytowana detekcja miala status `candidate` albo `accepted`, status zmienia sie na `edited`,
- detekcje `manual`, `rejected`, `uncertain` i juz `edited` zachowuja swoj status po zmianie bboxa,
- edytowany bbox jest zapisywany w native coordinates.

Akcje zbiorcze bboxow w panelu bocznym:

- lista statusow i `Delete Status` usuwaja detekcje o wybranym statusie tylko z aktywnej klatki,
- `Delete in Region` usuwa z aktywnej klatki detekcje, ktorych centroid bboxa lezy wewnatrz zaznaczonego regionu,
- `Scale x ...` ustawia mnoznik skali bboxa,
- `Scale Current` skaluje wszystkie detekcje aktywnej working frame,
- `Scale All` skaluje detekcje ze wszystkich working frames,
- `Accept Current` ustawia status `accepted` dla wszystkich detekcji aktywnej klatki,
- `Accept All Frames` ustawia status `accepted` dla wszystkich detekcji ze wszystkich working frames,
- `Accept Above Conf` ustawia status `accepted` dla detekcji aktywnej klatki powyzej progu confidence,
- kasowanie wewnatrz regionu uzywa aktywnej geometrii regionu dla biezacej working frame,
- skalowanie jest wykonywane wzgledem srodka kazdego bboxa,
- skalowanie traktowane jest jak edycja bboxa: status `candidate` albo `accepted` przechodzi na `edited`, a statusy `manual`, `rejected`, `uncertain` i `edited` pozostaja bez automatycznej zmiany.

## Population Metrics

`PopulationMetrics.from_project(project)` tworzy tabele metryk populacyjnych per working frame i per aktywny region analizy.

Kazdy wiersz `PopulationMetricRow` zawiera:

- `working_frame_index` i `source_frame_index`,
- `region_name` i `region_kind`,
- `detection_count`,
- `region_area_px2`,
- `detection_footprint_area_px2`,
- `density_per_px2`,
- `detection_footprint_coverage`.

Domyslnie liczone sa tylko detekcje w domyslnej analizie, czyli statusy `accepted`, `edited` i `manual`. Detekcje `candidate`, `rejected` i `uncertain` sa pominiete. Detekcje przypisane do regionu `ignore` tez sa pominiete, nawet jesli maja status `accepted`, `edited` albo `manual`.

Jezeli detekcja ma zapisane `region_name`, metryki uzywaja tego przypisania. Jezeli `region_name` jest puste, metryki tymczasowo przypisuja detekcje do aktywnego regionu po centroidzie bboxa. Projekt nie jest przez to zmieniany, ale wyniki po `YOLO Detect All` z regionem obejmujacym cala klatke sa liczone bez recznego naciskania `Assign Regions`.

Wiersze sa tworzone dla aktywnych regionow innych niz `ignore`, rowniez gdy count wynosi zero. Dla regionow z wieloma geometriami na roznych working frames uzywana jest geometria aktywna dla danej klatki. Density jest liczone jako `detection_count / region_area_px2`, a coverage jako `suma pol bboxow / region_area_px2`.

## Population Metrics Window

Okno `Results -> Population Metrics...` pokazuje trzy wykresy populacyjne:

- count vs working frame,
- density vs working frame,
- detection footprint coverage vs working frame.

Opcja `All regions` agreguje aktywne regiony inne niz `ignore` per working frame:

- count jest suma `detection_count`,
- density jest liczone jako `suma count / suma area`,
- coverage jest liczone jako `suma footprint area / suma area`.

Po wyborze konkretnego regionu dialog pokazuje te same trzy serie tylko dla tego regionu. Dane pochodza z `PopulationMetrics.from_project(project)`, wiec obowiazuje ten sam filtr domyslnej analizy: `accepted`, `edited` i `manual`; bez `candidate`, `rejected`, `uncertain` oraz bez regionow `ignore`.

## Centroid Nearest-Neighbour Metrics

`CentroidNearestNeighbourMetrics.from_project(project)` liczy rozklad odleglosci najblizszego sasiada z centroidow bboxow `MolecularDetection`.

Metryki sa liczone per working frame i per aktywny region analizy inny niz `ignore`. Kazdy wiersz `CentroidNearestNeighbourMetricRow` zawiera:

- `working_frame_index` i `source_frame_index`,
- `region_name` i `region_kind`,
- `detection_count`,
- `nearest_neighbour_count`,
- `nearest_neighbour_distances_px`,
- `mean_nearest_neighbour_distance_px`,
- `median_nearest_neighbour_distance_px`.

Obowiazuje ten sam filtr domyslnej analizy co w metrykach populacyjnych: liczone sa tylko `accepted`, `edited` i `manual`. Detekcje `candidate`, `rejected` i `uncertain` sa pominiete. Detekcje z regionow `ignore` sa pominiete. Jezeli detekcja nie ma zapisanego `region_name`, metryki tymczasowo przypisuja region po centroidzie bboxa bez mutowania projektu.

Odleglosci sa wyrazone w pikselach natywnego ukladu klatki. Dla regionu z mniej niz dwiema detekcjami rozklad jest pusty, a srednia i mediana wynosza `0.0`.

## Molecular Row Orientation Metrics

`MolecularRowOrientationMetrics.from_project(project)` estymuje dominujaca orientacje rzedow molekul z centroidow bboxow `MolecularDetection`.

Metryki sa liczone per working frame i per aktywny region analizy inny niz `ignore`. Kazdy wiersz `MolecularRowOrientationMetricRow` zawiera:

- `working_frame_index` i `source_frame_index`,
- `region_name` i `region_kind`,
- `detection_count`,
- `orientation_degrees`,
- `orientation_confidence`.

Orientacja jest liczona metoda PCA na centroidach w natywnym ukladzie klatki. `orientation_degrees` jest katem w stopniach w zakresie `[0, 180)`: `0` oznacza rzad poziomy, `90` pionowy, a `45` przekatna w dol-prawo w ukladzie obrazu. `orientation_confidence` jest anizotropia PCA liczona jako `1 - lambda_minor / lambda_major`, obcieta do zakresu `0..1`.

Obowiazuje ten sam filtr domyslnej analizy co w metrykach populacyjnych: liczone sa tylko `accepted`, `edited` i `manual`; `candidate`, `rejected`, `uncertain` oraz regiony `ignore` sa pominiete. Jezeli detekcja nie ma zapisanego `region_name`, metryki tymczasowo przypisuja region po centroidzie bboxa bez mutowania projektu.

Dla regionu z mniej niz dwiema detekcjami `orientation_degrees = 0.0` i `orientation_confidence = 0.0`.

## Molecular Row Spacing Metrics

`MolecularRowSpacingMetrics.from_project(project)` estymuje odstep miedzy rzedami molekul z centroidow bboxow `MolecularDetection`.

Metryki sa liczone per working frame i per aktywny region analizy inny niz `ignore`. Kazdy wiersz `MolecularRowSpacingMetricRow` zawiera:

- `working_frame_index` i `source_frame_index`,
- `region_name` i `region_kind`,
- `detection_count`,
- `orientation_degrees`,
- `row_count`,
- `row_spacing_px`.

Najpierw liczona jest orientacja rzedow ta sama metoda PCA co w `MolecularRowOrientationMetrics`. Nastepnie centroidy sa projektowane na normalna do tej orientacji. Unikalne pozycje projekcji sa traktowane jako pozycje rzedow, a `row_spacing_px` jest mediana odstepow miedzy kolejnymi pozycjami rzedow.

Odstep jest wyrazony w pikselach natywnego ukladu klatki. Obowiazuje ten sam filtr domyslnej analizy: liczone sa tylko `accepted`, `edited` i `manual`; `candidate`, `rejected`, `uncertain` oraz regiony `ignore` sa pominiete. Jezeli detekcja nie ma zapisanego `region_name`, metryki tymczasowo przypisuja region po centroidzie bboxa bez mutowania projektu.

Dla regionu z mniej niz dwiema pozycjami rzedow `row_spacing_px = 0.0`.

## Molecular Row Order Metrics

`MolecularRowOrderMetrics.from_project(project)` liczy pierwszy centroidowy `Molecular Row Order` score bez uzywania masek.

Metryki sa liczone per working frame i per aktywny region analizy inny niz `ignore`. Kazdy wiersz `MolecularRowOrderMetricRow` zawiera:

- `working_frame_index` i `source_frame_index`,
- `region_name` i `region_kind`,
- `detection_count`,
- `assigned_detection_count`,
- `orientation_degrees`,
- `row_count`,
- `row_spacing_px`,
- `row_order_score`.

`row_order_score` ma zakres `0..1`. Wynik laczy trzy skladniki:

- jaki udzial detekcji da sie przypisac do pasm rzędow,
- jak blisko centroidy leza swoich pasm projekcji,
- jak regularne sa odstepy miedzy pasmami rzędow.

Orientacja pochodzi z tej samej estymacji PCA co `MolecularRowOrientationMetrics`. Centroidy sa projektowane na normalna do orientacji, a projekcje sa grupowane w pasma z tolerancja `1.0 px`. Rzad musi miec co najmniej dwie detekcje, zeby byl traktowany jako potwierdzony rzad.

Obowiazuje ten sam filtr domyslnej analizy: liczone sa tylko `accepted`, `edited` i `manual`; `candidate`, `rejected`, `uncertain` oraz regiony `ignore` sa pominiete. Jezeli detekcja nie ma zapisanego `region_name`, metryki tymczasowo przypisuja region po centroidzie bboxa bez mutowania projektu.

Ograniczenia: to pierwsza metryka centroidowa dla czystych, w przyblizeniu prostych rzędow. Nie uzywa masek, nie rozdziela wielu orientacji w jednym regionie i nie modeluje zakrzywionych domen. Przy duzym szumie pozycji, silnych defektach albo pojedynczych detekcjach na potencjalnych rzędach score moze zanizac uporzadkowanie.

## Row Order Metrics Window

Okno `Results -> Row Order Metrics...` pokazuje trzy wykresy metryk uporzadkowania rzędow:

- row order vs working frame,
- row orientation vs working frame,
- row spacing vs working frame.

Opcja `All regions` agreguje aktywne regiony per working frame jako srednia wazona liczba detekcji:

- `row_order_score` jest srednia wazona `detection_count`,
- `orientation_degrees` jest srednia wazona `detection_count`,
- `row_spacing_px` jest srednia wazona `detection_count`.

Po wyborze konkretnego regionu dialog pokazuje te same trzy serie tylko dla tego regionu. Dane pochodza z `MolecularRowOrderMetrics.from_project(project)`, wiec obowiazuje filtr domyslnej analizy: `accepted`, `edited` i `manual`; bez `candidate`, `rejected`, `uncertain` oraz bez regionow `ignore`.

## Detections CSV Export

`File -> Export Detections CSV...` zapisuje wszystkie detekcje z projektu do pliku `.csv`. Ten eksport nie uzywa filtra domyslnej analizy, wiec zawiera rowniez `candidate`, `rejected` i `uncertain`.

Kolumny:

- `working_frame_index`,
- `source_frame_index`,
- `detection_id`,
- `review_status`,
- `bbox_x0`, `bbox_y0`, `bbox_x1`, `bbox_y1`,
- `centroid_x`, `centroid_y`,
- `confidence`,
- `model_name`,
- `region_name`.

Detekcje sa zapisywane deterministycznie wedlug `working_frame_index`, `source_frame_index` i `detection_id`. Puste `region_name` oznacza detekcje bez przypisanego regionu.

## Regional Metrics CSV Export

`File -> Export Regional Metrics CSV...` zapisuje metryki populacyjne per working frame i per aktywny region do pliku `.csv`. Eksport korzysta z `PopulationMetrics.from_project(project)`, wiec obowiazuje filtr domyslnej analizy: liczone sa tylko `accepted`, `edited` i `manual`; pominiete sa `candidate`, `rejected`, `uncertain` oraz regiony `ignore`.

Kolumny:

- `working_frame_index`,
- `source_frame_index`,
- `region_name`,
- `region_kind`,
- `detection_count`,
- `region_area_px2`,
- `detection_footprint_area_px2`,
- `density_per_px2`,
- `detection_footprint_coverage`.

Wiersze sa zapisywane w kolejnosci zwracanej przez `PopulationMetrics`, czyli per working frame i aktywny region inny niz `ignore`. Region bez detekcji nadal daje wiersz z `detection_count = 0`.

## Row Order Metrics CSV Export

`File -> Export Row Order Metrics CSV...` zapisuje metryki uporzadkowania rzedow per working frame i per aktywny region do pliku `.csv`. Eksport korzysta z `MolecularRowOrderMetrics.from_project(project)`, wiec obowiazuje filtr domyslnej analizy: liczone sa tylko `accepted`, `edited` i `manual`; pominiete sa `candidate`, `rejected`, `uncertain` oraz regiony `ignore`.

Kolumny:

- `working_frame_index`,
- `source_frame_index`,
- `region_name`,
- `region_kind`,
- `detection_count`,
- `assigned_detection_count`,
- `orientation_degrees`,
- `row_count`,
- `row_spacing_px`,
- `row_order_score`.

Wiersze sa zapisywane w kolejnosci zwracanej przez `MolecularRowOrderMetrics`, czyli per working frame i aktywny region inny niz `ignore`. Eksport dziedziczy ograniczenia metryki centroidowej: uzywa centroidow bboxow, nie masek, i najlepiej opisuje czyste, w przyblizeniu proste rzedy w jednym dominujacym kierunku.

## Project Summary CSV Export

`File -> Export Project Summary CSV...` zapisuje podsumowanie projektu jako tabele `metric,value`.

Eksport zawiera:

- `project_name`,
- `source_frame_count`,
- `working_frame_count`,
- `removed_source_frame_count`,
- `removed_source_frame_indices`,
- `detection_count_total`,
- `detection_count_candidate`,
- `detection_count_accepted`,
- `detection_count_edited`,
- `detection_count_rejected`,
- `detection_count_manual`,
- `detection_count_uncertain`,
- `yolo_model_count`,
- `yolo_models`.

`removed_source_frame_indices` i `yolo_models` sa zapisywane jako wartosci rozdzielone srednikiem. Modele YOLO sa zbierane z detekcji, dla ktorych `backend_name = "yolo"`, sortowane i deduplikowane.

## YOLO Labels Export

`File -> Export YOLO Labels...` zapisuje katalog etykiet YOLO bbox. Eksport tworzy jeden plik `.txt` na working frame:

```text
working_0000_source_0000.txt
working_0001_source_0001.txt
```

Kazda linia ma standardowy format YOLO:

```text
class_id x_center y_center width height
```

`x_center`, `y_center`, `width` i `height` sa normalizowane do rozmiaru obrazu z `SourceImageSeries.raw_frames`. Jezeli projekt nie ma zaladowanych obrazow zrodlowych, eksport wymaga jawnego rozmiaru obrazu w publicznym API `export_yolo_labels(...)`.

Tryby:

- `Accepted / edited / manual` - domyslny tryb eksportu statusow `accepted`, `edited` i `manual`,
- `Candidate / uncertain` - osobny tryb eksportu statusow `candidate` i `uncertain`.

Status `rejected` nie jest eksportowany w zadnym z tych trybow. Domyslny `class_id` to `0`.

Round-trip zachowuje:

- `detection_id`,
- `working_frame_index` i `source_frame_index`,
- `bbox_xyxy`,
- `confidence`,
- `model_name`,
- `review_status`,
- `backend_name`,
- `run_mode`,
- `region_name`,
- `coordinate_system`.

## Aktualne ograniczenia

Na tym etapie nie ma jeszcze:

- metryk uporzadkowania rzedow,
- masek instancji,
- SAM2/DAM4SAM/SAMURAI/micro-sam w MolTrack,
- Trackastry,
- UI do usuwania klatek z serii roboczej.

Te elementy sa zaplanowane od kroku 14 dalej.
