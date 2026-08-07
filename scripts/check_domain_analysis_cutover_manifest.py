from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any


REQUIRED_CATEGORIES = {
    "routing",
    "state_fields",
    "workers",
    "persistence_export",
    "tests",
}


def validate_cutover_manifest(root: Path, manifest_path: Path) -> int:
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    if payload.get("schema_version") != 1:
        raise ValueError("Cutover manifest schema_version must be 1.")
    _validate_preflight_composition(root, payload.get("preflight_composition"))
    _validate_invariants(payload.get("invariants"))
    entries = payload.get("entries")
    if not isinstance(entries, list) or not entries:
        raise ValueError("Cutover manifest entries must be a non-empty list.")
    identifiers = [entry.get("id") for entry in entries]
    if any(not isinstance(value, str) or not value for value in identifiers):
        raise ValueError("Every cutover entry requires a non-empty id.")
    if len(set(identifiers)) != len(identifiers):
        raise ValueError("Cutover entry ids must be unique.")
    categories = {entry.get("category") for entry in entries}
    if categories != REQUIRED_CATEGORIES:
        raise ValueError(
            "Cutover manifest categories must be exactly: "
            + ", ".join(sorted(REQUIRED_CATEGORIES))
        )
    for entry in entries:
        _validate_entry(root, entry)
    return len(entries)


def _validate_preflight_composition(root: Path, value: object) -> None:
    if not isinstance(value, str) or not value.strip() or "." not in value:
        raise ValueError("preflight_composition must be a dotted class path.")
    module_name, class_name = value.rsplit(".", 1)
    relative_path = Path(*module_name.split(".")).with_suffix(".py")
    path = (root / relative_path).resolve()
    if root.resolve() not in path.parents or not path.is_file():
        raise ValueError(
            "preflight_composition module does not resolve inside the repository."
        )
    text = path.read_text(encoding="utf-8")
    if re.search(rf"^class\s+{re.escape(class_name)}\b", text, re.MULTILINE) is None:
        raise ValueError("preflight_composition class does not exist.")


def _validate_invariants(value: object) -> None:
    if (
        not isinstance(value, list)
        or len(value) < 3
        or any(not isinstance(item, str) or not item.strip() for item in value)
        or len(set(value)) != len(value)
    ):
        raise ValueError(
            "invariants must contain at least three unique non-empty strings."
        )


def _validate_entry(root: Path, entry: dict[str, Any]) -> None:
    identifier = entry["id"]
    legacy = entry.get("legacy")
    if not isinstance(legacy, list) or not legacy:
        raise ValueError(f"{identifier}: legacy locators are required.")
    for locator in legacy:
        _validate_locator(
            root,
            locator,
            f"{identifier}: legacy",
            test_locator=entry.get("category") == "tests",
        )
    disposition = entry.get("disposition")
    replacements = entry.get("replacement")
    if not isinstance(replacements, list):
        raise ValueError(f"{identifier}: replacement must be a list.")
    if disposition == "replace":
        if not replacements:
            raise ValueError(f"{identifier}: replacement locators are required.")
        for locator in replacements:
            _validate_locator(root, locator, f"{identifier}: replacement")
        if entry.get("decision") is not None:
            raise ValueError(f"{identifier}: replace entries cannot have a decision.")
        return
    if disposition == "remove":
        if replacements:
            raise ValueError(f"{identifier}: remove entries cannot have replacements.")
        decision = entry.get("decision")
        if not isinstance(decision, str) or not decision.strip():
            raise ValueError(f"{identifier}: removal requires an explicit decision.")
        return
    raise ValueError(f"{identifier}: unsupported disposition {disposition!r}.")


def _validate_locator(
    root: Path,
    locator: object,
    label: str,
    *,
    test_locator: bool = False,
) -> None:
    if not isinstance(locator, dict):
        raise ValueError(f"{label}: locator must be an object.")
    relative_path = locator.get("path")
    anchors = locator.get("anchors")
    if not isinstance(relative_path, str) or not relative_path:
        raise ValueError(f"{label}: locator path is required.")
    if (
        not isinstance(anchors, list)
        or not anchors
        or any(not isinstance(anchor, str) or not anchor for anchor in anchors)
    ):
        raise ValueError(f"{label}: non-empty string anchors are required.")
    path = (root / relative_path).resolve()
    if root.resolve() not in path.parents:
        raise ValueError(f"{label}: path escapes the repository root.")
    if not path.is_file():
        raise ValueError(f"{label}: file does not exist: {relative_path}.")
    text = path.read_text(encoding="utf-8")
    missing = [anchor for anchor in anchors if anchor not in text]
    if missing:
        raise ValueError(f"{label}: missing anchors in {relative_path}: {missing!r}.")
    scope = locator.get("scope")
    if not test_locator:
        if scope is not None:
            raise ValueError(f"{label}: scope is only valid for legacy tests.")
        return
    if scope not in {"file", "anchors"}:
        raise ValueError(
            f"{label}: legacy test scope must be 'file' or 'anchors'."
        )
    if scope == "file" and re.search(
        r"^\s*(?:async\s+)?def\s+test_",
        text,
        re.MULTILINE,
    ) is None:
        raise ValueError(f"{label}: file scope does not contain tests.")


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    manifest_path = root / "docs" / "domain_analysis_cutover_manifest.json"
    count = validate_cutover_manifest(root, manifest_path)
    print(f"Domain Analysis cutover manifest passed: {count} entries.")


if __name__ == "__main__":
    main()
