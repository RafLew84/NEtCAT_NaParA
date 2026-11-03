# 16 — Zapisać i otworzyć correction-aware session v3

**What to build:** Operator zapisuje i otwiera MolTrack session v3 zawierającą automatic snapshot, Orientation Class Catalog, correction/rebase history, oba review, Funnels oraz Effective Projection Checkpoint. Runtime capability catalog pozostaje własnością aplikacji, nie payloadu.

**Blocked by:** 02 — Zachować capability `abc_orientation` po Open; 15 — Porównać rerun i wykonać atomowy Correction Rebase.

**Status:** completed

- [x] Round-trip odtwarza wszystkie źródła prawdy i przelicza identyczną Effective Domain Projection zamiast ufać zapisanym mutowalnym metrykom.
- [x] Outer session v3 zawiera Domain Analysis v2 i correction workspace v1; nieznana outer version jest odrzucana przed częściowym Open.
- [x] Save jest atomowy, a draft, pending rebase i historyczne stale revisions pozostają audytowalne bez fałszywego readiness.
- [x] Tracer RED–GREEN używa rzeczywistego Save/Open; typecheck, targeted tests, pełne `tests/moltrack`, code-size guard i code review przechodzą; powstaje jeden commit.
- [x] Nowa schema trafia do osobnego głębokiego Module, nie powiększa istniejących serializerów ratchetu i mieści się w limitach.
