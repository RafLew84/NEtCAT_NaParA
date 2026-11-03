# 28 — Udostępnić correction-aware export v10 w produkcyjnym UI

**What to build:** Operator eksportuje correction-aware package v10 przez rzeczywisty `MainWindow` i produkcyjną kompozycję Domain Analysis. V9 pozostaje osobnym, jawnie legacy automatic-only formatem i nie może być cichym domyślnym wynikiem akcji eksportu poprawionej analizy.

**Blocked by:** 19 — Eksportować correction-aware package v10.

**Status:** completed

- [x] Produkcyjny callback buduje `CorrectionAwareExportSettings`, a pełna ścieżka `MainWindow` → composition → dispatcher publikuje manifest z `export_schema_version=10`.
- [x] V9 jest dostępne wyłącznie przez osobną jawną akcję legacy; nie powstaje dual-write, automatyczny fallback ani zależność wyniku od typu testowego callbacku.
- [x] Draft, stale, conflicted i quarantined mogą wyjść wyłącznie jako audit z `readiness=false`, a aktywna reference-ready projekcja zachowuje cały kontrakt v10.
- [x] Tracer Qt RED–GREEN nie wstrzykuje własnego eksportera i obserwuje rzeczywisty katalog; typecheck, targeted tests, pełne `tests/moltrack` (`1170 passed`), code-size guard i code review przechodzą; powstaje jeden commit.
- [x] Publiczny export seam pozostaje jednym właścicielem wyboru schematu, UI jest cienkie, a nowe pliki nie przekraczają limitów 800/30/10/80 ani ratchetu.
