# 23 — Rankingować kandydatów M6 source-aligned objective

**What to build:** Operator uruchamia kampanię M6 dla obu backendów na tej samej immutable M6 Reference Dataset Version. Jeden campaign seam reużywa istniejący bounded search i rankinguje source-ID-aligned kandydatów dopiero po przejściu precision oraz stability gates.

**Blocked by:** 21 — Chronić integralność i wersjonowanie referencji.

**Status:** completed

- [x] Membership TP/FP/FN, ARI/VI i correctly-assigned fraction są liczone niezależnie od frame-local domain IDs, z macro agregacją po measurement groups i zachowanymi micro counts.
- [x] Eligible kandydaci minimalizują `1 - recall + split_weight * split_rate + merge_weight * merge_rate`; precision i local stability są twardymi constraints.
- [x] Capability-dependent metric jest `unavailable` z reason, nie zerem; funnel miss attribution zachowuje najwcześniejszą terminalną przyczynę i sumuje się do FN.
- [x] Tracer RED–GREEN przechodzi przez jeden campaign seam i istniejący search; typecheck, targeted tests, pełne `tests/moltrack`, code-size guard i code review przechodzą; powstaje jeden commit.
- [x] Nie powstaje drugi sweep engine ani wzrost modułu kalibracji objętego ratchetem; nowy orkiestrator mieści się w limitach.
