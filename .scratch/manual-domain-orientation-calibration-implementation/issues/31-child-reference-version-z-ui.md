# 31 — Publikować immutable child Reference Dataset Version z UI

**What to build:** Operator aktualizuje M6 lub Orientation Reference Dataset przez produkcyjny workflow, wskazując zweryfikowany parent package. UI pokazuje ancestry i przewidywaną regułę Validation epoch przed atomową publikacją child version.

**Blocked by:** 21 — Chronić integralność i wersjonowanie referencji; 22 — Publikować osobny Orientation Reference Dataset v2.

**Status:** completed

- [x] Workflow pozwala wybrać parent package zgodnego targetu i dataset ID, waliduje jego envelope oraz pokazuje parent version, source revisions i split fingerprints przed publikacją.
- [x] Calibration-only child zachowuje Validation epoch, zmiana Validation tworzy nowy epoch, a inny dataset, target lub uszkodzony parent jest odrzucany fail-closed.
- [x] Parent pozostaje bitowo niezmieniony, destination nie może wskazywać parenta, a child zapisuje stabilne ancestry i nie nadpisuje istniejącej version ID.
- [x] Tracer Qt RED–GREEN przechodzi przez produkcyjny References workflow zamiast bezpośredniego wywołania publishera; typecheck, targeted tests, pełne `tests/moltrack`, code-size guard i code review przechodzą; powstaje jeden commit.
- [x] UI pozostaje cienkim Adapterem wspólnego publishera i identity policy; nie duplikuje leakage, drift, epoch ani readiness i nie zwiększa ratchetu.
