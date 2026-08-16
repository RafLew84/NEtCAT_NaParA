# 04 — Zachować lejek klasycznego backendu M6

**What to build:** Dla każdej molekuły analizowanej przez `m6_orientation_components` operator i maintainer otrzymują pełny, uporządkowany Molecule Diagnostic Funnel. Raw q6/orientation i przyczyny odrzucenia pozostają widoczne, a nieobsługiwane M3/core/halo/boundary są `unavailable`, nie wymyślone.

**Blocked by:** 03 — Uruchamiać jawnie wybrany backend domen.

**Status:** completed

- [x] Funnel zawiera wszystkie 17 etapów oraz osobne execution, decision, reason, typowane evidence i provenance nawet po wcześniejszej bramce.
- [x] Raw orientation odrzucone przez threshold lub component filter pozostaje w śladzie, a `boundary_or_disordered` nie udaje jawnego boundary.
- [x] Cienki widok diagnostyczny potrafi pokazać skrót i rozwinąć ten sam ślad bez rekonstrukcji z końcowej etykiety.
- [x] Tracer RED–GREEN przechodzi przez publiczny seam analizy; typecheck, targeted tests, pełne `tests/moltrack`, code-size guard i code review przechodzą, a zmiana tworzy jeden commit.
- [x] Nowy kod mieści się w limitach 800/30/10/80, preferuje pliki 250–500 linii i nie podnosi wyjątków ratchetu.
