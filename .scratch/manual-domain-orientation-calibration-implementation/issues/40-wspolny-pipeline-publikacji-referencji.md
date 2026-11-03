# 40 — Wydzielić wspólny pipeline publikacji referencji

**What to build:** Publikacja M6 i orientation współdzieli jeden pipeline readiness, walidacji, wersjonowania oraz zapisu, a różnice między typami referencji są dostarczane przez jawne strategie domenowe.

**Blocked by:** 20 — Publikować M6 Reference v2; 22 — Publikować Orientation Reference v2; 32 — Wyliczać Reference Readiness przez jeden domenowy seam; 39 — Użyć DetectionIdentity na granicach payloadów referencji.

**Status:** completed

- [x] `domain_analysis_reference_workflow.py` ma jednego właściciela wspólnej sekwencji readiness → validation → version allocation → publication → result.
- [x] M6 i orientation dostarczają wyłącznie jawne różnice payloadu oraz walidacji, bez kopiowania całej orkiestracji i bez warunków zależnych od testów.
- [x] Publikacja root i immutable child zachowuje ancestry, correction revision, analysis epoch, fingerprinty oraz atomowość zapisu.
- [x] Testy kontraktowe wykonują ten sam zestaw przypadków sukcesu i odmowy dla M6 oraz orientation, w tym stale, conflicted i quarantined.
- [x] Typecheck, targeted tests, pełne `tests/moltrack`, code-size guard i code review przechodzą bez zmiany publicznych formatów; powstaje jeden commit.
