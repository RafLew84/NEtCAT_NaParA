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

Run the automatic Domain Analysis typecheck locally and in CI with the same
command:

```powershell
conda run -n netcat python scripts\check_domain_analysis_types.py
```

The checker always discovers the complete
`moltrack/analysis/domain_analysis/**/*.py` and `moltrack/ui/**/*.py` packages.
It also discovers every other production `moltrack/**/*.py` file added or
changed since the fixed Domain Analysis ownership boundary
`d0e542a0a601e9306d17d56b353a13d6c50b3af1`, including untracked production
files during local development. Therefore later modules enter the gate without
editing a file list. CI checks out full Git history so the same boundary is
available there. Imported type information remains available, while optional
scientific and GUI packages without typing metadata are tolerated.

Nine legacy files currently carry 165 diagnostics in
`scripts/domain_analysis_mypy_baseline.json`. Every entry has an owner and a
justification. Stable path, error-code, and message fingerprints are ratchets:
adding or replacing a diagnostic, raising a count, or moving the ownership
boundary fails the gate. When a diagnostic is fixed, the stale fingerprint or
higher count also fails until the baseline is lowered or removed. Locally the
ratchet compares against `HEAD`; CI sets `DOMAIN_ANALYSIS_RATCHET_REF` to the PR
base or pre-push revision so a commit cannot raise its own accepted debt. On a
first branch push, GitHub's all-zero `before` value falls back to `HEAD^`.

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
