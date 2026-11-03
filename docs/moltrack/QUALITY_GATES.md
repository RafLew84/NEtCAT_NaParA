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

## Acceptance/release public-seam guard

Domain Analysis modules that exercise a full operator workflow declare
`DOMAIN_ANALYSIS_TEST_TIER = "acceptance"` or `"release"`. The production TTMAPP
test and its UI support module form the current acceptance suite. Tests using
injected adapters or compositions are explicitly named as component tests and do
not claim release evidence.

Run the automatic tier and private-seam guard with:

```powershell
conda run -n netcat python -m pytest tests\moltrack\test_domain_analysis_test_tiers.py -q
```

The guard discovers explicitly tiered modules and Domain Analysis files named as
acceptance, release, or end-to-end tests. It rejects `_save_as()`,
`_MolTrackM6Adapter`, and injected session restorers, composition factories, or
export callbacks in that suite.

## Domain Analysis cutover manifest

Run the release cutover inventory validation locally and in CI with:

```powershell
conda run -n netcat python scripts\check_domain_analysis_cutover_manifest.py
```

The validator requires every legacy routing, state, worker, persistence/export,
and test locator to remain absent, while every declared replacement anchor must
resolve in the repository. It also verifies the completed cutover invariants and
the production preflight composition.

## Domain Analysis issue plan

The implementation plan has one closed status dictionary:

| Status | Checklist rule | Allowed next status |
| --- | --- | --- |
| `pending` | At least one acceptance criterion remains unchecked. | `completed` |
| `completed` | Every acceptance criterion is checked. | None |

A ticket moves from `pending` to `completed` only after every acceptance
criterion is checked. Run the validator locally with the same command used by
CI:

```powershell
conda run -n netcat python scripts\check_domain_analysis_issue_plan.py
```

The validator scans every Markdown file in
`.scratch/manual-domain-orientation-calibration-implementation/issues`, rejects
missing or unknown statuses, duplicate ticket numbers, and status/checklist
contradictions. Every failure identifies the ticket path and violated rule.

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
