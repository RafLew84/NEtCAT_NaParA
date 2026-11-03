# 17 — Migrować session v2 do pustej historii v3

**What to build:** Operator otwiera istniejącą session v2 w nowej aplikacji bez utraty automatycznego wyniku. Migracja przypisuje wyłącznie dowiedziony historyczny backend, tworzy pustą correction history i osobne review `draft`, nie wymyślając D-Z, accepted decisions ani sign-off.

**Blocked by:** 16 — Zapisać i otworzyć correction-aware session v3.

**Status:** completed

- [x] Migracja zachowuje series identity, draft, kompatybilny published result, classifier evidence i diagnostykę oraz jawnie przypisuje historyczny backend tylko znanemu payloadowi.
- [x] Effective Projection może wartościowo odpowiadać automatowi, lecz correction history jest pusta, oba review są draft i readiness pozostaje false.
- [x] Session v2 pozostaje wspieraną granicą wejściową; starszy reader v2 odrzuca v3 zamiast cicho zgubić correction workspace.
- [x] Tracer RED–GREEN oraz regresja `abc_orientation` przechodzą z typecheck, targeted tests, pełnym `tests/moltrack`, code-size guard i code review; powstaje jeden commit.
- [x] Migrator ma mały Interface, nie zgaduje brakujących danych i nie zwiększa żadnego wyjątku ratchetu.
