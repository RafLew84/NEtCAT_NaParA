from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

from moltrack import __version__ as moltrack_version
from moltrack.analysis.domain_analysis.session_state import (
    DOMAIN_ANALYSIS_SESSION_SCHEMA_VERSION,
)
from moltrack.analysis.domain_analysis import (
    M6_PRESET_LIBRARY_SCHEMA_VERSION,
    M6_PRESET_SCHEMA_VERSION,
)
from moltrack.analysis.m6_validation_campaign_models import (
    M6_CAMPAIGN_REPORT_SCHEMA_VERSION,
)
from moltrack.core.session import (
    MOLTRACK_SESSION_SCHEMA_VERSION,
    SUPPORTED_MOLTRACK_SESSION_SCHEMA_VERSIONS,
)
from moltrack.persistence.correction_aware_export_schema import (
    CORRECTION_AWARE_EXPORT_SCHEMA_VERSION,
)
from moltrack.persistence.m6_reference_schema import (
    M6_REFERENCE_DATASET_SCHEMA_VERSION,
)
from moltrack.persistence.orientation_reference_schema import (
    ORIENTATION_REFERENCE_DATASET_SCHEMA_VERSION,
)
from moltrack.persistence.reference_dataset_reader import (
    REFERENCE_DATASET_ENVELOPE_VERSION,
)


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
DOCUMENTATION_ROOT = REPOSITORY_ROOT / "docs" / "moltrack"
DOCUMENTATION_RELEASE = REPOSITORY_ROOT / "docs" / "domain_analysis_documentation_release.json"
TTMAPP_RELEASE_VALIDATION = (
    REPOSITORY_ROOT / "docs" / "domain_analysis_ttmapp_release_validation.json"
)
DOCUMENTATION_FILES = (
    "README.md",
    "CONTEXT.md",
    "QUALITY_GATES.md",
    "DOMAIN_ANALYSIS_USER_GUIDE.md",
    "DOMAIN_ANALYSIS_TECHNICAL_REFERENCE.md",
    "DOMAIN_ANALYSIS_FORMATS.md",
    "DOMAIN_ANALYSIS_MIGRATION_AND_TROUBLESHOOTING.md",
)
MARKDOWN_LINK = re.compile(r"\[[^\]]+\]\(([^)]+)\)")
SCREENSHOT_WITH_CAPTION = re.compile(
    r"!\[([^\]]+)\]\((screenshots/[^)]+\.png)\)\n"
    r"\*Rysunek [^*]+\*"
)


def test_domain_analysis_documentation_index_lists_the_delivery_set() -> None:
    index = (DOCUMENTATION_ROOT / "README.md").read_text(encoding="utf-8")

    for filename in DOCUMENTATION_FILES:
        path = DOCUMENTATION_ROOT / filename
        assert path.is_file(), filename
        if filename != "README.md":
            assert f"]({filename})" in index, filename

    assert "_DRAFT" not in index


def test_domain_analysis_documentation_has_no_broken_local_links() -> None:
    failures: list[str] = []

    for filename in DOCUMENTATION_FILES:
        path = DOCUMENTATION_ROOT / filename
        text = path.read_text(encoding="utf-8")
        for match in MARKDOWN_LINK.finditer(text):
            raw_target = match.group(1)
            if raw_target.startswith("#") or "://" in raw_target:
                continue
            target = raw_target.split("#", 1)[0].split("?", 1)[0]
            if target and not (path.parent / target).resolve().exists():
                failures.append(f"{filename}: {raw_target}")

    assert not failures, "Broken local Markdown links:\n" + "\n".join(failures)


def test_format_reference_matches_current_schema_constants() -> None:
    reference = (
        DOCUMENTATION_ROOT / "DOMAIN_ANALYSIS_FORMATS.md"
    ).read_text(encoding="utf-8")
    supported_session_versions = "/".join(
        f"v{version}" for version in SUPPORTED_MOLTRACK_SESSION_SCHEMA_VERSIONS
    )

    expected_current_version_fragments = (
        f"| MolTrack session | v{MOLTRACK_SESSION_SCHEMA_VERSION}; "
        f"loader {supported_session_versions} | v{MOLTRACK_SESSION_SCHEMA_VERSION}; "
        f"loader {supported_session_versions} |",
        f"| Domain Analysis state | v{DOMAIN_ANALYSIS_SESSION_SCHEMA_VERSION} |",
        f"| Domain Analysis export | v{CORRECTION_AWARE_EXPORT_SCHEMA_VERSION} |",
        "| M6 Reference Dataset | "
        f"v{M6_REFERENCE_DATASET_SCHEMA_VERSION} |",
        "| Orientation Reference Dataset | "
        f"v{ORIENTATION_REFERENCE_DATASET_SCHEMA_VERSION} |",
        "| Reference collection envelope | "
        f"manifest schema v{REFERENCE_DATASET_ENVELOPE_VERSION} |",
        "| M6 preset | "
        f"{M6_PRESET_LIBRARY_SCHEMA_VERSION} / {M6_PRESET_SCHEMA_VERSION} |",
        "| M6 calibration campaign report | "
        f"{M6_CAMPAIGN_REPORT_SCHEMA_VERSION} |",
    )

    for fragment in expected_current_version_fragments:
        assert fragment in reference, fragment


def test_quick_start_uses_production_control_names_and_signoff_contract() -> None:
    guide = (DOCUMENTATION_ROOT / "DOMAIN_ANALYSIS_USER_GUIDE.md").read_text(
        encoding="utf-8"
    )

    assert "`Domain Analysis...`" in guide
    assert "`Analyze range`" in guide
    assert "`Analysis > Domain Analysis`" not in guide
    assert "Sign-off ma operatora" not in guide
    assert "Sign-off zachowuje timestamp i fingerprint" in guide


def test_technical_reference_names_the_single_readiness_owner() -> None:
    reference = (
        DOCUMENTATION_ROOT / "DOMAIN_ANALYSIS_TECHNICAL_REFERENCE.md"
    ).read_text(encoding="utf-8")

    assert "`ReferenceReadinessPolicy` jest jedynym właścicielem" in reference
    assert "`evaluate_snapshot(...)`" in reference
    assert "`evaluate_dataset(...)`" in reference


def test_final_documentation_has_no_release_placeholders() -> None:
    for filename in DOCUMENTATION_FILES:
        text = (DOCUMENTATION_ROOT / filename).read_text(encoding="utf-8")
        assert "_DRAFT" not in text, filename
        assert "TODO" not in text, filename
        assert "(draft)" not in text.casefold(), filename


def test_user_guide_uses_verified_production_screenshots() -> None:
    guide = (DOCUMENTATION_ROOT / "DOMAIN_ANALYSIS_USER_GUIDE.md").read_text(
        encoding="utf-8"
    )
    release = json.loads(DOCUMENTATION_RELEASE.read_text(encoding="utf-8"))
    documented = {
        target: alt
        for alt, target in SCREENSHOT_WITH_CAPTION.findall(guide)
        if alt.strip()
    }
    released = {entry["path"]: entry for entry in release["screenshots"]}

    assert set(documented) == set(released)
    assert {entry["stage"] for entry in released.values()} == {
        "Analyze",
        "Correct",
        "Review",
        "Calibrate",
    }
    for relative_path, entry in released.items():
        screenshot = DOCUMENTATION_ROOT / relative_path
        assert screenshot.is_file(), relative_path
        assert hashlib.sha256(screenshot.read_bytes()).hexdigest() == entry["sha256"]


def test_documentation_release_records_clean_ttmapp_walkthrough_and_help() -> None:
    release = json.loads(DOCUMENTATION_RELEASE.read_text(encoding="utf-8"))
    acceptance = json.loads(TTMAPP_RELEASE_VALIDATION.read_text(encoding="utf-8"))

    assert release["validation_schema_version"] == 2
    assert release["validated_at"] == acceptance["validated_at"]
    assert release["application_version"] == moltrack_version
    assert release["result"] == "passed"
    assert release["workflow"] == (
        "clean-session TTMAPP variant C production MainWindow walkthrough"
    )
    assert release["acceptance_evidence"] == (
        "docs/domain_analysis_ttmapp_release_validation.json"
    )
    assert acceptance["campaign"]["status"] == "validated"
    assert acceptance["validation_schema_version"] == 3
    assert acceptance["workflow_assertions"]["production_main_window"] is True
    assert acceptance["workflow_assertions"][
        "m6_reference_root_and_child_v2"
    ] is True
    assert release["screenshot_source"] == (
        "production MolTrackMainWindow composition"
    )
    assert len(acceptance["fixture"]["domain_geometry"]) >= 2
    assert release["help"] == {
        "menu": "Help",
        "action": "Domain Analysis Guide",
        "guide": "docs/moltrack/DOMAIN_ANALYSIS_USER_GUIDE.md",
        "result": "passed",
    }


def test_documented_code_size_limits_match_the_release_policy() -> None:
    gates = (DOCUMENTATION_ROOT / "QUALITY_GATES.md").read_text(encoding="utf-8")

    for fragment in (
        "Prefer 250-500 physical lines per MolTrack production file",
        "hard limit is\n800",
        "at most 30 functions/methods and 10 classes",
        "hard limit is\n80",
        "The JSON baseline lists only existing exceptions",
        "An exception may not grow",
        "adding or raising an exception together with\nthe offending code is rejected",
    ):
        assert fragment in gates, fragment
