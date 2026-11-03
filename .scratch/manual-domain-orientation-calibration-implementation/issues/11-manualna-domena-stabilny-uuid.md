# 11 — Zarządzać ręczną domeną ze stabilnym UUID

**What to build:** Operator tworzy ręczną domenę, przenosi do niej molekuły, usuwa ją i przywraca bez utraty tożsamości. Effective Domain Projection gwarantuje jedno membership, tombstone pustej domeny i ponownie wyliczone metryki zamiast mutowalnych kopii.

**Blocked by:** 10 — Przypisać ręczną orientację poza domeną M6.

**Status:** completed

- [x] Create nadaje UUID dokładnie raz, a move/delete/restore zachowują ten UUID niezależnie od członków, geometrii i metryk.
- [x] Punkt należy najwyżej do jednej domeny; usunięcie nie usuwa molekuł ani ich orientacji, a pusta ręczna domena jest tombstone.
- [x] Count, centroid, bounds, footprint, role boundary i kompozycja A-Z są przeliczane z automatu i historii po każdym Apply.
- [x] Tracer RED–GREEN obejmuje DomainCorrectionModule i UI; typecheck, targeted tests, pełne `tests/moltrack`, code-size guard i code review przechodzą; powstaje jeden commit.
- [x] Reguły lifecycle pozostają za jednym Interface, nowe pliki celują w 250–500 i nie przekraczają twardych limitów.
