# 32 — Wyliczać Reference Readiness przez jeden domenowy seam

**What to build:** UI, M6 publisher i Orientation publisher korzystają z jednego target-specific wyniku Reference Readiness. Ten sam zestaw blockerów decyduje o etykiecie `Ready`, dostępności publikacji i błędzie fail-closed.

**Blocked by:** 30 — Zachować audit kwarantanny po rerun i Save/Open.

**Status:** completed

- [x] Jeden `ReferenceReadinessPolicy` uwzględnia review completeness/sign-off, required reasons, quarantine, pending candidate, prepared correction, stale/conflicted rebase, effective projection i kompletność splitów.
- [x] UI pokazuje wszystkie typowane blockery i nigdy nie wyświetla `Ready`, jeśli target-specific publisher odrzuciłby ten sam snapshot.
- [x] M6 i Orientation publisher nie implementują ponownie readiness; otrzymują albo wyliczają identyczny fingerprintowany rezultat policy.
- [x] Tracery RED–GREEN obejmują rozbieżne wcześniej stany UI/publishera; typecheck, targeted tests, pełne `tests/moltrack`, code-size guard i code review przechodzą; powstaje jeden commit.
- [x] Readiness ma jednego właściciela za małym Interface, dokumentacja wskazuje tego samego właściciela, a nowe pliki mieszczą się w limitach bez wzrostu ratchetu.
