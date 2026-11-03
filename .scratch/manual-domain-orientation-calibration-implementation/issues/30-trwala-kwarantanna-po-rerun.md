# 30 — Zachować audit kwarantanny po rerun i Save/Open

**What to build:** Quarantined correction workspace pozostaje trwałym audit evidence także po uruchomieniu nowej analizy. Nowa aktywna publikacja nie usuwa ani nie aktywuje starego payloadu, a jego archiwizacja lub usunięcie wymaga jawnej operacji.

**Blocked by:** 18 — Kwarantannować niereprodukowalny checkpoint po Open.

**Status:** completed

- [x] Kwarantanna jest częścią Controller-owned snapshotu lub jawnego audit archive, a kompozycja UI nie przechowuje równoległego naukowego stanu poza Controllerem.
- [x] Open uszkodzonej sesji → rerun → Save → Open zachowuje dokładnie automatic snapshot, correction payload, reason i status pierwotnej kwarantanny.
- [x] Audit-only kwarantanna nie staje się aktywną semantyką i nie zanieczyszcza readiness nowej poprawnej revision; usunięcie lub archiwizacja jest jawne i audytowalne.
- [x] Tracer RED–GREEN obejmuje produkcyjną kompozycję i rzeczywisty round-trip; typecheck, targeted tests, pełne `tests/moltrack`, code-size guard i code review przechodzą; powstaje jeden commit.
- [x] Quarantine lifecycle ma jednego właściciela za małym Interface, nie jest duplikowany w UI, persistence lub eksporcie i mieści się w limitach 800/30/10/80.
