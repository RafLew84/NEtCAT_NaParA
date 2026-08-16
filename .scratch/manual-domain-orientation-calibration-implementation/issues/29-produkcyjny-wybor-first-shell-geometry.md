# 29 — Wybrać fixed lub adaptive First-Shell Geometry w produkcyjnym workflow

**What to build:** Produkcyjny workflow Calibration porównuje fixed range z deterministycznym adaptive `g(r)`, pokazuje operatorowi metryki i evidence, a następnie zamraża jawnie wybraną wykonywalną policy przed sweepem klasyfikacyjnym.

**Blocked by:** 24 — Wybrać i zamrozić First-Shell Geometry Policy.

**Status:** completed

- [x] Oba produkcyjne backendy dostarczają potrzebne Calibration evidence, a workflow raportuje fixed i adaptive P/R/F1 per measurement group i symmetry bez otwierania Validation.
- [x] Operator jawnie wybiera policy; adaptive jest wykonywalne w aktywnym presecie, a brak capability tworzy fixed fallback z niepustym reason zamiast `operator_selected_fixed_policy` udającego eksperyment.
- [x] Wybrana policy zapisuje parametry, evidence, wersję i fingerprint przed sweepem, a zmiana geometry fingerprint unieważnia search oraz shortlistę.
- [x] Tracer RED–GREEN przechodzi przez produkcyjny workflow i oba Adaptery; typecheck, targeted tests, pełne `tests/moltrack`, code-size guard i code review przechodzą; powstaje jeden commit.
- [x] Orkiestracja eksperymentu, adapterów i mapowania native evidence trafia do Qt-free application service; UI wyłącznie zbiera decyzję i renderuje wynik, bez wzrostu ratchetu.
