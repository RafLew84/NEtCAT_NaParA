# 22 — Publikować osobny Orientation Reference Dataset v2

**What to build:** Operator publikuje Orientation Reference Dataset Version v2 niezależnie od M6. Pakiet zachowuje effective A-Z/`Unresolvable`, raw frames, segmentacje, pixel size, scan angle lub missing-QC, sample coordinates i pełne provenance potrzebne przyszłemu klasyfikatorowi.

**Blocked by:** 21 — Chronić integralność i wersjonowanie referencji.

**Status:** completed

- [x] Orientation publisher używa wspólnego envelope i integrity policy, ale własnego target schema, review, splitów i readiness.
- [x] Ręczne A-Z poza full domain trafia do datasetu bez utworzenia M6 targetu; missing scan angle wymaga jawnego QC, a pixel size i coordinate frame są wymagane.
- [x] Content-addressed raw-frame i segmentation objects oraz orientation geometry przechodzą immutable child publication bez mieszania M6 assignments.
- [x] Tracer RED–GREEN buduje rzeczywisty pakiet; typecheck, targeted tests, pełne `tests/moltrack`, code-size guard i code review przechodzą; powstaje jeden commit.
- [x] Target Adapter korzysta z głębokiego wspólnego publishera, nie duplikuje jego reguł i mieści się w limitach kodu.
