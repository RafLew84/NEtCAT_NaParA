# MolTrack - dokumentacja aktualnego zakresu

Ten dokument opisuje funkcjonalnosci dodane do `moltrack` do kroku 42 planu. Aktualny zakres obejmuje fundament aplikacji, import i przegladanie jednej serii obrazow, zapis/odczyt projektu, regiony analizy z geometriami aktywnymi na wybranych klatkach oraz opcjonalny workflow rejestracji globalnych przesuniec XY.

Funkcje detekcji YOLO, review bboxow, metryki, maski i pelny tracking sa nadal etapami planowanymi.

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

## Aktualne ograniczenia

Na tym etapie nie ma jeszcze:

- detekcji molekul YOLO,
- statusow detekcji,
- listy i review detekcji,
- recznej edycji bboxow,
- metryk populacyjnych,
- metryk uporzadkowania rzedow,
- masek instancji,
- SAM2/DAM4SAM/SAMURAI/micro-sam w MolTrack,
- Trackastry,
- eksportow CSV,
- UI do usuwania klatek z serii roboczej.

Te elementy sa zaplanowane od kroku 14 dalej.
