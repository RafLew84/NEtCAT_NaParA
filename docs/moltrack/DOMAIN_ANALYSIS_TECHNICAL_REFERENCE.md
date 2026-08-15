# Domain Analysis — referencja techniczna

**Status:** kontrakt produkcyjny MolTrack 0.1.0; zweryfikowany 2026-08-15

**Interfejs:** C — Spatial Command Center

**Słownik:** [CONTEXT.md](CONTEXT.md)

**Formaty:** [DOMAIN_ANALYSIS_FORMATS.md](DOMAIN_ANALYSIS_FORMATS.md)

## Granica modułów

| Seam | Odpowiedzialność | Stan produkcyjny |
| --- | --- | --- |
| `DomainAnalysisModule.run(...)` | Wykonuje jawnie wybrany `DomainBackendAdapter`, buduje backend-qualified immutable automatic snapshot i pełny funnel | wdrożony dla obu stabilnych backendów |
| `DomainCorrectionModule.initialize/prepare/dispatch/project(...)` | Jest jedynym właścicielem correction history, konfliktów, Undo/Redo, review, rebase i Effective Domain Projection | wdrożony |
| `DomainAnalysisWorkspaceController.snapshot/dispatch(...)` | Udostępnia jeden niemutowalny snapshot UI: analizę, korekty, selection, highlight i prepared preview | wdrożony |
| `save_moltrack_session(...)` / `load_moltrack_session(...)` | Waliduje i atomowo zapisuje/otwiera wersjonowaną sesję; wykonuje migrację i quarantine | session v3; loader v1/v2/v3 |
| `export_analysis_package(...)` | Publikuje v10 correction-aware; v9 pozostaje legacy automatic-only | wdrożony |
| Target-specific Reference Dataset modules | Publikują i czytają niemutowalne M6/Orientation Reference Dataset Version | target schema v2, envelope v2 |
| `M6PresetLibrary` / `M6PresetWorkspace` | Zarządzają saved presets, working copy i jednym active presetem | schema v1; wdrożone |
| `run_lattice_domain_calibration_campaign(...)` | Orkiestruje bounded search, metryki, shortlistę i jednorazową Validation | campaign report v2; wdrożony |
| `MainWindow` + `DomainAnalysisDialog` | Cienko renderują snapshot i wysyłają akcje Controllerowi | produkcyjny wariant C z przewodnikiem Help |

UI, persistence ani eksport nie mogą implementować ponownie reguł projekcji,
review, rebase lub gotowości datasetu. Każda z tych reguł ma jednego właściciela
za publicznym seamem.

## Przepływ stanu

```text
runtime capability catalog + request + frozen preset
                         |
                         v
              DomainAnalysisModule.run
                         |
            immutable automatic snapshot
                         |
                         v
            DomainCorrectionModule  <---- correction commands / review / rebase
                         |
            Effective Domain Projection
                         |
                         v
      DomainAnalysisWorkspaceController.snapshot
        |             |              |             |
        v             v              v             v
      canvas      domain tree    bottom sheet   diagnostics
                         |
        +----------------+------------------+
        |                                   |
        v                                   v
  session v3 / export v10       reference datasets / campaign
```

Katalog capabilities jest własnością runtime. Sesja zapisuje żądane classifier
IDs i zamrożone konfiguracje, ale Open nigdy nie może zastąpić katalogu runtime
listą aktywną w zapisanym drafcie.

## Właściciele stanu

### Automatic snapshot

`DomainAnalysisModule` tworzy immutable wynik z pełną identity backendu,
ustawieniami, algorytm version, native evidence i fingerprintami. Korekta,
Undo/Redo i rebase nie modyfikują tego obiektu. Rerun tworzy pending candidate.

### Correction workspace

`DomainCorrectionModule` przechowuje:

- series-wide Orientation Class Catalog;
- frame-local correction sets i immutable revisions;
- append-only operations, także Undo/Redo;
- stabilne UUID domen ręcznych i tombstones;
- oddzielne M6 oraz Orientation review scopes, decisions i sign-offs;
- pending automatic candidates, rebase diagnostics i aktywną revision;
- status `draft`, `stale`, `conflicted` albo `quarantined`.

Metryki domen nie są mutowalnymi polami correction setu. Powstają przy każdej
projekcji ze źródłowego automatu i historii.

### Workspace Controller

Controller jest jedynym punktem styku UI ze stanem naukowym. Snapshot zawiera
selection i highlight jako osobne wartości, bieżącą oś i target, prepared preview
oraz projekcje dla canvasu, drzewa, ledgeru i diagnostyki. Zmiana selection
unieważnia preview; zmiana highlightu nie może zmienić selection.

Widgety wariantu C nie przechowują równoległych list domen ani lokalnej historii
Undo. Renderują view model i wysyłają typowane akcje przez `dispatch(...)`.

## Kontrakt polecenia korekty

1. `prepare(...)` zamraża `source_id`, oś, target, expected workspace revision i
   automatic fingerprint.
2. Policy klasyfikuje każdy problem jako `blocked`,
   `confirmation_required` lub `informational`.
3. `dispatch(Apply)` odrzuca stale preview oraz niepotwierdzony high impact.
4. Poprawny Apply dopisuje jeden atom obejmujący cały batch. Nie istnieje
   częściowy commit bezkonfliktowego podzbioru.
5. Projekcja jest przeliczana, a dotknięty scope review wraca do `draft`.

Undo/Redo są kolejnymi rekordami historii. Nowy Apply zamyka starą gałąź Redo.
Last applicable command wins tylko na osi, której dotyczy polecenie; M6 nie
nadpisuje Orientation i odwrotnie.

## Rebase

Rerun nie zmienia aktywnego automatu. Jawny rebase przygotowuje mapowanie po
stabilnym `source_id`, fingerprintach i geometrii. Dopasowanie wyłącznie po
współrzędnych lub snapshot-local domain ID jest niedozwolone. Brakujące źródła,
changed geometry oraz split/merge są widocznymi konfliktami. Promocja nowej bazy
i przeniesienie zgodnych decyzji są jednym atomem.

## Review i readiness

M6 i Orientation mają oddzielne scope, decisions, abstentions i sign-off. Każdy
`source_id` w zamrożonym scope musi wystąpić dokładnie raz, również jako
`accepted_automatic`, jawnie niekwalifikujący się lub `Unresolvable` z reason.
Save i Export nie wykonują sign-off.

Readiness jest wyliczana z kompletności i fingerprintów. Nie jest edytowalną
flagą. MolTrack jest narzędziem single-operator, więc kontrakt nie wymaga
`reviewer_id`; zachowuje scope, automatyczny timestamp UTC i fingerprint
podpisanego stanu.

`ReferenceReadinessPolicy` jest jedynym właścicielem target-specific readiness.
`evaluate_snapshot(...)` daje UI typowane blockery i steruje dostępnością
publikacji, a `evaluate_dataset(...)` dokłada kompletność Calibration/Validation.
Oba wejścia zwracają ten sam fingerprintowany `ReferenceReadiness`; M6 i
Orientation publisher wyłącznie egzekwują ten wynik przez `require_ready()`.
Policy uwzględnia quarantine bez aktywnej publikacji, pending candidate,
prepared correction, stale/conflicted rebase, Effective Domain Projection,
kompletność i sign-off review oraz wymagane reason codes.

## Persistence i integralność

Źródłami prawdy po Open są automatic snapshot, Orientation Class Catalog i
correction history. Materializowany Effective Projection Checkpoint służy tylko
do sprawdzenia reprodukowalności. Loader ponownie liczy projekcję i porównuje jej
fingerprint. Niezgodny checkpoint zachowuje dane do audytu, przełącza workspace w
quarantine i nie aktywuje korekt.

Zapis jest atomowy: cały envelope ma przejść walidację przed zastąpieniem pliku.
Draft, pending rebase i historyczne stale revisions mogą zostać zapisane, lecz
nie mogą deklarować readiness.

## Reference datasets, presets i kampania

Wspólny envelope kolekcji nie staje się trzecim modelem targetów. M6 i Orientation
mają osobne modele v2, osobne review i osobne Calibration/Validation. Jednostką
splitu jest cały `measurement_group`; content, acquisition i lineage fingerprinty
blokują leakage przez rename, kopię lub sąsiednią klatkę.

Preset jest konfiguracją przyszłego runu, nie dowodem walidacji. Analiza zamraża
backend, ustawienia, First-Shell Geometry Policy, wersje i fingerprint. Późniejsza
edycja biblioteki nie zmienia runu.

Kampania reużywa istniejącego bounded search. Najpierw wybiera geometrię na
Calibration, stosuje precision/stability gates, liczy objective obejmujący recall
oraz split/merge, zamraża po jednym kandydacie każdego backendu i dopiero wtedy
zużywa jeden Validation receipt. Report nigdy automatycznie nie aktywuje presetu.

## Mapowanie wariantu C na Controller

| Element UI | Czyta | Wysyła |
| --- | --- | --- |
| Canvas | effective overlay, highlight, selection | point/polygon selection, viewport actions |
| Pionowy rail | bieżący stage i readiness | zmiana stage |
| Dolny arkusz Analyze | request, capabilities, run status | run/cancel/rerun |
| Dolny arkusz Correct | selected axis/target, prepared preview, conflicts | prepare/apply/undo/redo/rebase |
| Dolny arkusz Review | target-specific scope i completeness | disposition, reason, sign-off |
| References | dataset draft, split diagnostics, source revisions | validate/publish |
| Presets | library, working copy, active preset | save/discard/activate/import |
| Calibrate | campaign draft, shortlist, receipt | run/freeze/open Validation/report |

## Testy kontraktowe

Implementacja jest prowadzona pionowo TDD. Testy obserwują wyłącznie publiczne
snapshoty, raporty, pliki i zdarzenia. Nie asercjonują prywatnych wywołań.
Minimalny zestaw końcowy obejmuje:

- regresję capability `abc_orientation` po Open → enable → Save → Open;
- oba backendy z backend-qualified fingerprintami i pełnym funnel;
- korektę punktową/polygon, konflikty, Undo/Redo, review i rebase;
- jeden snapshot Controllera dla canvasu, drzewa i preview;
- session v3 round-trip, quarantine checkpointu i export v10;
- publikację obu Reference Dataset v2 i brak leakage/source drift;
- zamrożenie runu względem zmian biblioteki presetów;
- jednorazowy Validation receipt i report v2;
- pełny przypadek TTMAPP oraz test `Help` otwierający instrukcję.

Przed finalnym wydaniem pełne `tests/moltrack` działają z
`QT_QPA_PLATFORM=offscreen`, a `scripts/check_moltrack_code_size.py` pozostaje
bramką ratchetu.
