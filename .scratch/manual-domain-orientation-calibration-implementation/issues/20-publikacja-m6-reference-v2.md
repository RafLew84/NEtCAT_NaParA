# 20 — Publikować M6 Reference Dataset v2

**What to build:** Operator wybiera kompletne, target-specific reviewowane klatki i publikuje pierwszą immutable M6 Reference Dataset Version v2. Pakiet przechowuje pełne measurement groups, effective M6 assignments, first-shell edges, provenance i diagnostykę, bez targetów orientacji.

**Blocked by:** 19 — Eksportować correction-aware package v10.

**Status:** completed

- [x] Publisher odrzuca draft, niekompletny scope, brak reason, stale/conflicted/quarantined corrections oraz puste Calibration lub Validation.
- [x] Jednostką splitu jest cały `measurement_group`; pakiet zapisuje manifest, measurements, frames, molecules, source geometry, sign-offs, diagnostic stages, M6 assignments i first-shell edges.
- [x] Publikacja jest atomowa, immutable i nadaje stabilne dataset ID, version ID, version fingerprint oraz Validation epoch identity.
- [x] Tracer RED–GREEN używa publicznego publishera i rzeczywistego katalogu; typecheck, targeted tests, pełne `tests/moltrack`, code-size guard i code review przechodzą; powstaje jeden commit.
- [x] Publisher jest głębokim target-specific Module, nie trzecim modelem etykiet; nowe pliki celują w 250–500 i nie przekraczają limitów.
