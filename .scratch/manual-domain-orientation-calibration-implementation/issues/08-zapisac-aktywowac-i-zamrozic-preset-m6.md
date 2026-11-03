# 08 — Zapisać, aktywować i zamrozić preset M6

**What to build:** Operator tworzy nazwany preset M6, zapisuje go i ustawia jako jeden aktywny default dla przyszłych analiz. Każdy run zamraża backend, pełne ustawienia, First-Shell Geometry Policy, wersje i configuration fingerprint, więc późniejsza zmiana biblioteki nie zmienia wyniku.

**Blocked by:** 06 — Otworzyć Spatial Command Center nad jednym workspace.

**Status:** completed

- [x] New/Save/Set active działa przez etap Presets, a etap Analyze rozpoczyna przyszły run od aktywnego zapisanego presetu.
- [x] Zmiana lub aktywacja innego presetu po starcie nie zmienia zamrożonej konfiguracji trwającego ani zakończonego runu.
- [x] Zapis i aktywacja nie wymagają campaign report, Validation receipt ani approval i nigdy nie przeliczają istniejącego wyniku.
- [x] Tracer RED–GREEN przechodzi przez bibliotekę i `DomainAnalysisModule.run(...)`; typecheck, targeted tests, pełne `tests/moltrack`, code-size guard i code review przechodzą; powstaje jeden commit.
- [x] Biblioteka jest głębokim Module z małym Interface; nowe pliki celują w 250–500 i nie przekraczają twardych limitów.
