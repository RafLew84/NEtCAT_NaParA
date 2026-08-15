# Domain Analysis — formaty i kompatybilność (draft)

**Status:** referencja stanu obecnego i zatwierdzonego kontraktu docelowego

**Słownik:** [CONTEXT.md](CONTEXT.md)

**Migracje:**
[DOMAIN_ANALYSIS_MIGRATION_AND_TROUBLESHOOTING_DRAFT.md](DOMAIN_ANALYSIS_MIGRATION_AND_TROUBLESHOOTING_DRAFT.md)

## Macierz wersji

| Format | Produkcja obecnie | Kontrakt docelowy | Zasada zgodności |
| --- | --- | --- | --- |
| MolTrack session | v3; loader v1/v2/v3 | v3; loader v2/v3 | nieznana outer version jest odrzucana |
| Domain Analysis state | v2 | v2 | v2 zawiera correction-aware workspace |
| `correction_workspace` | v1 | v1 | wymagany wewnątrz session v3 |
| Domain Analysis export | v10 | v10 | v9 pozostaje jawnie automatic-only; v10 jest correction-aware package kind |
| M6 Reference Dataset | v2 | v2 | v1 importuje się jako audit-only draft |
| Orientation Reference Dataset | v2 | v2 | v1 importuje się jako audit-only draft |
| Reference collection envelope | manifest schema v2 | manifest schema v2 | envelope nie jest trzecim targetem |
| M6 preset | m6-preset-library-v1 / m6-preset-v1 | m6-preset-library-v1 / m6-preset-v1 | nieznana nowsza schema blokuje aktywację |
| M6 calibration campaign report | m6-campaign-report-v2 | m6-campaign-report-v2 | v2 zachowuje dataset/epoch/backend/receipt identity |

Session v3, Domain Analysis state v2 i correction workspace v1 przeszły pełny
cutover modeli, migratora, testów i readera. Starsze wersje są obsługiwane wyłącznie
przez jawne ścieżki odczytu lub migracji wskazane w tabeli.

## MolTrack session v3

Outer envelope v3 zawiera zagnieżdżony Domain Analysis state v2. Ten z kolei
przechowuje:

- immutable `published_result` z automatic snapshotem i backend identity;
- `correction_workspace` v1 z katalogiem A–Z, revisions, operations, review,
  rebase i pending candidates;
- pełne Molecule Diagnostic Funnels;
- materializowany Effective Projection Checkpoint oraz fingerprinty integralności;
- żądane classifier IDs i reprodukcyjne konfiguracje, ale nie runtime capability
  catalog.

Session v2 migruje się do pustej correction history i review `draft`. Migracja nie
tworzy D–Z, decyzji `accepted_automatic` ani sign-off. Starsza aplikacja ma
odrzucić v3 zamiast pominąć correction workspace i utracić go przy Save.

## Domain Analysis export v9

V9 jest istniejącym, automatic-only pakietem. Zachowuje bieżące tabele automatu,
ale nie ma correction history, target-specific review ani correction-aware
effective state. Reader i UI muszą prezentować go jako legacy automatic-only;
v9 nie może deklarować reference readiness.

## Domain Analysis export v10

V10 otrzymuje nowy `package_kind` i manifest fingerprintujący każdy plik oraz
kotwiczący automatic snapshot, katalog, correction revision i efektywną
projekcję. Zachowuje tabele automatic z v9 oraz dodaje co najmniej artefakty dla:

- Orientation Class Catalog;
- correction revisions i append-only operations;
- effective frames, domains i molecules;
- target-specific review decisions i sign-offs;
- diagnostic stages każdego `source_id`;
- rebase diagnostics i readiness.

Jeden rekord effective molecule przechowuje oddzielnie automatic M6, automatic
domain/native role, raw orientation/evidence, effective M6 membership, effective
orientation lub `Unresolvable`, provenance i review disposition. Wspólne pole nie
może łączyć obu osi.

Pakiet `audit` może zawierać draft, stale/conflicted revisions i niekompletne
review, ale ma `readiness=false`. Reference-ready v10 obejmuje dokładnie raz każdy
`source_id` zamrożonego scope, również poprawne `accepted_automatic`.

## Reference Dataset v2

Wspólna kolekcja zawiera co najmniej:

- `manifest.json` — dataset/version identity, rodzic, target schema, readiness,
  Validation epoch i fingerprinty partycji;
- `file_manifest.json` — ścieżki, liczby rekordów i content fingerprinty;
- `measurements.jsonl` — measurement groups, split, source revision i lineage;
- `frames.jsonl`, `molecules.jsonl`, `source_geometry.jsonl`;
- `review_signoffs.jsonl` i `diagnostic_stages.jsonl`.

M6 dodaje `m6_assignments.jsonl` i `m6_first_shell_edges.jsonl`. Orientation
dodaje `orientation_assignments.jsonl`, `orientation_geometry.jsonl` oraz
content-addressed `objects/raw_frames/*` i `objects/segmentations/*`.

Kanoniczne splity to `calibration` oraz `validation`. Cały `measurement_group`
należy do dokładnie jednego splitu w obrębie targetu. `dataset_id` jest stabilne,
a każda publikacja ma rosnący `dataset_version`, niezmienne `version_id`,
`parent_version_id` i `version_fingerprint`.

Zmiana Calibration przy identycznym Validation fingerprint pozostaje w tym samym
Validation epoch. Zmiana Validation tworzy nowy epoch. Inne bytes pod tą samą
ścieżką tworzą nową source revision; relokacja identycznych bytes nie tworzy jej.

## Preset schema

Numer pierwszej produkcyjnej schema presetu musi zostać zamrożony razem z modelem
i migratorem — plan nie nadaje mu numeru na zapas. Payload zawiera:

- niepustą, unikalną nazwę oraz opcjonalny opis;
- backend identity;
- komplet M6 Orientation Analysis Settings;
- fixed albo adaptive First-Shell Geometry Policy, parametry, fingerprint i
  jawny fixed fallback;
- algorithm version, schema version, configuration fingerprint oraz timestamps.

Fingerprint konfiguracji nie obejmuje nazwy, opisu ani timestamps. Znany starszy
schemat otwiera się jako working copy wymagająca `Save As`. Nieznana nowsza
schema, niekompletna konfiguracja lub niedostępny backend blokują aktywację.

## Campaign report v2

Report v2 kotwiczy:

- M6 Reference Dataset Version i Validation epoch;
- porównywane backend identities oraz First-Shell Geometry Policy;
- objective, precision/stability constraints i konfigurację bounded search;
- wyniki Calibration, shortlistę po jednym kandydacie każdego backendu;
- pojedynczy Validation receipt i wyniki Validation;
- capability `unavailable`, funnel misses i legalny wynik bez rekomendacji.

Report nie zmienia biblioteki presetów i nie aktywuje zwycięzcy. Zmiana datasetu,
objective lub shortlisty po zamrożeniu unieważnia próbę użycia istniejącego
Validation receipt.

## Reguły fail-closed

- Nieznana outer session/export/dataset version jest odrzucana bez częściowego
  Open lub importu.
- Niezgodny checkpoint trafia do quarantine i nie jest drugim źródłem prawdy.
- Brak fingerprintu albo niejednoznaczna migracja nie jest uzupełniana bieżącym
  defaultem.
- Legacy flagi dataset-level `reviewed/reviewed_by` nie nadają readiness.
- V9 nie jest automatycznie konwertowany w reviewowany v10.
- Nieznany backend lub schema presetu blokuje wykonanie zamiast wybierać fallback.

## Kanoniczne stałe obecnego kodu

Do czasu cutoveru deklaracje stanu produkcyjnego muszą być zgodne z:

- `moltrack/core/session.py` — MolTrack session version i supported versions;
- `moltrack/analysis/domain_analysis/session_state.py` — Domain Analysis state;
- `moltrack/persistence/domain_analysis_export_schema.py` — export v9;
- `moltrack/analysis/lattice_domain_calibration_models.py` — calibration v1;
- `moltrack/analysis/molecular_orientation_models.py` — orientation v1.

Po implementacji nowych formatów test dokumentacji ma porównywać tę tabelę ze
stałymi zamiast polegać na ręcznej kontroli tekstu.
