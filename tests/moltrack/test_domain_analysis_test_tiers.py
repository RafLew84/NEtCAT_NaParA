from __future__ import annotations

import ast
from pathlib import Path


_TEST_ROOT = Path(__file__).parent
_REPOSITORY_ROOT = _TEST_ROOT.parents[1]
_TIER_VARIABLE = "DOMAIN_ANALYSIS_TEST_TIER"
_PUBLIC_WORKFLOW_TIERS = {"acceptance", "release"}
_EXPECTED_ACCEPTANCE_MODULES = {
    "test_domain_analysis_ttmapp_cutover.py",
    "ttmapp_cutover_ui_support.py",
}
_FORBIDDEN_PRIVATE_IDENTIFIERS = {"_save_as", "_MolTrackM6Adapter"}
_FORBIDDEN_INJECTION_KEYWORDS = {
    "session_restorer",
    "domain_analysis_composition_factory",
    "export_published",
    "export_audit",
    "export_legacy_published",
    "export_settings_for",
    "audit_export_settings_for",
    "legacy_export_settings_for",
}


def test_acceptance_and_release_modules_are_explicitly_tiered() -> None:
    tiered = {
        path.name
        for path in _TEST_ROOT.glob("*.py")
        if _declared_tier(path) in _PUBLIC_WORKFLOW_TIERS
    }
    named_as_public_workflow = {
        path.name
        for path in _TEST_ROOT.glob("*.py")
        if _claims_public_workflow(path)
    }

    assert _EXPECTED_ACCEPTANCE_MODULES.issubset(tiered)
    assert named_as_public_workflow.issubset(tiered)


def test_acceptance_and_release_modules_use_only_public_production_seams() -> None:
    violations = []
    for path in _TEST_ROOT.glob("*.py"):
        if _declared_tier(path) not in _PUBLIC_WORKFLOW_TIERS:
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            identifier = _identifier(node)
            if (
                identifier in _FORBIDDEN_PRIVATE_IDENTIFIERS
                or _is_private_adapter(identifier)
                or identifier in _FORBIDDEN_INJECTION_KEYWORDS
            ):
                violations.append(f"{path.name}:{node.lineno}: {identifier}")
            if (
                isinstance(node, ast.keyword)
                and node.arg in _FORBIDDEN_INJECTION_KEYWORDS
            ):
                violations.append(f"{path.name}:{node.lineno}: {node.arg}")

    assert not violations, "Forbidden acceptance/release seams:\n" + "\n".join(
        sorted(violations)
    )


def test_quality_workflow_runs_the_public_seam_guard() -> None:
    workflow = (
        _REPOSITORY_ROOT / ".github" / "workflows" / "moltrack-quality.yml"
    ).read_text(encoding="utf-8")

    assert '- "tests/moltrack/**"' in workflow
    assert (
        "python -m pytest "
        "tests\\moltrack\\test_domain_analysis_test_tiers.py -q"
    ) in workflow


def _declared_tier(path: Path) -> str | None:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    for statement in tree.body:
        if not isinstance(statement, ast.Assign) or len(statement.targets) != 1:
            continue
        target = statement.targets[0]
        if (
            isinstance(target, ast.Name)
            and target.id == _TIER_VARIABLE
            and isinstance(statement.value, ast.Constant)
            and isinstance(statement.value.value, str)
        ):
            return statement.value.value
    return None


def _claims_public_workflow(path: Path) -> bool:
    return path.stem.startswith("test_domain_analysis") and any(
        label in path.stem
        for label in ("acceptance", "release", "end_to_end")
    )


def _identifier(node: ast.AST) -> str | None:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    return None


def _is_private_adapter(identifier: str | None) -> bool:
    return bool(
        identifier
        and identifier.startswith("_")
        and identifier.endswith("Adapter")
    )
