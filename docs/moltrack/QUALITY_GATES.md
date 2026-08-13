# MolTrack quality gates

Run commands from the repository root in the `netcat` Conda environment.

## Test baseline

The pre-Domain-Analysis baseline was captured at commit
`e6ec46b9a9170e5ae155cff77f7ac7cd3099f85b` with Qt running offscreen:

```powershell
$env:QT_QPA_PLATFORM = 'offscreen'
conda run -n netcat python -m pytest tests\moltrack -q --tb=short
```

The result was `1135 passed in 275.60s`, with no failures or collection
errors. The same result is recorded in
`scripts/moltrack_code_size_baseline.json` so later regressions cannot be
mistaken for pre-existing failures.

## Domain Analysis typecheck

Typecheck the Domain Analysis core together with its thin Qt composition and
views using one repeatable command:

```powershell
conda run -n netcat python -m mypy --ignore-missing-imports --follow-imports=silent moltrack\analysis\domain_analysis moltrack\ui\domain_analysis_composition.py moltrack\ui\domain_analysis_runtime.py moltrack\ui\domain_analysis_overlay.py moltrack\ui\domain_analysis_hierarchy.py moltrack\ui\domain_analysis_workspace_view.py moltrack\ui\domain_correction_sheet.py moltrack\ui\domain_correction_view.py moltrack\ui\manual_domain_controls.py moltrack\ui\position_analysis_workspace_presentation.py moltrack\ui\dialogs\domain_analysis_command_center.py moltrack\ui\dialogs\domain_analysis_dialog.py moltrack\ui\dialogs\m6_preset_sheet.py moltrack\ui\dialogs\m6_settings_editor.py moltrack\ui\dialogs\position_analysis_workspace_dialog.py moltrack\ui\dialogs\m6_current_frame_results_panel.py
```

The explicit file list is the agreed typecheck scope. `follow-imports=silent`
still uses imported type information while keeping failures owned by this gate
inside Domain Analysis and its Qt adapters. `ignore-missing-imports` is required
for optional scientific and GUI packages that do not publish typing metadata.

## Code-size guard

Run the architecture guard with one command:

```powershell
conda run -n netcat python scripts\check_moltrack_code_size.py
```

Prefer 250-500 physical lines per MolTrack production file; the hard limit is
800. A production file may contain at most 30 functions/methods and 10 classes.
Prefer no more than 40 physical lines per function or method; the hard limit is
80. A MolTrack test file may contain at most 1000 physical lines and 40 tests.

The JSON baseline lists only existing exceptions. An exception may not grow.
When an exception shrinks, the guard fails until its recorded cap is lowered;
remove the entry after it reaches the universal limit. Files excluded from
version control are outside the guard. The initial caps are verified against
the recorded baseline commit, and later cap changes are compared with the
previous committed baseline, so adding or raising an exception together with
the offending code is rejected.
