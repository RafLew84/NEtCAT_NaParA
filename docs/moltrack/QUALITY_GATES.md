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

## Code-size guard

Run the architecture guard with one command:

```powershell
conda run -n netcat python scripts\check_moltrack_code_size.py
```

New MolTrack production files are limited to 800 physical lines, 30
functions/methods, 10 classes, and 80 physical lines per function or method.
Prefer 250-500 lines per production file and no more than 40 lines per
function. MolTrack test files are limited to 1000 physical lines and 40 tests.

The JSON baseline lists only existing exceptions. An exception may not grow.
When an exception shrinks, the guard fails until its recorded cap is lowered;
remove the entry after it reaches the universal limit. Files excluded from
version control are outside the guard. The initial caps are verified against
the recorded baseline commit, and later cap changes are compared with the
previous committed baseline, so adding or raising an exception together with
the offending code is rejected.
