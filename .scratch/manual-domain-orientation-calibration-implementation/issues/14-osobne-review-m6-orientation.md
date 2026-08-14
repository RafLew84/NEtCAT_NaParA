# 14 — Reviewować M6 i Orientation niezależnie

**What to build:** Operator rozlicza pełny, zamrożony Reference Review Scope osobno dla M6 i Orientation, a następnie wykonuje jawny sign-off każdego targetu. Kompletność obejmuje także `accepted_automatic`, abstencje i wykluczenia, nie tylko ręcznie zmienione punkty.

**Blocked by:** 13 — Cofać i ponawiać korekty append-only.

**Status:** completed

- [x] Każdy `source_id` scope występuje dokładnie raz jako eligible albo `not eligible`; reason jest wymagany dla rejection, uncertain, Unresolvable i wykluczenia.
- [x] M6 oraz Orientation mają osobne disposition, status i timestampowany sign-off bez `reviewer_id`; jedna oś może być reviewed, gdy druga pozostaje draft.
- [x] Save, Export i Calibration nigdy nie wykonują sign-off niejawnie, a zmiana źródła, scope lub anotacji unieważnia tylko właściwy podpisany stan.
- [x] Tracer RED–GREEN przechodzi przez wspólną policy i Qt Review; typecheck, targeted tests, pełne `tests/moltrack`, code-size guard i code review przechodzą; powstaje jeden commit.
- [x] Readiness jest wyliczana za małym Interface, a nowe pliki nie przekraczają 800/30/10/80 ani ratchetu.
