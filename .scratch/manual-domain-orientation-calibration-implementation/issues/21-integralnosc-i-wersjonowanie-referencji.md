# 21 — Chronić integralność i wersjonowanie referencji

**What to build:** Operator aktualizuje Reference Dataset przez immutable child version. System wykrywa leakage mimo rename/copy/conversion, source drift mimo tej samej ścieżki oraz wymusza zamrożone Validation w obrębie jednego epoch.

**Blocked by:** 20 — Publikować M6 Reference Dataset v2.

**Status:** completed

- [x] Ta sama group/acquisition/content/lineage identity nie może wystąpić po obu stronach Calibration/Validation, także po zmianie nazwy, kopii lub wyborze sąsiedniej klatki.
- [x] Zmiana Calibration przy identycznym Validation fingerprint tworzy child w tym samym epoch; zmiana Validation rozpoczyna nowy epoch.
- [x] Inne source bytes tworzą nową source revision i nie nadpisują starej; relokacja zweryfikowanych identycznych bytes nie tworzy rewizji.
- [x] Tracery RED–GREEN obejmują leakage, drift i child publication; typecheck, targeted tests, pełne `tests/moltrack`, code-size guard i code review przechodzą; powstaje jeden commit.
- [x] Identity i readiness mają jednego właściciela, a nowe pliki nie przekraczają 800/30/10/80 ani ratchetu.
