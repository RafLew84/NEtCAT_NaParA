# 10 — Przypisać ręczną orientację poza domeną M6

**What to build:** Operator wybiera molekułę w domenie, island, Unassigned, outside, boundary albo uncertain, przygotowuje Preview i przypisuje A-Z lub `Unresolvable`. Effective orientation zmienia się bez niejawnej zmiany M6, a immutable automatic result i raw evidence pozostają dostępne do audytu oraz resetu.

**Blocked by:** 07 — Nawigować hierarchią domen bez zmiany selection.

**Status:** completed

- [x] Point selection → Preview → Apply przypisuje ręczne D-Z poza full domain, nie tworzy M6 membership i nie tworzy Orientation Subdomain do czasu wejścia do efektywnej domeny.
- [x] Ręczne A-Z nie otrzymuje sztucznego confidence; `Unresolvable` wymaga reason, a Reset orientation odsłania tylko kompatybilny automat.
- [x] Jeden `DomainCorrectionModule` inicjalizuje correction set i wylicza Effective Domain Projection; UI nie mutuje automatu ani nie implementuje pierwszeństwa etykiet.
- [x] Tracer RED–GREEN przechodzi przez publiczny seam korekt i cienkie Qt; typecheck, targeted tests, pełne `tests/moltrack`, code-size guard i code review przechodzą; powstaje jeden commit.
- [x] Nowy głęboki Module ma mały Interface, pliki celują w 250–500 i nie przekraczają limitów 800/30/10/80.
