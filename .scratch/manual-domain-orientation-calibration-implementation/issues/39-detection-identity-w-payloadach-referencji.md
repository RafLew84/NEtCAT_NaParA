# 39 — Użyć DetectionIdentity na granicach payloadów referencji

**What to build:** Payloady i workflow referencji M6 oraz orientation używają `DetectionIdentity` zamiast ponownie składanych pozycyjnych krotek `(physical_frame_id, source_id)`.

**Blocked by:** 33 — Zastąpić tuple jawnym typem Detection Identity.

**Status:** completed

- [x] `m6_reference_payload.py` i `orientation_reference_payload.py` przyjmują oraz porównują nazwany `DetectionIdentity` we wszystkich ścieżkach walidacji i deduplikacji.
- [x] Nie istnieje równoległa lokalna definicja ani ręcznie składana krotka pełniąca rolę identity w produkcyjnym kodzie publikacji referencji.
- [x] Serializacja zachowuje zgodne pola publicznego formatu, canonical fingerprinty i możliwość odczytu istniejących M6 Reference v2 oraz Orientation Reference v2.
- [x] Testy obejmują odwrócone pola, niepełną identity, duplikaty, child publication i round-trip obu rodzajów referencji.
- [x] Typecheck, targeted tests, pełne `tests/moltrack`, code-size guard i code review przechodzą; powstaje jeden commit.
