# 19 — Eksportować correction-aware package v10

**What to build:** Operator eksportuje package v10, który zachowuje automatic snapshot, katalog A-Z, correction revisions i operations, effective state, oba review, pełne Funnels, rebase diagnostics oraz readiness. V9 pozostaje osobnym, jednoznacznie automatic-only formatem.

**Blocked by:** 18 — Kwarantannować niereprodukowalny checkpoint po Open.

**Status:** completed

- [x] V10 zawiera dokładnie raz każdy `source_id` zamrożonego scope, także accepted automatic i jawne not eligible, oraz zachowuje raw automatic evidence po korekcie.
- [x] Manifest fingerprintuje każdy plik i kotwiczy backend identity, automat, katalog, correction revision i efektywną projekcję.
- [x] Draft/conflicted/stale może wyjść wyłącznie jako audit z `readiness=false`; quarantined state nie może udawać aktywnej correction-aware projekcji.
- [x] Tracer RED–GREEN buduje rzeczywisty katalog; typecheck, targeted tests, pełne `tests/moltrack`, code-size guard i code review przechodzą; powstaje jeden commit.
- [x] Export policy pozostaje za jednym Interface, v9 nie jest dual-write v10, a nowe pliki mieszczą się w limitach bez wzrostu ratchetu.
