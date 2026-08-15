from __future__ import annotations

import re
from pathlib import Path

from moltrack.analysis.domain_analysis.session_state import (
    DOMAIN_ANALYSIS_SESSION_SCHEMA_VERSION,
)
from moltrack.analysis.lattice_domain_calibration_models import (
    LATTICE_DOMAIN_CALIBRATION_SCHEMA_VERSION,
)
from moltrack.analysis.molecular_orientation_models import (
    MOLECULAR_ORIENTATION_SCHEMA_VERSION,
)
from moltrack.core.session import (
    MOLTRACK_SESSION_SCHEMA_VERSION,
    SUPPORTED_MOLTRACK_SESSION_SCHEMA_VERSIONS,
)
from moltrack.persistence.domain_analysis_export_schema import (
    DOMAIN_ANALYSIS_EXPORT_SCHEMA_VERSION,
)


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
DOCUMENTATION_ROOT = REPOSITORY_ROOT / "docs" / "moltrack"
DOCUMENTATION_FILES = (
    "README.md",
    "CONTEXT.md",
    "QUALITY_GATES.md",
    "DOMAIN_ANALYSIS_USER_GUIDE_DRAFT.md",
    "DOMAIN_ANALYSIS_TECHNICAL_REFERENCE_DRAFT.md",
    "DOMAIN_ANALYSIS_FORMATS_DRAFT.md",
    "DOMAIN_ANALYSIS_MIGRATION_AND_TROUBLESHOOTING_DRAFT.md",
)
MARKDOWN_LINK = re.compile(r"\[[^\]]+\]\(([^)]+)\)")


def test_domain_analysis_documentation_index_lists_the_delivery_set() -> None:
    index = (DOCUMENTATION_ROOT / "README.md").read_text(encoding="utf-8")

    for filename in DOCUMENTATION_FILES:
        path = DOCUMENTATION_ROOT / filename
        assert path.is_file(), filename
        if filename != "README.md":
            assert f"]({filename})" in index, filename


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
        DOCUMENTATION_ROOT / "DOMAIN_ANALYSIS_FORMATS_DRAFT.md"
    ).read_text(encoding="utf-8")
    supported_session_versions = "/".join(
        f"v{version}" for version in SUPPORTED_MOLTRACK_SESSION_SCHEMA_VERSIONS
    )

    expected_current_version_fragments = (
        f"| MolTrack session | v{MOLTRACK_SESSION_SCHEMA_VERSION}; "
        f"loader {supported_session_versions} |",
        f"| Domain Analysis state | v{DOMAIN_ANALYSIS_SESSION_SCHEMA_VERSION} |",
        f"| Domain Analysis export | v{DOMAIN_ANALYSIS_EXPORT_SCHEMA_VERSION} |",
        "| M6 Reference Dataset | "
        f"legacy v{LATTICE_DOMAIN_CALIBRATION_SCHEMA_VERSION} |",
        "| Orientation Reference Dataset | "
        f"legacy v{MOLECULAR_ORIENTATION_SCHEMA_VERSION} |",
    )

    for fragment in expected_current_version_fragments:
        assert fragment in reference, fragment
