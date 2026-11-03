# 33 — Zastąpić tuple jawnym typem Detection Identity

**What to build:** Stabilna tożsamość detekcji i mapowanie źródeł korekty są reprezentowane przez nazwane niemutowalne typy domenowe zamiast pozycyjnych `tuple[str, ...]`, bez zmiany istniejącej semantyki fingerprintów i payloadów.

**Blocked by:** 15 — Porównać rerun i wykonać atomowy Correction Rebase.

**Status:** completed

- [x] Powstaje `DetectionIdentity` z jawnie nazwanymi polami frame/source oraz nazwany `CorrectionSourceMapping`; correction workspace, history i rebase używają ich end-to-end.
- [x] Konstrukcja odwróconej kolejności lub niepełnej identity jest niemożliwa typowo albo odrzucana na granicy, a porównania i deduplikacja zachowują dotychczasową stabilność.
- [x] Persistence czyta istniejące session v3 i export v10, zapisuje zgodny kontrakt oraz nie zmienia canonical fingerprintów bez jawnej migracji wersji.
- [x] Tracer RED–GREEN obejmuje round-trip, rebase i błędne identity; typecheck, targeted tests, pełne `tests/moltrack`, code-size guard i code review przechodzą; powstaje jeden commit.
- [x] Typ ma jednego właściciela w modelu domenowym, usuwa data clumps bez pass-through wrapperów, a pliki nie przekraczają limitów 800/30/10/80 ani ratchetu.
